# trading_engine.py - 修复版网格交易引擎
import asyncio
import logging
import hashlib
import time
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json

from core_system import (
    OrderInfo, OrderSide, OrderStatus, GridLevel, TradingState,
    DatabaseManager, ConfigManager, HTTPClient, TradingSystemError,
    handle_exceptions
)

class MarketState(Enum):
    SIDEWAYS = "sideways"
    BULL = "bull"
    BEAR = "bear"
    VOLATILE = "volatile"

class GridCalculator:
    """网格价格计算器"""
    
    @staticmethod
    def calculate_grid_prices(center_price: Decimal, range_percent: Decimal, 
                            spacing_percent: Decimal, max_orders: int = 50) -> Dict[str, List[Decimal]]:
        """计算网格价格"""
        try:
            buy_prices = []
            sell_prices = []
            
            # 计算价格边界
            min_price = center_price * (Decimal("1") - range_percent)
            max_price = center_price * (Decimal("1") + range_percent)
            
            # 生成买单价格（向下）
            current_price = center_price
            for i in range(max_orders // 2):
                current_price = current_price * (Decimal("1") - spacing_percent)
                if current_price >= min_price:
                    buy_prices.append(current_price.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
                else:
                    break
            
            # 生成卖单价格（向上）
            current_price = center_price
            for i in range(max_orders // 2):
                current_price = current_price * (Decimal("1") + spacing_percent)
                if current_price <= max_price:
                    sell_prices.append(current_price.quantize(Decimal('0.01'), rounding=ROUND_DOWN))
                else:
                    break
            
            return {
                "buy_prices": sorted(buy_prices, reverse=True),
                "sell_prices": sorted(sell_prices)
            }
            
        except Exception as e:
            logging.error(f"Grid calculation failed: {e}")
            return {"buy_prices": [], "sell_prices": []}
    
    @staticmethod
    def calculate_order_quantity(order_size_usdt: Decimal, price: Decimal, 
                               symbol_info: Optional[Dict] = None) -> Decimal:
        """计算订单数量"""
        try:
            if price <= 0:
                raise ValueError("Price must be positive")
            
            quantity = order_size_usdt / price
            
            # 应用交易所规则
            if symbol_info:
                step_size = Decimal(str(symbol_info.get('stepSize', '0.000001')))
                min_qty = Decimal(str(symbol_info.get('minQty', '0.000001')))
                
                # 按步长调整
                if step_size > 0:
                    quantity = (quantity // step_size) * step_size
                
                # 检查最小数量
                if quantity < min_qty:
                    quantity = min_qty
            else:
                # 默认保留6位小数
                quantity = quantity.quantize(Decimal('0.000001'), rounding=ROUND_DOWN)
            
            return quantity
            
        except Exception as e:
            logging.error(f"Quantity calculation failed: {e}")
            return Decimal("0")

class RiskManager:
    """风险管理器"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
    async def check_risk_limits(self, db_manager: DatabaseManager) -> Tuple[bool, str]:
        """检查风险限制"""
        try:
            state = await db_manager.get_system_state()
            
            # 获取风险配置
            max_drawdown = Decimal(str(self.config.get('trading.risk_management.max_drawdown', 0.20)))
            stop_loss = Decimal(str(self.config.get('trading.risk_management.stop_loss', 0.15)))
            initial_balance = Decimal(str(self.config.get('trading.initial_balance', 1000)))
            
            # 检查最大回撤
            if state.total_balance > 0 and initial_balance > 0:
                drawdown = (initial_balance - state.total_balance) / initial_balance
                if drawdown > max_drawdown:
                    return False, f"Maximum drawdown exceeded: {drawdown:.2%} > {max_drawdown:.2%}"
            
            # 检查止损
            if state.total_pnl < 0:
                loss_percent = abs(state.total_pnl) / initial_balance
                if loss_percent > stop_loss:
                    return False, f"Stop loss triggered: {loss_percent:.2%} > {stop_loss:.2%}"
            
            return True, "Risk check passed"
            
        except Exception as e:
            self.logger.error(f"Risk check failed: {e}")
            return False, f"Risk check error: {str(e)}"
    
    def calculate_position_size(self, symbol: str, price: Decimal, 
                              risk_percent: Decimal = Decimal("0.02")) -> Decimal:
        """计算仓位大小"""
        try:
            # 基于风险百分比计算仓位
            account_balance = Decimal(str(self.config.get('trading.initial_balance', 1000)))
            risk_amount = account_balance * risk_percent
            
            # 基于价格计算数量
            quantity = risk_amount / price
            
            return quantity.quantize(Decimal('0.000001'), rounding=ROUND_DOWN)
            
        except Exception as e:
            self.logger.error(f"Position size calculation failed: {e}")
            return Decimal("0")

class BinanceAPIClient:
    """Binance API客户端"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # API配置
        self.api_key = self.config.get('api.binance_api_key', '')
        self.api_secret = self.config.get('api.binance_api_secret', '')
        self.testnet = self.config.get('api.use_testnet', True)
        
        # API端点
        if self.testnet:
            self.base_url = "https://testnet.binancefuture.com"
        else:
            self.base_url = "https://fapi.binance.com"
            
        self.http_client: Optional[HTTPClient] = None
        
        # 符合真实Binance库的接口
        self.testnet_mode = self.testnet
    
    async def __aenter__(self):
        """异步上下文管理器"""
        self.http_client = HTTPClient(self.base_url)
        await self.http_client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        if self.http_client:
            await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """生成签名"""
        import hmac
        
        query_string = "&".join([f"{key}={value}" for key, value in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'X-MBX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        }
    
    async def ping(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            if self.testnet:
                # 测试网模式返回模拟数据
                return {'ping': 'pong', 'timestamp': int(time.time() * 1000)}
            
            return await self.http_client.get("/fapi/v1/ping")
            
        except Exception as e:
            self.logger.error(f"Ping failed: {e}")
            raise TradingSystemError(f"API ping failed: {e}")
    
    async def futures_symbol_ticker(self, symbol: str) -> Dict[str, Any]:
        """获取价格"""
        try:
            if self.testnet:
                # 测试网模式返回模拟价格
                base_prices = {
                    'BTCUSDT': 68000,
                    'ETHUSDT': 3800,
                    'BNBUSDT': 630,
                    'ADAUSDT': 1.2,
                    'SOLUSDT': 180
                }
                base_price = base_prices.get(symbol, 50000)
                # 添加随机波动
                import random
                price = base_price * (1 + random.uniform(-0.02, 0.02))
                
                return {
                    'symbol': symbol,
                    'price': f"{price:.2f}",
                    'time': int(time.time() * 1000)
                }
            
            return await self.http_client.get(f"/fapi/v1/ticker/price?symbol={symbol}")
            
        except Exception as e:
            self.logger.error(f"Failed to get ticker for {symbol}: {e}")
            raise TradingSystemError(f"Failed to get ticker: {e}")
    
    async def futures_account(self) -> Dict[str, Any]:
        """获取账户信息"""
        try:
            if self.testnet:
                # 测试网模式返回模拟账户信息
                return {
                    'totalWalletBalance': '10000.00',
                    'availableBalance': '8500.00',
                    'totalUnrealizedProfit': '0.00',
                    'totalMarginBalance': '10000.00'
                }
            
            params = {
                'timestamp': int(time.time() * 1000)
            }
            params['signature'] = self._generate_signature(params)
            
            return await self.http_client.get("/fapi/v2/account", params=params, 
                                            headers=self._get_headers())
            
        except Exception as e:
            self.logger.error(f"Failed to get account info: {e}")
            raise TradingSystemError(f"Failed to get account: {e}")
    
    async def futures_create_order(self, symbol: str, side: str, type_: str,
                                 quantity: str, price: str = None, 
                                 timeInForce: str = 'GTC') -> Dict[str, Any]:
        """创建订单"""
        try:
            if self.testnet:
                # 测试网模式返回模拟订单
                order_id = int(time.time() * 1000)
                return {
                    'orderId': order_id,
                    'symbol': symbol,
                    'status': 'NEW',
                    'clientOrderId': f"test_{order_id}",
                    'side': side,
                    'type': type_,
                    'quantity': quantity,
                    'price': price or '0',
                    'timeInForce': timeInForce
                }
            
            params = {
                'symbol': symbol,
                'side': side,
                'type': type_,
                'quantity': quantity,
                'timestamp': int(time.time() * 1000)
            }
            
            if price:
                params['price'] = price
            if timeInForce:
                params['timeInForce'] = timeInForce
                
            params['signature'] = self._generate_signature(params)
            
            return await self.http_client.post("/fapi/v1/order", json=params,
                                             headers=self._get_headers())
            
        except Exception as e:
            self.logger.error(f"Failed to create order: {e}")
            raise TradingSystemError(f"Failed to create order: {e}")
    
    async def futures_get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取开放订单"""
        try:
            if self.testnet:
                # 测试网模式返回空列表
                return []
            
            params = {
                'timestamp': int(time.time() * 1000)
            }
            
            if symbol:
                params['symbol'] = symbol
                
            params['signature'] = self._generate_signature(params)
            
            return await self.http_client.get("/fapi/v1/openOrders", params=params,
                                            headers=self._get_headers())
            
        except Exception as e:
            self.logger.error(f"Failed to get open orders: {e}")
            return []
    
    async def futures_cancel_order(self, symbol: str, orderId: str) -> Dict[str, Any]:
        """取消订单"""
        try:
            if self.testnet:
                # 测试网模式返回模拟取消结果
                return {
                    'orderId': orderId,
                    'symbol': symbol,
                    'status': 'CANCELED'
                }
            
            params = {
                'symbol': symbol,
                'orderId': orderId,
                'timestamp': int(time.time() * 1000)
            }
            params['signature'] = self._generate_signature(params)
            
            return await self.http_client.post("/fapi/v1/order", json=params,
                                             headers=self._get_headers())
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order: {e}")
            raise TradingSystemError(f"Failed to cancel order: {e}")

class GridTradingEngine:
    """网格交易引擎"""
    
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 交易客户端
        self.binance_client: Optional[BinanceAPIClient] = None
        
        # 风险管理
        self.risk_manager = RiskManager(config_manager)
        
        # 网格计算器
        self.calculator = GridCalculator()
        
        # 状态变量
        self.running = False
        self.current_price = Decimal("0")
        self.symbol = config_manager.get('trading.symbol', 'BTCUSDT')
        
        # 订单缓存
        self.local_orders: Dict[str, OrderInfo] = {}
        
        # 性能统计
        self.start_time = time.time()
        self.orders_created = 0
        self.orders_filled = 0
    
    async def initialize(self) -> bool:
        """初始化交易引擎"""
        try:
            self.logger.info("Initializing Grid Trading Engine...")
            
            # 初始化Binance客户端
            self.binance_client = BinanceAPIClient(self.config)
            
            # 验证API连接
            async with self.binance_client as client:
                await client.ping()
                self.logger.info("Binance API connection verified")
                
                # 获取当前价格
                ticker = await client.futures_symbol_ticker(self.symbol)
                self.current_price = Decimal(ticker['price'])
                self.logger.info(f"Current price for {self.symbol}: {self.current_price}")
            
            # 初始化网格
            await self._initialize_grids()
            
            # 记录初始化事件
            await self.db.log_event("INFO", "GridEngine", "Engine initialized successfully", {
                "symbol": self.symbol,
                "current_price": float(self.current_price)
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Engine initialization failed: {e}")
            return False
    
    async def _initialize_grids(self):
        """初始化所有网格层级"""
        try:
            grid_configs = self.config.get('trading.grid_configs', {})
            
            for level_name, level_config in grid_configs.items():
                grid_level = GridLevel(level_name)
                await self._create_grid_level(grid_level, level_config)
                
        except Exception as e:
            self.logger.error(f"Grid initialization failed: {e}")
    
    async def _create_grid_level(self, grid_level: GridLevel, config: Dict[str, Any]):
        """创建单个网格层级"""
        try:
            range_percent = Decimal(str(config['range']))
            spacing_percent = Decimal(str(config['spacing']))
            order_size = Decimal(str(config['size']))
            
            # 计算网格价格
            grid_prices = self.calculator.calculate_grid_prices(
                self.current_price, range_percent, spacing_percent
            )
            
            orders_created = 0
            
            # 创建买单
            for i, price in enumerate(grid_prices["buy_prices"]):
                quantity = self.calculator.calculate_order_quantity(order_size, price)
                
                if quantity > 0:
                    order = self._create_order_info(
                        self.symbol, OrderSide.BUY, price, quantity, grid_level, i
                    )
                    
                    if await self._place_order(order):
                        orders_created += 1
            
            # 创建卖单
            for i, price in enumerate(grid_prices["sell_prices"]):
                quantity = self.calculator.calculate_order_quantity(order_size, price)
                
                if quantity > 0:
                    order = self._create_order_info(
                        self.symbol, OrderSide.SELL, price, quantity, grid_level, i
                    )
                    
                    if await self._place_order(order):
                        orders_created += 1
            
            self.logger.info(f"Grid {grid_level.value} created with {orders_created} orders")
            
        except Exception as e:
            self.logger.error(f"Failed to create grid {grid_level.value}: {e}")
    
    def _create_order_info(self, symbol: str, side: OrderSide, price: Decimal,
                          quantity: Decimal, grid_level: GridLevel, grid_index: int) -> OrderInfo:
        """创建订单信息对象"""
        order_id = f"{symbol}_{grid_level.value}_{side.value}_{grid_index}_{int(time.time())}"
        
        return OrderInfo(
            id=order_id,
            symbol=symbol,
            side=side,
            price=price,
            quantity=quantity,
            status=OrderStatus.PENDING,
            grid_level=grid_level,
            grid_index=grid_index
        )
    
    async def _place_order(self, order: OrderInfo) -> bool:
        """下单到交易所"""
        try:
            # 保存到数据库
            await self.db.save_order(order)
            
            # 下单到交易所
            async with self.binance_client as client:
                result = await client.futures_create_order(
                    symbol=order.symbol,
                    side=order.side.value,
                    type_='LIMIT',
                    quantity=str(order.quantity),
                    price=str(order.price),
                    timeInForce='GTC'
                )
                
                # 更新订单状态
                order.exchange_order_id = str(result['orderId'])
                order.status = OrderStatus.NEW
                
                await self.db.update_order_status(
                    order.id, OrderStatus.NEW, order.exchange_order_id
                )
                
                # 缓存订单
                self.local_orders[order.id] = order
                self.orders_created += 1
                
                self.logger.debug(f"Order placed: {order.side.value} {order.quantity} @ {order.price}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            await self.db.update_order_status(order.id, OrderStatus.FAILED)
            return False
    
    @handle_exceptions
    async def run_trading_loop(self):
        """运行交易循环"""
        self.running = True
        self.logger.info("Starting trading loop...")
        
        check_interval = self.config.get('system.check_interval', 5)
        
        while self.running:
            try:
                # 更新市场价格
                await self._update_market_price()
                
                # 检查风险限制
                risk_ok, risk_msg = await self.risk_manager.check_risk_limits(self.db)
                if not risk_ok:
                    self.logger.warning(f"Risk limit exceeded: {risk_msg}")
                    await self._emergency_stop(risk_msg)
                    break
                
                # 检查订单状态
                await self._check_order_status()
                
                # 更新系统状态
                await self._update_system_state()
                
                # 等待下一个检查周期
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(10)
    
    async def _update_market_price(self):
        """更新市场价格"""
        try:
            async with self.binance_client as client:
                ticker = await client.futures_symbol_ticker(self.symbol)
                self.current_price = Decimal(ticker['price'])
                
        except Exception as e:
            self.logger.error(f"Failed to update market price: {e}")
    
    async def _check_order_status(self):
        """检查订单状态"""
        try:
            # 获取本地活跃订单
            active_orders = await self.db.get_orders(status=OrderStatus.NEW)
            
            if not active_orders:
                return
            
            # 获取交易所开放订单
            async with self.binance_client as client:
                exchange_orders = await client.futures_get_open_orders(self.symbol)
                exchange_order_ids = {str(order['orderId']) for order in exchange_orders}
            
            # 检查已成交的订单
            for order in active_orders:
                if order.exchange_order_id and order.exchange_order_id not in exchange_order_ids:
                    await self._process_filled_order(order)
                    
        except Exception as e:
            self.logger.error(f"Order status check failed: {e}")
    
    async def _process_filled_order(self, order: OrderInfo):
        """处理已成交订单"""
        try:
            # 计算利润
            profit = self._calculate_order_profit(order)
            
            # 更新订单状态
            await self.db.update_order_status(
                order.id, OrderStatus.FILLED,
                filled_at=datetime.now(),
                profit=profit
            )
            
            # 在相同位置重新下单
            await self._rebuild_order(order)
            
            self.orders_filled += 1
            self.logger.info(f"Order filled: {order.side.value} {order.quantity} @ {order.price}, profit: {profit}")
            
            # 记录成交事件
            await self.db.log_event("INFO", "GridEngine", "Order filled", {
                "order_id": order.id,
                "symbol": order.symbol,
                "side": order.side.value,
                "price": float(order.price),
                "quantity": float(order.quantity),
                "profit": float(profit)
            })
            
        except Exception as e:
            self.logger.error(f"Failed to process filled order: {e}")
    
    def _calculate_order_profit(self, order: OrderInfo) -> Decimal:
        """计算订单利润"""
        try:
            # 简化的利润计算
            grid_spacing = self._get_grid_spacing(order.grid_level)
            order_value = order.price * order.quantity
            
            # 预期利润为网格间距的一半
            expected_profit = order_value * grid_spacing * Decimal("0.5")
            
            # 扣除手续费（0.1%）
            commission = order_value * Decimal("0.001")
            
            return expected_profit - commission
            
        except Exception as e:
            self.logger.error(f"Profit calculation failed: {e}")
            return Decimal("0")
    
    def _get_grid_spacing(self, grid_level: GridLevel) -> Decimal:
        """获取网格间距"""
        grid_configs = self.config.get('trading.grid_configs', {})
        level_config = grid_configs.get(grid_level.value, {})
        return Decimal(str(level_config.get('spacing', 0.01)))
    
    async def _rebuild_order(self, filled_order: OrderInfo):
        """重建订单"""
        try:
            # 创建新订单（在相同位置）
            new_order = self._create_order_info(
                filled_order.symbol,
                filled_order.side,
                filled_order.price,
                filled_order.quantity,
                filled_order.grid_level,
                filled_order.grid_index
            )
            
            await self._place_order(new_order)
            
        except Exception as e:
            self.logger.error(f"Failed to rebuild order: {e}")
    
    async def _update_system_state(self):
        """更新系统状态"""
        try:
            # 获取账户信息
            async with self.binance_client as client:
                account_info = await client.futures_account()
                
                total_balance = Decimal(account_info['totalWalletBalance'])
                available_balance = Decimal(account_info['availableBalance'])
            
            # 计算活跃订单数
            active_orders = await self.db.get_orders(status=OrderStatus.NEW)
            
            # 计算总盈亏
            # 这里应该从交易记录计算，简化处理
            initial_balance = Decimal(str(self.config.get('trading.initial_balance', 1000)))
            total_pnl = total_balance - initial_balance
            
            # 更新系统状态
            state = TradingState(
                running=self.running,
                current_price=self.current_price,
                active_orders=len(active_orders),
                total_balance=total_balance,
                available_balance=available_balance,
                total_pnl=total_pnl,
                last_update=datetime.now()
            )
            
            await self.db.save_system_state(state)
            
        except Exception as e:
            self.logger.error(f"Failed to update system state: {e}")
    
    async def _emergency_stop(self, reason: str):
        """紧急停止"""
        self.logger.critical(f"Emergency stop triggered: {reason}")
        self.running = False
        
        try:
            # 取消所有挂单
            active_orders = await self.db.get_orders(status=OrderStatus.NEW)
            
            async with self.binance_client as client:
                for order in active_orders:
                    if order.exchange_order_id:
                        try:
                            await client.futures_cancel_order(
                                order.symbol, order.exchange_order_id
                            )
                            await self.db.update_order_status(order.id, OrderStatus.CANCELED)
                        except Exception as e:
                            self.logger.error(f"Failed to cancel order {order.id}: {e}")
            
            # 记录紧急停止事件
            await self.db.log_event("CRITICAL", "GridEngine", "Emergency stop", {
                "reason": reason,
                "canceled_orders": len(active_orders)
            })
            
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
    
    async def stop(self):
        """停止交易引擎"""
        self.running = False
        self.logger.info("Grid Trading Engine stopped")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        try:
            uptime_seconds = int(time.time() - self.start_time)
            
            return {
                "running": self.running,
                "symbol": self.symbol,
                "current_price": float(self.current_price),
                "orders_created": self.orders_created,
                "orders_filled": self.orders_filled,
                "uptime_seconds": uptime_seconds,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查API连接
            api_healthy = False
            try:
                async with self.binance_client as client:
                    await client.ping()
                    api_healthy = True
            except:
                api_healthy = False
            
            # 检查数据库状态
            db_healthy = False
            try:
                await self.db.get_system_state()
                db_healthy = True
            except:
                db_healthy = False
            
            overall_healthy = api_healthy and db_healthy and self.running
            
            return {
                "status": "healthy" if overall_healthy else "unhealthy",
                "api_connection": api_healthy,
                "database": db_healthy,
                "engine_running": self.running,
                "current_price": float(self.current_price) if self.current_price > 0 else None
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }