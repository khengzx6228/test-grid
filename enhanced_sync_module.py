# sync_monitor.py - 实时同步与异常检测模块
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from decimal import Decimal
from data_models import OrderInfo, OrderStatus, OrderSide
from database_manager import DatabaseManager

class OrderSyncMonitor:
    """订单同步监控器 - 解决系统状态与交易所不一致问题"""
    
    def __init__(self, binance_client, db_manager: DatabaseManager):
        self.binance = binance_client
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 同步状态追踪
        self.last_sync_time = datetime.now()
        self.sync_interval = 30  # 30秒同步一次
        self.inconsistency_count = 0
        self.max_inconsistency = 5  # 最大允许不一致次数
        
        # 异常检测阈值
        self.order_timeout_minutes = 60  # 订单超时时间
        self.price_deviation_percent = Decimal("0.05")  # 5% 价格偏差告警
        
    async def start_monitoring(self):
        """启动持续监控"""
        self.logger.info("Starting order sync monitoring...")
        
        while True:
            try:
                await self._sync_order_states()
                await self._detect_anomalies()
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                self.logger.error(f"Sync monitoring error: {e}")
                await asyncio.sleep(10)
    
    async def _sync_order_states(self):
        """同步订单状态"""
        try:
            # 获取本地活跃订单
            local_orders = await self._get_local_active_orders()
            local_order_ids = {order.exchange_order_id for order in local_orders if order.exchange_order_id}
            
            # 获取交易所开放订单
            exchange_orders = await self.binance.futures_get_open_orders()
            exchange_order_ids = {str(order['orderId']) for order in exchange_orders}
            
            # 检测状态不一致
            inconsistencies = await self._detect_state_inconsistencies(
                local_orders, local_order_ids, exchange_order_ids
            )
            
            if inconsistencies:
                await self._handle_inconsistencies(inconsistencies)
            
            # 更新同步时间
            self.last_sync_time = datetime.now()
            self.logger.debug(f"Sync completed. Local: {len(local_order_ids)}, Exchange: {len(exchange_order_ids)}")
            
        except Exception as e:
            self.logger.error(f"Failed to sync order states: {e}")
            self.inconsistency_count += 1
    
    async def _get_local_active_orders(self) -> List[OrderInfo]:
        """获取本地活跃订单"""
        return self.db.get_active_orders()
    
    async def _detect_state_inconsistencies(self, local_orders: List[OrderInfo], 
                                          local_ids: Set[str], 
                                          exchange_ids: Set[str]) -> Dict[str, List]:
        """检测状态不一致"""
        inconsistencies = {
            'local_missing': [],      # 本地有但交易所没有（可能已成交或被撤销）
            'exchange_extra': [],     # 交易所有但本地没有（可能是手动下单）
            'status_mismatch': [],    # 状态不匹配
            'timeout_orders': []      # 超时订单
        }
        
        # 检查本地订单在交易所的状态
        for order in local_orders:
            if not order.exchange_order_id:
                continue
                
            # 检查是否在交易所存在
            if order.exchange_order_id not in exchange_ids:
                inconsistencies['local_missing'].append(order)
        
        # 检查交易所额外订单
        untracked_ids = exchange_ids - local_ids
        if untracked_ids:
            inconsistencies['exchange_extra'] = list(untracked_ids)
        
        # 检查超时订单
        timeout_threshold = datetime.now() - timedelta(minutes=self.order_timeout_minutes)
        for order in local_orders:
            if order.created_at < timeout_threshold and order.status == OrderStatus.PENDING:
                inconsistencies['timeout_orders'].append(order)
        
        return inconsistencies
    
    async def _handle_inconsistencies(self, inconsistencies: Dict[str, List]):
        """处理状态不一致"""
        try:
            # 处理本地有但交易所没有的订单
            for order in inconsistencies['local_missing']:
                await self._handle_missing_order(order)
            
            # 处理交易所额外订单
            for order_id in inconsistencies['exchange_extra']:
                await self._handle_extra_order(order_id)
            
            # 处理超时订单
            for order in inconsistencies['timeout_orders']:
                await self._handle_timeout_order(order)
            
            # 记录不一致事件
            if any(inconsistencies.values()):
                await self.db.log_event("WARNING", "SyncMonitor", 
                                       "Order state inconsistencies detected", 
                                       inconsistencies)
                
        except Exception as e:
            self.logger.error(f"Failed to handle inconsistencies: {e}")
    
    async def _handle_missing_order(self, order: OrderInfo):
        """处理缺失订单（可能已成交）"""
        try:
            # 查询订单详细信息
            order_detail = await self.binance.futures_get_order(
                symbol=order.symbol,
                orderId=order.exchange_order_id
            )
            
            if order_detail['status'] == 'FILLED':
                # 订单已成交，更新本地状态
                filled_quantity = Decimal(order_detail['executedQty'])
                avg_price = Decimal(order_detail['avgPrice'])
                
                await self.db.update_order_status(
                    order.id, OrderStatus.FILLED,
                    filled_at=datetime.now()
                )
                
                # 创建交易记录
                trade_id = f"sync_trade_{order.id}_{int(datetime.now().timestamp())}"
                await self._create_trade_record(trade_id, order, filled_quantity, avg_price)
                
                self.logger.info(f"Synced filled order: {order.id}")
                
            elif order_detail['status'] in ['CANCELED', 'EXPIRED']:
                # 订单已取消或过期
                await self.db.update_order_status(order.id, OrderStatus.CANCELED)
                self.logger.info(f"Synced canceled order: {order.id}")
                
        except Exception as e:
            self.logger.error(f"Failed to handle missing order {order.id}: {e}")
    
    async def _handle_extra_order(self, order_id: str):
        """处理交易所额外订单（可能是手动下单）"""
        try:
            order_detail = await self.binance.futures_get_order(orderId=order_id)
            
            # 记录发现的额外订单
            await self.db.log_event("WARNING", "SyncMonitor", 
                                   f"Found untracked order on exchange: {order_id}",
                                   {"order_detail": order_detail})
            
            # 可选：自动导入到系统中
            # await self._import_external_order(order_detail)
            
        except Exception as e:
            self.logger.error(f"Failed to handle extra order {order_id}: {e}")
    
    async def _handle_timeout_order(self, order: OrderInfo):
        """处理超时订单"""
        try:
            # 检查订单是否仍然有效
            if order.exchange_order_id:
                try:
                    order_detail = await self.binance.futures_get_order(
                        symbol=order.symbol,
                        orderId=order.exchange_order_id
                    )
                    
                    if order_detail['status'] == 'NEW':
                        # 订单仍然有效但超时，可能需要重新评估
                        await self.db.log_event("WARNING", "SyncMonitor",
                                               f"Order timeout but still active: {order.id}")
                    
                except:
                    # 订单查询失败，标记为失败
                    await self.db.update_order_status(order.id, OrderStatus.FAILED)
            
        except Exception as e:
            self.logger.error(f"Failed to handle timeout order {order.id}: {e}")
    
    async def _create_trade_record(self, trade_id: str, order: OrderInfo, 
                                 quantity: Decimal, price: Decimal):
        """创建交易记录"""
        try:
            from data_models import TradeRecord
            
            # 计算手续费和利润
            commission = quantity * price * Decimal("0.001")  # 0.1% 手续费
            profit = self._calculate_trade_profit(order, price)
            
            trade = TradeRecord(
                trade_id=trade_id,
                order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                price=price,
                quantity=quantity,
                commission=commission,
                profit=profit,
                grid_level=order.grid_level
            )
            
            await self.db.save_trade(trade)
            
        except Exception as e:
            self.logger.error(f"Failed to create trade record: {e}")
    
    def _calculate_trade_profit(self, order: OrderInfo, filled_price: Decimal) -> Decimal:
        """计算交易利润"""
        # 简化的利润计算
        if order.side == OrderSide.BUY:
            # 买单成交，期望价格上涨
            expected_sell_price = filled_price * Decimal("1.005")  # 0.5% 利润预期
            return (expected_sell_price - filled_price) * order.quantity
        else:
            # 卖单成交，已实现部分利润
            return filled_price * order.quantity * Decimal("0.005")  # 0.5% 利润
    
    async def _detect_anomalies(self):
        """检测交易异常"""
        try:
            # 检测价格异常
            await self._detect_price_anomalies()
            
            # 检测订单执行异常
            await self._detect_execution_anomalies()
            
            # 检测资金异常
            await self._detect_balance_anomalies()
            
        except Exception as e:
            self.logger.error(f"Anomaly detection failed: {e}")
    
    async def _detect_price_anomalies(self):
        """检测价格异常"""
        try:
            # 获取当前价格
            ticker = await self.binance.futures_symbol_ticker(symbol="BTCUSDT")
            current_price = Decimal(ticker['price'])
            
            # 获取本地活跃订单
            active_orders = await self._get_local_active_orders()
            
            for order in active_orders:
                price_diff_percent = abs(order.price - current_price) / current_price
                
                if price_diff_percent > self.price_deviation_percent:
                    await self.db.log_event("WARNING", "SyncMonitor",
                                           f"Large price deviation detected for order {order.id}",
                                           {
                                               "order_price": float(order.price),
                                               "current_price": float(current_price),
                                               "deviation_percent": float(price_diff_percent * 100)
                                           })
            
        except Exception as e:
            self.logger.error(f"Price anomaly detection failed: {e}")
    
    async def _detect_execution_anomalies(self):
        """检测执行异常"""
        try:
            # 检查最近1小时内的订单执行情况
            recent_time = datetime.now() - timedelta(hours=1)
            
            # 统计订单成功率
            total_orders = 0
            failed_orders = 0
            
            local_orders = await self._get_local_active_orders()
            for order in local_orders:
                if order.created_at > recent_time:
                    total_orders += 1
                    if order.status == OrderStatus.FAILED:
                        failed_orders += 1
            
            if total_orders > 0:
                failure_rate = failed_orders / total_orders
                if failure_rate > 0.1:  # 失败率 > 10%
                    await self.db.log_event("WARNING", "SyncMonitor",
                                           f"High order failure rate: {failure_rate:.2%}",
                                           {"total_orders": total_orders, "failed_orders": failed_orders})
            
        except Exception as e:
            self.logger.error(f"Execution anomaly detection failed: {e}")
    
    async def _detect_balance_anomalies(self):
        """检测资金异常"""
        try:
            # 获取账户信息
            account_info = await self.binance.futures_account()
            current_balance = Decimal(account_info['totalWalletBalance'])
            
            # 简单的资金变化检测
            # 这里可以扩展为更复杂的资金流分析
            if current_balance <= Decimal("0"):
                await self.db.log_event("CRITICAL", "SyncMonitor",
                                       "Account balance is zero or negative",
                                       {"balance": float(current_balance)})
            
        except Exception as e:
            self.logger.error(f"Balance anomaly detection failed: {e}")
    
    def get_sync_status(self) -> Dict[str, any]:
        """获取同步状态"""
        return {
            "last_sync_time": self.last_sync_time.isoformat(),
            "sync_interval": self.sync_interval,
            "inconsistency_count": self.inconsistency_count,
            "status": "healthy" if self.inconsistency_count < self.max_inconsistency else "warning"
        }