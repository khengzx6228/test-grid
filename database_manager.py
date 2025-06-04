# database_manager.py - SQLite数据库管理器
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, date
from decimal import Decimal
from data_models import *

class DatabaseManager:
    """轻量级SQLite数据库管理器"""
    
    def __init__(self, db_path: str = "grid_trading.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._ensure_database()
    
    def _ensure_database(self):
        """确保数据库存在并创建表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- 订单表
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    exchange_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    status TEXT NOT NULL,
                    grid_level TEXT NOT NULL,
                    grid_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    filled_at TEXT,
                    profit REAL DEFAULT 0
                );
                
                -- 交易记录表
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    commission REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    grid_level TEXT NOT NULL,
                    executed_at TEXT NOT NULL
                );
                
                -- 性能指标表
                CREATE TABLE IF NOT EXISTS performance (
                    date TEXT PRIMARY KEY,
                    total_pnl REAL DEFAULT 0,
                    realized_pnl REAL DEFAULT 0,
                    unrealized_pnl REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    current_drawdown REAL DEFAULT 0,
                    daily_return REAL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                
                -- 系统日志表
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT
                );
                
                -- 网格状态表
                CREATE TABLE IF NOT EXISTS grid_states (
                    grid_level TEXT PRIMARY KEY,
                    center_price REAL NOT NULL,
                    active_orders INTEGER DEFAULT 0,
                    integrity_percentage REAL DEFAULT 0,
                    last_rebuild TEXT,
                    updated_at TEXT NOT NULL
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_grid_level ON orders(grid_level);
                CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp);
            """)
    
    def save_order(self, order: OrderInfo) -> bool:
        """保存订单"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO orders 
                    (id, exchange_order_id, symbol, side, price, quantity, status, 
                     grid_level, grid_index, created_at, filled_at, profit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.id, order.exchange_order_id, order.symbol, order.side.value,
                    float(order.price), float(order.quantity), order.status.value,
                    order.grid_level.value, order.grid_index, order.created_at.isoformat(),
                    order.filled_at.isoformat() if order.filled_at else None,
                    float(order.profit)
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save order: {e}")
            return False
    
    def get_active_orders(self, grid_level: Optional[GridLevel] = None) -> List[OrderInfo]:
        """获取活跃订单"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                query = "SELECT * FROM orders WHERE status IN ('NEW', 'PENDING')"
                params = []
                
                if grid_level:
                    query += " AND grid_level = ?"
                    params.append(grid_level.value)
                
                query += " ORDER BY created_at DESC"
                
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
                orders = []
                for row in rows:
                    order = OrderInfo(
                        id=row['id'],
                        exchange_order_id=row['exchange_order_id'],
                        symbol=row['symbol'],
                        side=OrderSide(row['side']),
                        price=Decimal(str(row['price'])),
                        quantity=Decimal(str(row['quantity'])),
                        status=OrderStatus(row['status']),
                        grid_level=GridLevel(row['grid_level']),
                        grid_index=row['grid_index'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        filled_at=datetime.fromisoformat(row['filled_at']) if row['filled_at'] else None,
                        profit=Decimal(str(row['profit']))
                    )
                    orders.append(order)
                
                return orders
        except Exception as e:
            self.logger.error(f"Failed to get active orders: {e}")
            return []
    
    def update_order_status(self, order_id: str, status: OrderStatus, 
                           exchange_order_id: Optional[str] = None,
                           filled_at: Optional[datetime] = None,
                           profit: Optional[Decimal] = None) -> bool:
        """更新订单状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates = ["status = ?"]
                params = [status.value]
                
                if exchange_order_id:
                    updates.append("exchange_order_id = ?")
                    params.append(exchange_order_id)
                
                if filled_at:
                    updates.append("filled_at = ?")
                    params.append(filled_at.isoformat())
                
                if profit is not None:
                    updates.append("profit = ?")
                    params.append(float(profit))
                
                params.append(order_id)
                
                query = f"UPDATE orders SET {', '.join(updates)} WHERE id = ?"
                conn.execute(query, params)
                
            return True
        except Exception as e:
            self.logger.error(f"Failed to update order status: {e}")
            return False
    
    def save_trade(self, trade: TradeRecord) -> bool:
        """保存交易记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trades
                    (trade_id, order_id, symbol, side, price, quantity, 
                     commission, profit, grid_level, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id, trade.order_id, trade.symbol, trade.side.value,
                    float(trade.price), float(trade.quantity), float(trade.commission),
                    float(trade.profit), trade.grid_level.value, trade.executed_at.isoformat()
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save trade: {e}")
            return False
    
    def get_trades(self, days: int = 7) -> List[TradeRecord]:
        """获取交易记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
                
                cursor = conn.execute("""
                    SELECT * FROM trades 
                    WHERE executed_at >= ? 
                    ORDER BY executed_at DESC
                """, (cutoff_date.isoformat(),))
                
                trades = []
                for row in cursor.fetchall():
                    trade = TradeRecord(
                        trade_id=row['trade_id'],
                        order_id=row['order_id'],
                        symbol=row['symbol'],
                        side=OrderSide(row['side']),
                        price=Decimal(str(row['price'])),
                        quantity=Decimal(str(row['quantity'])),
                        commission=Decimal(str(row['commission'])),
                        profit=Decimal(str(row['profit'])),
                        grid_level=GridLevel(row['grid_level']),
                        executed_at=datetime.fromisoformat(row['executed_at'])
                    )
                    trades.append(trade)
                
                return trades
        except Exception as e:
            self.logger.error(f"Failed to get trades: {e}")
            return []
    
    def get_performance_metrics(self, target_date: Optional[date] = None) -> PerformanceMetrics:
        """获取性能指标"""
        if target_date is None:
            target_date = date.today()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 尝试从缓存获取
                cursor = conn.execute(
                    "SELECT * FROM performance WHERE date = ?",
                    (target_date.isoformat(),)
                )
                row = cursor.fetchone()
                
                if row:
                    return PerformanceMetrics(
                        total_pnl=Decimal(str(row['total_pnl'])),
                        realized_pnl=Decimal(str(row['realized_pnl'])),
                        unrealized_pnl=Decimal(str(row['unrealized_pnl'])),
                        total_trades=row['total_trades'],
                        winning_trades=row['winning_trades'],
                        win_rate=Decimal(str(row['win_rate'])),
                        max_drawdown=Decimal(str(row['max_drawdown'])),
                        current_drawdown=Decimal(str(row['current_drawdown'])),
                        daily_return=Decimal(str(row['daily_return'])),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                
                # 实时计算
                return self._calculate_performance_metrics(target_date)
                
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return PerformanceMetrics()
    
    def _calculate_performance_metrics(self, target_date: date) -> PerformanceMetrics:
        """实时计算性能指标"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # 获取当日交易数据
                start_date = target_date.strftime('%Y-%m-%d')
                end_date = (target_date.replace(day=target_date.day + 1)).strftime('%Y-%m-%d')
                
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(profit) as realized_pnl,
                        SUM(commission) as total_commission
                    FROM trades
                    WHERE executed_at >= ? AND executed_at < ?
                """, (start_date, end_date))
                
                row = cursor.fetchone()
                
                metrics = PerformanceMetrics()
                if row and row['total_trades'] > 0:
                    metrics.total_trades = row['total_trades']
                    metrics.winning_trades = row['winning_trades'] or 0
                    metrics.realized_pnl = Decimal(str(row['realized_pnl'] or 0))
                    metrics.win_rate = metrics.calculate_win_rate()
                
                # 计算累计数据
                cursor = conn.execute("SELECT SUM(profit) as total_pnl FROM trades")
                row = cursor.fetchone()
                if row:
                    metrics.total_pnl = Decimal(str(row['total_pnl'] or 0))
                
                return metrics
                
        except Exception as e:
            self.logger.error(f"Failed to calculate performance metrics: {e}")
            return PerformanceMetrics()
    
    def save_performance_metrics(self, metrics: PerformanceMetrics, target_date: date) -> bool:
        """保存性能指标"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO performance
                    (date, total_pnl, realized_pnl, unrealized_pnl, total_trades,
                     winning_trades, win_rate, max_drawdown, current_drawdown, 
                     daily_return, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_date.isoformat(), float(metrics.total_pnl),
                    float(metrics.realized_pnl), float(metrics.unrealized_pnl),
                    metrics.total_trades, metrics.winning_trades,
                    float(metrics.win_rate), float(metrics.max_drawdown),
                    float(metrics.current_drawdown), float(metrics.daily_return),
                    metrics.updated_at.isoformat()
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to save performance metrics: {e}")
            return False
    
    def log_event(self, level: str, component: str, message: str, details: Optional[dict] = None) -> bool:
        """记录系统日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO system_logs (timestamp, level, component, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(), level, component, message,
                    json.dumps(details) if details else None
                ))
            return True
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
            return False
    
    def cleanup_old_data(self, days: int = 30):
        """清理旧数据"""
        try:
            cutoff_date = datetime.now().replace(day=datetime.now().day - days)
            
            with sqlite3.connect(self.db_path) as conn:
                # 清理旧日志
                cursor = conn.execute(
                    "DELETE FROM system_logs WHERE timestamp < ?",
                    (cutoff_date.isoformat(),)
                )
                deleted_logs = cursor.rowcount
                
                # 清理旧性能记录（保留最近30天）
                cursor = conn.execute(
                    "DELETE FROM performance WHERE date < ?",
                    (cutoff_date.date().isoformat(),)
                )
                deleted_performance = cursor.rowcount
                
                self.logger.info(f"Cleaned up {deleted_logs} log entries and {deleted_performance} performance records")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old data: {e}")
    
    def backup_database(self, backup_path: str) -> bool:
        """备份数据库"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            self.logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to backup database: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}
                
                # 各表的记录数
                tables = ['orders', 'trades', 'performance', 'system_logs', 'grid_states']
                for table in tables:
                    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[f"{table}_count"] = cursor.fetchone()[0]
                
                # 数据库文件大小
                db_file = Path(self.db_path)
                if db_file.exists():
                    stats['db_size_mb'] = round(db_file.stat().st_size / 1024 / 1024, 2)
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
            return {}