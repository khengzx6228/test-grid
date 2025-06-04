# capital_manager.py - 动态资金管理模块
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from data_models import GridLevel, OrderInfo, OrderStatus, TradingConfig
from database_manager import DatabaseManager

class DynamicCapitalManager:
    """动态资金管理器 - 解决保险层资金冻结问题"""
    
    def __init__(self, config: TradingConfig, binance_client, db_manager: DatabaseManager):
        self.config = config
        self.binance = binance_client
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 资金管理参数
        self.max_insurance_ratio = Decimal("0.40")  # 保险层最大占用40%资金
        self.capital_rebalance_hours = 24  # 24小时重新评估一次
        self.frozen_capital_threshold = Decimal("0.60")  # 冻结资金超过60%时触发回收
        
        # 动态调整参数
        self.volatility_window = 168  # 7天（168小时）波动率计算窗口
        self.trend_strength_threshold = Decimal("0.15")  # 15%趋势强度阈值
        
        # 资金使用统计
        self.capital_allocation = {
            GridLevel.HIGH_FREQ: Decimal("0"),
            GridLevel.MAIN_TREND: Decimal("0"),
            GridLevel.INSURANCE: Decimal("0")
        }
        
        self.last_rebalance_time = datetime.now()
    
    async def start_monitoring(self):
        """启动资金管理监控"""
        self.logger.info("Starting dynamic capital management...")
        
        while True:
            try:
                await self._analyze_capital_usage()
                await self._rebalance_capital_if_needed()
                await self._manage_insurance_layer()
                
                # 每小时检查一次
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Capital management error: {e}")
                await asyncio.sleep(600)  # 出错时10分钟后重试
    
    async def _analyze_capital_usage(self):
        """分析资金使用情况"""
        try:
            # 获取账户信息
            account_info = await self.binance.futures_account()
            total_balance = Decimal(account_info['totalWalletBalance'])
            available_balance = Decimal(account_info['availableBalance'])
            
            # 计算各层级资金占用
            await self._calculate_grid_capital_usage(total_balance)
            
            # 计算冻结资金比例
            frozen_capital = total_balance - available_balance
            frozen_ratio = frozen_capital / total_balance if total_balance > 0 else Decimal("0")
            
            # 记录资金使用状态
            capital_status = {
                "total_balance": float(total_balance),
                "available_balance": float(available_balance),
                "frozen_capital": float(frozen_capital),
                "frozen_ratio": float(frozen_ratio),
                "grid_allocation": {level.value: float(amount) for level, amount in self.capital_allocation.items()}
            }
            
            await self.db.log_event("INFO", "CapitalManager", "Capital usage analysis", capital_status)
            
            # 检查是否需要资金回收
            if frozen_ratio > self.frozen_capital_threshold:
                await self._trigger_capital_recovery(frozen_ratio)
            
        except Exception as e:
            self.logger.error(f"Failed to analyze capital usage: {e}")
    
    async def _calculate_grid_capital_usage(self, total_balance: Decimal):
        """计算各网格层级的资金占用"""
        try:
            for grid_level in GridLevel:
                active_orders = self.db.get_active_orders(grid_level)
                
                level_capital = Decimal("0")
                for order in active_orders:
                    if order.status in [OrderStatus.NEW, OrderStatus.PENDING]:
                        order_value = order.price * order.quantity
                        level_capital += order_value
                
                self.capital_allocation[grid_level] = level_capital
                
                # 计算占用比例
                usage_ratio = level_capital / total_balance if total_balance > 0 else Decimal("0")
                
                self.logger.debug(f"Grid {grid_level.value} capital usage: {level_capital:.2f} USDT ({usage_ratio:.1%})")
        
        except Exception as e:
            self.logger.error(f"Failed to calculate grid capital usage: {e}")
    
    async def _trigger_capital_recovery(self, frozen_ratio: Decimal):
        """触发资金回收"""
        self.logger.warning(f"High frozen capital ratio detected: {frozen_ratio:.1%}")
        
        try:
            # 优先回收保险层资金
            insurance_recovery = await self._recover_insurance_capital()
            
            # 如果保险层回收不足，考虑其他层级
            if frozen_ratio > Decimal("0.80"):  # 超过80%时更激进回收
                main_trend_recovery = await self._recover_main_trend_capital()
                
            await self.db.log_event("WARNING", "CapitalManager", 
                                   f"Capital recovery triggered due to high frozen ratio: {frozen_ratio:.1%}")
        
        except Exception as e:
            self.logger.error(f"Capital recovery failed: {e}")
    
    async def _recover_insurance_capital(self) -> Decimal:
        """回收保险层资金"""
        try:
            insurance_orders = self.db.get_active_orders(GridLevel.INSURANCE)
            
            # 按距离当前价格远近排序，优先取消最远的订单
            current_price = await self._get_current_price()
            
            # 计算每个订单与当前价格的距离
            orders_with_distance = []
            for order in insurance_orders:
                distance = abs(order.price - current_price) / current_price
                orders_with_distance.append((order, distance))
            
            # 按距离排序，距离最远的优先取消
            orders_with_distance.sort(key=lambda x: x[1], reverse=True)
            
            recovered_capital = Decimal("0")
            cancel_count = 0
            
            # 取消最远的50%保险层订单
            target_cancel_count = len(orders_with_distance) // 2
            
            for order, distance in orders_with_distance[:target_cancel_count]:
                if await self._cancel_order_safely(order):
                    recovered_capital += order.price * order.quantity
                    cancel_count += 1
            
            self.logger.info(f"Recovered {recovered_capital:.2f} USDT by canceling {cancel_count} insurance orders")
            return recovered_capital
        
        except Exception as e:
            self.logger.error(f"Failed to recover insurance capital: {e}")
            return Decimal("0")
    
    async def _recover_main_trend_capital(self) -> Decimal:
        """回收主趋势层资金（更保守）"""
        try:
            main_trend_orders = self.db.get_active_orders(GridLevel.MAIN_TREND)
            current_price = await self._get_current_price()
            
            # 只取消距离当前价格最远的25%订单
            orders_with_distance = []
            for order in main_trend_orders:
                distance = abs(order.price - current_price) / current_price
                orders_with_distance.append((order, distance))
            
            orders_with_distance.sort(key=lambda x: x[1], reverse=True)
            
            recovered_capital = Decimal("0")
            cancel_count = 0
            
            # 只取消最远的25%订单
            target_cancel_count = len(orders_with_distance) // 4
            
            for order, distance in orders_with_distance[:target_cancel_count]:
                if await self._cancel_order_safely(order):
                    recovered_capital += order.price * order.quantity
                    cancel_count += 1
            
            self.logger.info(f"Recovered {recovered_capital:.2f} USDT by canceling {cancel_count} main trend orders")
            return recovered_capital
        
        except Exception as e:
            self.logger.error(f"Failed to recover main trend capital: {e}")
            return Decimal("0")
    
    async def _cancel_order_safely(self, order: OrderInfo) -> bool:
        """安全取消订单"""
        try:
            if order.exchange_order_id:
                await self.binance.futures_cancel_order(
                    symbol=order.symbol,
                    orderId=order.exchange_order_id
                )
                
                # 更新本地状态
                self.db.update_order_status(order.id, OrderStatus.CANCELED)
                return True
        
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order.id}: {e}")
            return False
    
    async def _rebalance_capital_if_needed(self):
        """根据需要重新平衡资金"""
        current_time = datetime.now()
        time_since_rebalance = (current_time - self.last_rebalance_time).total_seconds() / 3600
        
        if time_since_rebalance >= self.capital_rebalance_hours:
            await self._perform_capital_rebalancing()
            self.last_rebalance_time = current_time
    
    async def _perform_capital_rebalancing(self):
        """执行资金重新平衡"""
        try:
            self.logger.info("Starting capital rebalancing...")
            
            # 分析市场状态
            market_analysis = await self._analyze_market_conditions()
            
            # 根据市场状态调整资金分配
            new_allocation = await self._calculate_optimal_allocation(market_analysis)
            
            # 执行资金重新分配
            await self._execute_rebalancing(new_allocation)
            
            self.logger.info("Capital rebalancing completed")
        
        except Exception as e:
            self.logger.error(f"Capital rebalancing failed: {e}")
    
    async def _analyze_market_conditions(self) -> Dict[str, any]:
        """分析市场状况"""
        try:
            # 获取历史价格数据
            klines = await self.binance.futures_klines(
                symbol=self.config.symbol,
                interval='1h',
                limit=self.volatility_window
            )
            
            prices = [Decimal(kline[4]) for kline in klines]  # 收盘价
            
            # 计算波动率
            volatility = self._calculate_volatility(prices)
            
            # 计算趋势强度
            trend_strength = self._calculate_trend_strength(prices)
            
            # 判断市场状态
            market_state = self._determine_market_state(volatility, trend_strength)
            
            return {
                "volatility": float(volatility),
                "trend_strength": float(trend_strength),
                "market_state": market_state,
                "current_price": float(prices[-1]),
                "price_change_7d": float((prices[-1] - prices[0]) / prices[0])
            }
        
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
            return {
                "volatility": 0.02,
                "trend_strength": 0.0,
                "market_state": "sideways",
                "current_price": 0,
                "price_change_7d": 0
            }
    
    def _calculate_volatility(self, prices: List[Decimal]) -> Decimal:
        """计算价格波动率"""
        if len(prices) < 2:
            return Decimal("0.02")  # 默认2%波动率
        
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        # 计算标准差
        if not returns:
            return Decimal("0.02")
        
        mean_return = sum(returns) / len(returns)
        variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
        volatility = variance ** Decimal("0.5")
        
        return volatility
    
    def _calculate_trend_strength(self, prices: List[Decimal]) -> Decimal:
        """计算趋势强度"""
        if len(prices) < 20:
            return Decimal("0")
        
        # 使用简单移动平均线计算趋势
        short_ma = sum(prices[-20:]) / 20
        long_ma = sum(prices[-50:]) / 50 if len(prices) >= 50 else sum(prices) / len(prices)
        
        trend_strength = abs(short_ma - long_ma) / long_ma if long_ma > 0 else Decimal("0")
        return min(trend_strength, Decimal("1"))
    
    def _determine_market_state(self, volatility: Decimal, trend_strength: Decimal) -> str:
        """判断市场状态"""
        if volatility > Decimal("0.05"):
            return "high_volatility"
        elif trend_strength > self.trend_strength_threshold:
            return "trending"
        else:
            return "sideways"
    
    async def _calculate_optimal_allocation(self, market_analysis: Dict[str, any]) -> Dict[GridLevel, Decimal]:
        """计算最优资金分配"""
        market_state = market_analysis["market_state"]
        volatility = Decimal(str(market_analysis["volatility"]))
        
        # 获取总可用资金
        account_info = await self.binance.futures_account()
        total_balance = Decimal(account_info['totalWalletBalance'])
        
        # 根据市场状态调整分配比例
        if market_state == "sideways":
            # 震荡市场：平衡分配，重点高频
            allocation_ratios = {
                GridLevel.HIGH_FREQ: Decimal("0.40"),
                GridLevel.MAIN_TREND: Decimal("0.35"),
                GridLevel.INSURANCE: Decimal("0.25")
            }
        elif market_state == "trending":
            # 趋势市场：重点主趋势层
            allocation_ratios = {
                GridLevel.HIGH_FREQ: Decimal("0.25"),
                GridLevel.MAIN_TREND: Decimal("0.50"),
                GridLevel.INSURANCE: Decimal("0.25")
            }
        else:  # high_volatility
            # 高波动：保守策略，增加保险层
            allocation_ratios = {
                GridLevel.HIGH_FREQ: Decimal("0.20"),
                GridLevel.MAIN_TREND: Decimal("0.40"),
                GridLevel.INSURANCE: Decimal("0.40")
            }
        
        # 应用保险层资金限制
        if allocation_ratios[GridLevel.INSURANCE] > self.max_insurance_ratio:
            excess = allocation_ratios[GridLevel.INSURANCE] - self.max_insurance_ratio
            allocation_ratios[GridLevel.INSURANCE] = self.max_insurance_ratio
            allocation_ratios[GridLevel.MAIN_TREND] += excess
        
        # 计算具体金额
        target_allocation = {}
        for level, ratio in allocation_ratios.items():
            target_allocation[level] = total_balance * ratio
        
        return target_allocation
    
    async def _execute_rebalancing(self, target_allocation: Dict[GridLevel, Decimal]):
        """执行资金重新分配"""
        try:
            for grid_level, target_amount in target_allocation.items():
                current_amount = self.capital_allocation[grid_level]
                
                if abs(target_amount - current_amount) > Decimal("100"):  # 差异超过100 USDT才调整
                    await self._adjust_grid_capital(grid_level, target_amount, current_amount)
        
        except Exception as e:
            self.logger.error(f"Failed to execute rebalancing: {e}")
    
    async def _adjust_grid_capital(self, grid_level: GridLevel, target_amount: Decimal, current_amount: Decimal):
        """调整特定网格层级的资金"""
        try:
            if target_amount > current_amount:
                # 需要增加资金：创建更多订单
                additional_capital = target_amount - current_amount
                await self._add_grid_orders(grid_level, additional_capital)
                
            else:
                # 需要减少资金：取消部分订单
                excess_capital = current_amount - target_amount
                await self._remove_grid_orders(grid_level, excess_capital)
            
            self.logger.info(f"Adjusted {grid_level.value} capital from {current_amount:.2f} to {target_amount:.2f}")
        
        except Exception as e:
            self.logger.error(f"Failed to adjust grid capital for {grid_level.value}: {e}")
    
    async def _add_grid_orders(self, grid_level: GridLevel, additional_capital: Decimal):
        """为网格层级添加订单"""
        # 这里需要与GridTradingEngine集成
        # 简化实现：记录需要添加的资金量
        await self.db.log_event("INFO", "CapitalManager", 
                               f"Request to add {additional_capital:.2f} USDT to {grid_level.value}")
    
    async def _remove_grid_orders(self, grid_level: GridLevel, excess_capital: Decimal):
        """移除网格层级的部分订单"""
        try:
            orders = self.db.get_active_orders(grid_level)
            current_price = await self._get_current_price()
            
            # 按距离当前价格排序，优先移除最远的订单
            orders_with_distance = []
            for order in orders:
                distance = abs(order.price - current_price) / current_price
                order_value = order.price * order.quantity
                orders_with_distance.append((order, distance, order_value))
            
            orders_with_distance.sort(key=lambda x: x[1], reverse=True)
            
            removed_capital = Decimal("0")
            for order, distance, order_value in orders_with_distance:
                if removed_capital >= excess_capital:
                    break
                
                if await self._cancel_order_safely(order):
                    removed_capital += order_value
            
            self.logger.info(f"Removed {removed_capital:.2f} USDT from {grid_level.value}")
        
        except Exception as e:
            self.logger.error(f"Failed to remove grid orders: {e}")
    
    async def _get_current_price(self) -> Decimal:
        """获取当前价格"""
        try:
            ticker = await self.binance.futures_symbol_ticker(symbol=self.config.symbol)
            return Decimal(ticker['price'])
        except:
            return Decimal("50000")  # 默认价格
    
    async def _manage_insurance_layer(self):
        """管理保险层特殊逻辑"""
        try:
            # 检查保险层订单是否长期未成交
            insurance_orders = self.db.get_active_orders(GridLevel.INSURANCE)
            current_time = datetime.now()
            
            stale_threshold = timedelta(days=7)  # 7天未成交视为过时
            stale_orders = []
            
            for order in insurance_orders:
                if current_time - order.created_at > stale_threshold:
                    stale_orders.append(order)
            
            if stale_orders:
                await self._handle_stale_insurance_orders(stale_orders)
        
        except Exception as e:
            self.logger.error(f"Insurance layer management failed: {e}")
    
    async def _handle_stale_insurance_orders(self, stale_orders: List[OrderInfo]):
        """处理过时的保险层订单"""
        try:
            current_price = await self._get_current_price()
            
            for order in stale_orders:
                price_diff_percent = abs(order.price - current_price) / current_price
                
                # 如果订单价格与当前价格差距超过30%，考虑取消
                if price_diff_percent > Decimal("0.30"):
                    await self._cancel_order_safely(order)
                    
                    # 在更接近当前价格的位置重新下单
                    await self._recreate_insurance_order(order, current_price)
            
            self.logger.info(f"Handled {len(stale_orders)} stale insurance orders")
        
        except Exception as e:
            self.logger.error(f"Failed to handle stale insurance orders: {e}")
    
    async def _recreate_insurance_order(self, original_order: OrderInfo, current_price: Decimal):
        """在新位置重新创建保险层订单"""
        try:
            # 计算新的订单价格（更接近当前价格）
            if original_order.side.value == "BUY":
                # 买单：在当前价格下方20-30%的位置
                new_price = current_price * Decimal("0.75")  # 25%下方
            else:
                # 卖单：在当前价格上方20-30%的位置
                new_price = current_price * Decimal("1.25")  # 25%上方
            
            # 记录重新创建的需求（实际创建需要与GridTradingEngine集成）
            await self.db.log_event("INFO", "CapitalManager",
                                   f"Request to recreate insurance order at new price: {new_price:.2f}",
                                   {
                                       "original_order_id": original_order.id,
                                       "original_price": float(original_order.price),
                                       "new_price": float(new_price),
                                       "current_price": float(current_price)
                                   })
        
        except Exception as e:
            self.logger.error(f"Failed to recreate insurance order: {e}")
    
    def get_capital_status(self) -> Dict[str, any]:
        """获取资金管理状态"""
        return {
            "capital_allocation": {level.value: float(amount) for level, amount in self.capital_allocation.items()},
            "max_insurance_ratio": float(self.max_insurance_ratio),
            "last_rebalance_time": self.last_rebalance_time.isoformat(),
            "frozen_threshold": float(self.frozen_capital_threshold)
        }