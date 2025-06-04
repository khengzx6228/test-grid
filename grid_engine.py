# grid_engine.py - 网格交易引擎
import asyncio
import logging
import time
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from data_models import *
from database_manager import DatabaseManager

class GridCalculator:
    """网格价格计算器"""
    
    @staticmethod
    def calculate_grid_levels(center_price: Decimal, config: TradingConfig) -> Dict[GridLevel, Dict[str, List[Decimal]]]:
        """计算所有网格层级的价格"""
        grids = {}
        
        # 高频套利层
        grids[GridLevel.HIGH_FREQ] = GridCalculator._calculate_single_grid(
            center_price, config.high_freq_range, config.high_freq_spacing
        )
        
        # 主趋势层
        grids[GridLevel.MAIN_TREND] = GridCalculator._calculate_single_grid(
            center_price, config.main_trend_range, config.main_trend_spacing
        )
        
        # 保险层
        grids[GridLevel.INSURANCE] = GridCalculator._calculate_single_grid(
            center_price, config.insurance_range, config.insurance_spacing
        )
        
        return grids
    
    @staticmethod
    def _calculate_single_grid(center_price: Decimal, range_percent: Decimal, spacing_percent: Decimal) -> Dict[str, List[Decimal]]:
        """计算单个网格层级的价格"""
        buy_prices = []
        sell_prices = []
        
        # 计算价格边界
        min_price = center_price * (Decimal("1") - range_percent)
        max_price = center_price * (Decimal("1") + range_percent)
        
        # 生成买单价格（中心价格下方）
        current_price = center_price
        while current_price > min_price:
            current_price = current_price * (Decimal("1") - spacing_percent)
            if current_price >= min_price:
                buy_prices.append(current_price)
        
        # 生成卖单价格（中心价格上方）
        current_price = center_price
        while current_price < max_price:
            current_price = current_price * (Decimal("1") + spacing_percent)
            if current_price <= max_price:
                sell_prices.append(current_price)
        
        return {
            "buy_prices": sorted(buy_prices, reverse=True),
            "sell_prices": sorted(sell_prices)
        }
    
    @staticmethod
    def calculate_order_quantity(order_size_usdt: Decimal, price: Decimal) -> Decimal:
        """计算订单数量"""
        quantity = order_size_usdt / price
        # 保留6位小数
        return quantity.quantize(Decimal('0.000001'))

class MarketAnalyzer:
    """市场分析器"""
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.price_history: List[Decimal] = []
        self.volume_history: List[Decimal] = []
    
    def add_market_data(self, price: Decimal, volume: Decimal = Decimal("0")):
        """添加市场数据"""
        self.price_history.append(price)
        self.volume_history.append(volume)
        
        # 保持窗口大小
        if len(self.price_history) > self.window_size:
            self.price_history.pop(0)
        if len(self.volume_history) > self.window_size:
            self.volume_history.pop(0)
    
    def detect_market_state(self) -> MarketState:
        """检测市场状态"""
        if len(self.price_history) < 5:
            return MarketState.SIDEWAYS
        
        # 计算价格变化和波动率
        recent_prices = self.price_history[-5:]
        price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
        volatility = self._calculate_volatility()
        
        # 判断市场状态
        if volatility > Decimal("0.05"):  # 波动率 > 5%
            return MarketState.VOLATILE
        elif price_change > Decimal("0.02"):  # 涨幅 > 2%
            return MarketState.BULL
        elif price_change < Decimal("-0.02"):  # 跌幅 > 2%
            return MarketState.BEAR
        else:
            return MarketState.SIDEWAYS
    
    def _calculate_volatility(self) -> Decimal:
        """计算价格波动率"""
        if len(self.price_history) < 2:
            return Decimal("0")
        
        changes = []
        for i in range(1, len(self.price_history)):
            change = abs(self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1]
            changes.append(change)
        
        if not changes:
            return Decimal("0")
        
        # 计算标准差
        mean_change = sum(changes) / len(changes)
        variance = sum((change - mean_change) ** 2 for change in changes) / len(changes)
        return variance ** Decimal("0.5")

class RiskManager:
    """风险管理器"""
    
    def __init__(self, config: TradingConfig, db: DatabaseManager):
        self.config = config
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    def check_risk_limits(self, current_balance: Decimal, current_pnl: Decimal) -> Tuple[bool, str]:
        """检查风险限制"""
        # 检查最大回撤
        if current_balance > 0:
            drawdown = (self.config.initial_balance - current_balance) / self.config.initial_balance
            if drawdown > self.config.max_drawdown:
                return False, f"最大回撤超限: {drawdown:.2%} > {self.config.max_drawdown:.2%}"
        
        # 检查止损
        if current_pnl < 0:
            loss_percent = abs(current_pnl) / self.config.initial_balance
            if loss_percent > self.config.stop_loss:
                return False, f"止损触发: {loss_percent:.2%} > {self.config.stop_loss:.2%}"
        
        return True, "风险检查通过"
    
    def should_reduce_position(self, current_pnl: Decimal) -> bool:
        """判断是否应该减仓"""
        if current_pnl < 0:
            loss_percent = abs(current_pnl) / self.config.initial_balance
            # 当亏损超过止损阈值的50%时开始减仓
            return loss_percent > (self.config.stop_loss * Decimal("0.5"))
        return False

class GridTradingEngine:
    """网格交易引擎主类"""
    
    def __init__(self, config: TradingConfig, binance_client, db: DatabaseManager):
        self.config = config
        self.binance = binance_client
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # 核心组件
        self.calculator = GridCalculator()
        self.analyzer = MarketAnalyzer()
        self.risk_manager = RiskManager(config, db)
        
        # 状态变量
        self.current_price = Decimal("0")
        self.running = False
        self.last_grid_rebuild = {}
        self.order_cache = {}
        
        # 性能统计
        self.start_time = time.time()
        self.total_orders_created = 0
        self.total_orders_filled = 0
    
    async def initialize(self) -> bool:
        """初始化引擎"""
        try:
            self.logger.info("Initializing Grid Trading Engine...")
            
            # 获取当前价格
            ticker = await self.binance.futures_symbol_ticker(symbol=self.config.symbol)
            self.current_price = Decimal(ticker['price'])
            
            self.logger.info(f"Current price: {self.current_price}")
            
            # 初始化网格
            await self._initialize_all_grids()
            
            # 记录初始化事件
            self.db.log_event("INFO", "GridEngine", "Engine initialized successfully", {
                "symbol": self.config.symbol,
                "current_price": float(self.current_price),
                "grid_levels": [level.value for level in GridLevel]
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize engine: {e}")
            return False
    
    async def _initialize_all_grids(self):
        """初始化所有网格层级"""
        grids = self.calculator.calculate_grid_levels(self.current_price, self.config)
        
        for grid_level in GridLevel:
            await self._initialize_single_grid(grid_level, grids[grid_level])
            self.last_grid_rebuild[grid_level] = datetime.now()
    
    async def _initialize_single_grid(self, grid_level: GridLevel, grid_prices: Dict[str, List[Decimal]]):
        """初始化单个网格层级"""
        try:
            # 获取订单大小
            if grid_level == GridLevel.HIGH_FREQ:
                order_size = self.config.high_freq_size
            elif grid_level == GridLevel.MAIN_TREND:
                order_size = self.config.main_trend_size
            else:
                order_size = self.config.insurance_size
            
            orders_created = 0
            
            # 创建买单
            for i, price in enumerate(grid_prices["buy_prices"]):
                quantity = self.calculator.calculate_order_quantity(order_size, price)
                
                order = OrderInfo(
                    id=f"{grid_level.value}_buy_{i}_{int(time.time())}",
                    exchange_order_id=None,
                    symbol=self.config.symbol,
                    side=OrderSide.BUY,
                    price=price,
                    quantity=quantity,
                    status=OrderStatus.PENDING,
                    grid_level=grid_level,
                    grid_index=i
                )
                
                if await self._place_order(order):
                    orders_created += 1
            
            # 创建卖单
            for i, price in enumerate(grid_prices["sell_prices"]):
                quantity = self.calculator.calculate_order_quantity(order_size, price)
                
                order = OrderInfo(
                    id=f"{grid_level.value}_sell_{i}_{int(time.time())}",
                    exchange_order_id=None,
                    symbol=self.config.symbol,
                    side=OrderSide.SELL,
                    price=price,
                    quantity=quantity,
                    status=OrderStatus.PENDING,
                    grid_level=grid_level,
                    grid_index=i
                )
                
                if await self._place_order(order):
                    orders_created += 1
            
            self.logger.info(f"Grid {grid_level.value} initialized with {orders_created} orders")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize grid {grid_level.value}: {e}")
    
    async def _place_order(self, order: OrderInfo) -> bool:
        """下单到交易所"""
        try:
            # 保存到数据库
            self.db.save_order(order)
            
            # 模拟模式下不实际下单
            if self.config.use_testnet and hasattr(self.binance, 'testnet') and self.binance.testnet:
                # 生成模拟订单ID
                order.exchange_order_id = f"TEST_{int(time.time())}_{order.id[-6:]}"
                order.status = OrderStatus.NEW
                self.db.update_order_status(order.id, OrderStatus.NEW, order.exchange_order_id)
                self.order_cache[order.exchange_order_id] = order
                self.total_orders_created += 1
                return True
            
            # 实际下单
            result = await self.binance.futures_create_order(
                symbol=order.symbol,
                side=order.side.value,
                type='LIMIT',
                timeInForce='GTC',
                quantity=str(order.quantity),
                price=str(order.price)
            )
            
            # 更新订单状态
            order.exchange_order_id = str(result['orderId'])
            order.status = OrderStatus.NEW
            self.db.update_order_status(order.id, OrderStatus.NEW, order.exchange_order_id)
            self.order_cache[order.exchange_order_id] = order
            self.total_orders_created += 1
            
            self.logger.info(f"Order placed: {order.side.value} {order.quantity} @ {order.price}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            self.db.update_order_status(order.id, OrderStatus.FAILED)
            return False
    
    async def run_trading_loop(self):
        """运行主交易循环"""
        self.running = True
        self.logger.info("Starting trading loop...")
        
        while self.running:
            try:
                # 更新市场数据
                await self._update_market_data()
                
                # 检查订单状态
                await self._check_order_status()
                
                # 检查风险状态
                await self._check_risk_status()
                
                # 检查网格完整性
                await self._check_grid_integrity()
                
                # 等待下一个检查周期
                await asyncio.sleep(self.config.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(10)  # 出错时等待10秒
    
    async def _update_market_data(self):
        """更新市场数据"""
        try:
            ticker = await self.binance.futures_symbol_ticker(symbol=self.config.symbol)
            new_price = Decimal(ticker['price'])
            
            # 更新价格和市场分析
            self.current_price = new_price
            self.analyzer.add_market_data(new_price)
            
        except Exception as e:
            self.logger.error(f"Failed to update market data: {e}")
    
    async def _check_order_status(self):
        """检查订单状态"""
        try:
            # 获取本地活跃订单
            active_orders = self.db.get_active_orders()
            
            if not active_orders:
                return
            
            # 模拟模式下的订单处理
            if self.config.use_testnet:
                await self._process_simulated_orders(active_orders)
                return
            
            # 获取交易所开放订单
            exchange_orders = await self.binance.futures_get_open_orders(symbol=self.config.symbol)
            exchange_order_ids = {order['orderId'] for order in exchange_orders}
            
            # 检查已成交的订单
            for order in active_orders:
                if order.exchange_order_id and order.exchange_order_id not in exchange_order_ids:
                    await self._process_filled_order(order)
            
        except Exception as e:
            self.logger.error(f"Failed to check order status: {e}")
    
    async def _process_simulated_orders(self, active_orders: List[OrderInfo]):
        """处理模拟订单"""
        for order in active_orders:
            # 简单的模拟成交逻辑
            should_fill = False
            
            if order.side == OrderSide.BUY and self.current_price <= order.price:
                should_fill = True
            elif order.side == OrderSide.SELL and self.current_price >= order.price:
                should_fill = True
            
            if should_fill:
                await self._process_filled_order(order, simulated=True)
    
    async def _process_filled_order(self, order: OrderInfo, simulated: bool = False):
        """处理已成交订单"""
        try:
            filled_price = self.current_price if simulated else order.price
            
            # 计算利润（简化计算）
            if order.side == OrderSide.BUY:
                # 买单成交，期待后续价格上涨
                expected_profit = order.quantity * filled_price * Decimal("0.005")  # 0.5%利润期望
            else:
                # 卖单成交，已实现利润
                expected_profit = order.quantity * filled_price * Decimal("0.005")
            
            # 更新订单状态
            self.db.update_order_status(
                order.id, OrderStatus.FILLED, 
                filled_at=datetime.now(), 
                profit=expected_profit
            )
            
            # 创建交易记录
            trade = TradeRecord(
                trade_id=f"trade_{order.id}_{int(time.time())}",
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                price=filled_price,
                quantity=order.quantity,
                commission=order.quantity * filled_price * Decimal("0.001"),  # 0.1%手续费
                profit=expected_profit,
                grid_level=order.grid_level
            )
            
            self.db.save_trade(trade)
            self.total_orders_filled += 1
            
            # 重建对应位置的订单
            await self._rebuild_order_position(order)
            
            self.logger.info(f"Order filled: {order.side.value} {order.quantity} @ {filled_price}")
            
        except Exception as e:
            self.logger.error(f"Failed to process filled order: {e}")
    
    async def _rebuild_order_position(self, filled_order: OrderInfo):
        """重建订单位置"""
        try:
            # 在相同位置重新下单
            new_order = OrderInfo(
                id=f"{filled_order.grid_level.value}_{filled_order.side.value}_{filled_order.grid_index}_rebuild_{int(time.time())}",
                exchange_order_id=None,
                symbol=filled_order.symbol,
                side=filled_order.side,
                price=filled_order.price,
                quantity=filled_order.quantity,
                status=OrderStatus.PENDING,
                grid_level=filled_order.grid_level,
                grid_index=filled_order.grid_index
            )
            
            await self._place_order(new_order)
            
        except Exception as e:
            self.logger.error(f"Failed to rebuild order position: {e}")
    
    async def _check_risk_status(self):
        """检查风险状态"""
        try:
            # 获取当前性能指标
            metrics = self.db.get_performance_metrics()
            
            # 模拟当前余额（实际应该从交易所获取）
            current_balance = self.config.initial_balance + metrics.total_pnl
            
            # 检查风险限制
            risk_ok, risk_message = self.risk_manager.check_risk_limits(current_balance, metrics.total_pnl)
            
            if not risk_ok:
                self.logger.warning(f"Risk limit exceeded: {risk_message}")
                await self._emergency_stop(risk_message)
                return
            
            # 检查是否需要减仓
            if self.risk_manager.should_reduce_position(metrics.total_pnl):
                self.logger.info("Position reduction recommended")
                # 可以在这里实现减仓逻辑
            
        except Exception as e:
            self.logger.error(f"Failed to check risk status: {e}")
    
    async def _check_grid_integrity(self):
        """检查网格完整性"""
        try:
            for grid_level in GridLevel:
                active_orders = self.db.get_active_orders(grid_level)
                
                # 计算期望的订单数量
                if grid_level == GridLevel.HIGH_FREQ:
                    range_percent = self.config.high_freq_range
                    spacing_percent = self.config.high_freq_spacing
                elif grid_level == GridLevel.MAIN_TREND:
                    range_percent = self.config.main_trend_range
                    spacing_percent = self.config.main_trend_spacing
                else:
                    range_percent = self.config.insurance_range
                    spacing_percent = self.config.insurance_spacing
                
                # 简单估算期望订单数
                expected_orders = int(range_percent / spacing_percent) * 2  # 买单+卖单
                actual_orders = len(active_orders)
                
                integrity = (actual_orders / expected_orders) * 100 if expected_orders > 0 else 100
                
                # 如果完整性低于60%，重建网格
                if integrity < 60:
                    last_rebuild = self.last_grid_rebuild.get(grid_level)
                    if not last_rebuild or (datetime.now() - last_rebuild).seconds > 300:  # 5分钟间隔
                        self.logger.warning(f"Grid {grid_level.value} integrity low: {integrity:.1f}%")
                        await self._rebuild_grid(grid_level)
            
        except Exception as e:
            self.logger.error(f"Failed to check grid integrity: {e}")
    
    async def _rebuild_grid(self, grid_level: GridLevel):
        """重建网格"""
        try:
            self.logger.info(f"Rebuilding grid: {grid_level.value}")
            
            # 取消现有订单
            active_orders = self.db.get_active_orders(grid_level)
            for order in active_orders:
                if order.exchange_order_id and not self.config.use_testnet:
                    try:
                        await self.binance.futures_cancel_order(
                            symbol=order.symbol,
                            orderId=order.exchange_order_id
                        )
                    except:
                        pass  # 忽略取消失败
                
                self.db.update_order_status(order.id, OrderStatus.CANCELED)
            
            # 重新计算并创建网格
            grids = self.calculator.calculate_grid_levels(self.current_price, self.config)
            await self._initialize_single_grid(grid_level, grids[grid_level])
            
            self.last_grid_rebuild[grid_level] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Failed to rebuild grid {grid_level.value}: {e}")
    
    async def _emergency_stop(self, reason: str):
        """紧急停止"""
        self.logger.critical(f"Emergency stop triggered: {reason}")
        self.running = False
        
        # 记录紧急停止事件
        self.db.log_event("CRITICAL", "GridEngine", "Emergency stop triggered", {
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        # 可以在这里添加更多紧急处理逻辑，如取消所有订单等
    
    def stop(self):
        """停止引擎"""
        self.logger.info("Stopping Grid Trading Engine...")
        self.running = False
    
    def get_status(self) -> SystemStatus:
        """获取系统状态"""
        active_orders = self.db.get_active_orders()
        
        # 计算网格完整性
        grid_integrity = {}
        for grid_level in GridLevel:
            level_orders = [o for o in active_orders if o.grid_level == grid_level]
            # 简化的完整性计算
            expected = 20  # 预期订单数
            actual = len(level_orders)
            integrity = (actual / expected) * 100 if expected > 0 else 100
            grid_integrity[grid_level] = Decimal(str(min(integrity, 100)))
        
        return SystemStatus(
            running=self.running,
            current_price=self.current_price,
            active_orders=len(active_orders),
            grid_integrity=grid_integrity,
            last_update=datetime.now(),
            uptime_seconds=int(time.time() - self.start_time)
        )