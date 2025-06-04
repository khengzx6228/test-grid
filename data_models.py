# data_models.py - 核心数据模型
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Literal
from enum import Enum
import json

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    PENDING = "PENDING"
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"

class GridLevel(Enum):
    HIGH_FREQ = "high_freq"      # 高频套利层 ±3%
    MAIN_TREND = "main_trend"    # 主趋势层 ±15% 
    INSURANCE = "insurance"      # 保险层 ±50%

class MarketState(Enum):
    SIDEWAYS = "sideways"        # 震荡
    BULL = "bull"               # 牛市
    BEAR = "bear"               # 熊市
    VOLATILE = "volatile"        # 高波动

@dataclass
class TradingConfig:
    """交易配置 - 简化版"""
    # 基础配置
    symbol: str = "BTCUSDT"
    leverage: int = 1
    initial_balance: Decimal = Decimal("1000")
    
    # 网格配置
    high_freq_range: Decimal = Decimal("0.03")     # ±3%
    high_freq_spacing: Decimal = Decimal("0.005")  # 0.5%
    high_freq_size: Decimal = Decimal("20")        # 20 USDT每单
    
    main_trend_range: Decimal = Decimal("0.15")    # ±15%
    main_trend_spacing: Decimal = Decimal("0.01")  # 1%
    main_trend_size: Decimal = Decimal("50")       # 50 USDT每单
    
    insurance_range: Decimal = Decimal("0.50")     # ±50%
    insurance_spacing: Decimal = Decimal("0.05")   # 5%
    insurance_size: Decimal = Decimal("100")       # 100 USDT每单
    
    # 风险控制
    max_drawdown: Decimal = Decimal("0.20")        # 20%最大回撤
    stop_loss: Decimal = Decimal("0.15")           # 15%止损
    
    # 系统配置
    check_interval: int = 5  # 检查间隔(秒)
    web_port: int = 8080
    
    # API配置
    binance_api_key: str = ""
    binance_api_secret: str = ""
    use_testnet: bool = True
    
    # 通知配置
    telegram_token: str = ""
    telegram_chat_id: str = ""
    enable_notifications: bool = False

@dataclass 
class OrderInfo:
    """订单信息"""
    id: str
    exchange_order_id: Optional[str]
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    status: OrderStatus
    grid_level: GridLevel
    grid_index: int
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    profit: Decimal = Decimal("0")
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'exchange_order_id': self.exchange_order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'price': float(self.price),
            'quantity': float(self.quantity),
            'status': self.status.value,
            'grid_level': self.grid_level.value,
            'grid_index': self.grid_index,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'profit': float(self.profit)
        }

@dataclass
class TradeRecord:
    """交易记录"""
    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    commission: Decimal
    profit: Decimal
    grid_level: GridLevel
    executed_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value,
            'price': float(self.price),
            'quantity': float(self.quantity),
            'commission': float(self.commission),
            'profit': float(self.profit),
            'grid_level': self.grid_level.value,
            'executed_at': self.executed_at.isoformat()
        }

@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    win_rate: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    current_drawdown: Decimal = Decimal("0")
    daily_return: Decimal = Decimal("0")
    updated_at: datetime = field(default_factory=datetime.now)
    
    def calculate_win_rate(self) -> Decimal:
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.total_trades)) * 100
    
    def to_dict(self) -> dict:
        return {
            'total_pnl': float(self.total_pnl),
            'realized_pnl': float(self.realized_pnl),
            'unrealized_pnl': float(self.unrealized_pnl),
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': float(self.win_rate),
            'max_drawdown': float(self.max_drawdown),
            'current_drawdown': float(self.current_drawdown),
            'daily_return': float(self.daily_return),
            'updated_at': self.updated_at.isoformat()
        }

@dataclass
class SystemStatus:
    """系统状态"""
    running: bool = False
    current_price: Decimal = Decimal("0")
    active_orders: int = 0
    grid_integrity: Dict[GridLevel, Decimal] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    uptime_seconds: int = 0
    
    def to_dict(self) -> dict:
        return {
            'running': self.running,
            'current_price': float(self.current_price),
            'active_orders': self.active_orders,
            'grid_integrity': {level.value: float(integrity) for level, integrity in self.grid_integrity.items()},
            'last_update': self.last_update.isoformat(),
            'error_message': self.error_message,
            'uptime_seconds': self.uptime_seconds
        }