# core_system.py - 修复版核心系统模块
import asyncio
import logging
import yaml
import json
import hashlib
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from contextlib import asynccontextmanager
import aiohttp
import aiosqlite
from dataclasses import dataclass, field, asdict
from enum import Enum
import traceback

# ===== 配置管理模块 =====
class ConfigManager:
    """统一配置管理器"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.encrypted_fields = {'binance_api_key', 'binance_api_secret', 'telegram_token'}
        
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if not self.config_path.exists():
                self._create_default_config()
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                
            # 验证配置
            if not self._validate_config():
                return False
                
            # 解密敏感字段
            self._decrypt_sensitive_fields()
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return False
    
    def _create_default_config(self):
        """创建默认配置"""
        default_config = {
            'trading': {
                'symbol': 'BTCUSDT',
                'leverage': 1,
                'initial_balance': 1000,
                'grid_configs': {
                    'high_freq': {
                        'range': 0.03,
                        'spacing': 0.005,
                        'size': 20
                    },
                    'main_trend': {
                        'range': 0.15,
                        'spacing': 0.01,
                        'size': 50
                    },
                    'insurance': {
                        'range': 0.50,
                        'spacing': 0.05,
                        'size': 100
                    }
                },
                'risk_management': {
                    'max_drawdown': 0.20,
                    'stop_loss': 0.15
                }
            },
            'system': {
                'check_interval': 5,
                'web_port': 8080,
                'log_level': 'INFO',
                'database_url': 'sqlite:///data/trading.db'
            },
            'api': {
                'binance_api_key': 'YOUR_API_KEY_HERE',
                'binance_api_secret': 'YOUR_API_SECRET_HERE',
                'use_testnet': True
            },
            'features': {
                'multi_symbol': {
                    'enabled': False,
                    'symbols': ['BTCUSDT', 'ETHUSDT'],
                    'capital_allocation': 'auto'
                },
                'ai_optimization': {
                    'enabled': False,
                    'interval_hours': 1
                },
                'notifications': {
                    'enabled': False,
                    'telegram_token': '',
                    'telegram_chat_id': ''
                }
            }
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    
    def _validate_config(self) -> bool:
        """验证配置有效性"""
        required_sections = ['trading', 'system', 'api']
        
        for section in required_sections:
            if section not in self.config:
                logging.error(f"Missing config section: {section}")
                return False
        
        # 验证API密钥
        api_key = self.config['api'].get('binance_api_key', '')
        if api_key == 'YOUR_API_KEY_HERE' or not api_key:
            logging.error("Please configure valid Binance API credentials")
            return False
            
        return True
    
    def _decrypt_sensitive_fields(self):
        """解密敏感字段（简化实现）"""
        # 在实际应用中应该使用适当的加密库
        pass
    
    def get(self, key_path: str, default=None):
        """获取配置值"""
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
    
    def update(self, key_path: str, value: Any):
        """更新配置值"""
        keys = key_path.split('.')
        config_section = self.config
        
        for key in keys[:-1]:
            if key not in config_section:
                config_section[key] = {}
            config_section = config_section[key]
            
        config_section[keys[-1]] = value
        
        # 保存到文件
        self.save_config()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

# ===== 数据模型 =====
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
    HIGH_FREQ = "high_freq"
    MAIN_TREND = "main_trend"
    INSURANCE = "insurance"

@dataclass
class OrderInfo:
    """订单信息数据类"""
    id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    status: OrderStatus
    grid_level: GridLevel
    grid_index: int
    exchange_order_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    profit: Decimal = field(default_factory=lambda: Decimal("0"))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'symbol': self.symbol,
            'side': self.side.value,
            'price': float(self.price),
            'quantity': float(self.quantity),
            'status': self.status.value,
            'grid_level': self.grid_level.value,
            'grid_index': self.grid_index,
            'exchange_order_id': self.exchange_order_id,
            'created_at': self.created_at.isoformat(),
            'filled_at': self.filled_at.isoformat() if self.filled_at else None,
            'profit': float(self.profit)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderInfo':
        """从字典创建对象"""
        return cls(
            id=data['id'],
            symbol=data['symbol'],
            side=OrderSide(data['side']),
            price=Decimal(str(data['price'])),
            quantity=Decimal(str(data['quantity'])),
            status=OrderStatus(data['status']),
            grid_level=GridLevel(data['grid_level']),
            grid_index=data['grid_index'],
            exchange_order_id=data.get('exchange_order_id'),
            created_at=datetime.fromisoformat(data['created_at']),
            filled_at=datetime.fromisoformat(data['filled_at']) if data.get('filled_at') else None,
            profit=Decimal(str(data.get('profit', 0)))
        )

@dataclass
class TradingState:
    """交易状态"""
    running: bool = False
    current_price: Decimal = field(default_factory=lambda: Decimal("0"))
    active_orders: int = 0
    total_balance: Decimal = field(default_factory=lambda: Decimal("0"))
    available_balance: Decimal = field(default_factory=lambda: Decimal("0"))
    total_pnl: Decimal = field(default_factory=lambda: Decimal("0"))
    last_update: datetime = field(default_factory=datetime.now)

# ===== 数据库管理器 =====
class DatabaseManager:
    """异步数据库管理器"""
    
    def __init__(self, db_url: str = "sqlite:///data/trading.db"):
        self.db_url = db_url
        self.db_path = db_url.replace("sqlite:///", "")
        self.connection_pool: Optional[aiosqlite.Connection] = None
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> bool:
        """初始化数据库"""
        try:
            # 确保数据目录存在
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            # 创建数据库表
            await self._create_tables()
            
            self.logger.info("Database initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return False
    
    @asynccontextmanager
    async def get_connection(self):
        """获取数据库连接"""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn
    
    async def _create_tables(self):
        """创建数据库表"""
        async with self.get_connection() as conn:
            await conn.executescript("""
                -- 订单表
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    status TEXT NOT NULL,
                    grid_level TEXT NOT NULL,
                    grid_index INTEGER NOT NULL,
                    exchange_order_id TEXT,
                    created_at TEXT NOT NULL,
                    filled_at TEXT,
                    profit REAL DEFAULT 0,
                    UNIQUE(symbol, grid_level, grid_index, side)
                );
                
                -- 交易记录表
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    commission REAL DEFAULT 0,
                    profit REAL DEFAULT 0,
                    grid_level TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    FOREIGN KEY (order_id) REFERENCES orders (id)
                );
                
                -- 系统状态表
                CREATE TABLE IF NOT EXISTS system_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    running BOOLEAN DEFAULT 0,
                    current_price REAL DEFAULT 0,
                    active_orders INTEGER DEFAULT 0,
                    total_balance REAL DEFAULT 0,
                    available_balance REAL DEFAULT 0,
                    total_pnl REAL DEFAULT 0,
                    last_update TEXT NOT NULL,
                    CHECK (id = 1)
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
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
                CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
                CREATE INDEX IF NOT EXISTS idx_trades_executed_at ON trades(executed_at);
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp);
                
                -- 插入默认系统状态
                INSERT OR IGNORE INTO system_state (id, last_update) 
                VALUES (1, datetime('now'));
            """)
            await conn.commit()
    
    async def save_order(self, order: OrderInfo) -> bool:
        """保存订单"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO orders 
                    (id, symbol, side, price, quantity, status, grid_level, grid_index,
                     exchange_order_id, created_at, filled_at, profit)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    order.id, order.symbol, order.side.value, float(order.price),
                    float(order.quantity), order.status.value, order.grid_level.value,
                    order.grid_index, order.exchange_order_id, order.created_at.isoformat(),
                    order.filled_at.isoformat() if order.filled_at else None,
                    float(order.profit)
                ))
                await conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save order: {e}")
            return False
    
    async def get_orders(self, status: Optional[OrderStatus] = None, 
                        symbol: Optional[str] = None) -> List[OrderInfo]:
        """获取订单列表"""
        try:
            query = "SELECT * FROM orders WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
                
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
                
            query += " ORDER BY created_at DESC"
            
            async with self.get_connection() as conn:
                async with conn.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    orders = []
                    for row in rows:
                        order_data = dict(row)
                        orders.append(OrderInfo.from_dict(order_data))
                    
                    return orders
                    
        except Exception as e:
            self.logger.error(f"Failed to get orders: {e}")
            return []
    
    async def update_order_status(self, order_id: str, status: OrderStatus,
                                exchange_order_id: Optional[str] = None,
                                filled_at: Optional[datetime] = None,
                                profit: Optional[Decimal] = None) -> bool:
        """更新订单状态"""
        try:
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
            
            async with self.get_connection() as conn:
                await conn.execute(query, params)
                await conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update order status: {e}")
            return False
    
    async def save_system_state(self, state: TradingState) -> bool:
        """保存系统状态"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE system_state SET
                        running = ?,
                        current_price = ?,
                        active_orders = ?,
                        total_balance = ?,
                        available_balance = ?,
                        total_pnl = ?,
                        last_update = ?
                    WHERE id = 1
                """, (
                    state.running, float(state.current_price), state.active_orders,
                    float(state.total_balance), float(state.available_balance),
                    float(state.total_pnl), state.last_update.isoformat()
                ))
                await conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save system state: {e}")
            return False
    
    async def get_system_state(self) -> TradingState:
        """获取系统状态"""
        try:
            async with self.get_connection() as conn:
                async with conn.execute("SELECT * FROM system_state WHERE id = 1") as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return TradingState(
                            running=bool(row['running']),
                            current_price=Decimal(str(row['current_price'])),
                            active_orders=row['active_orders'],
                            total_balance=Decimal(str(row['total_balance'])),
                            available_balance=Decimal(str(row['available_balance'])),
                            total_pnl=Decimal(str(row['total_pnl'])),
                            last_update=datetime.fromisoformat(row['last_update'])
                        )
                    
                    return TradingState()
                    
        except Exception as e:
            self.logger.error(f"Failed to get system state: {e}")
            return TradingState()
    
    async def log_event(self, level: str, component: str, 
                       message: str, details: Optional[Dict] = None) -> bool:
        """记录系统日志"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO system_logs (timestamp, level, component, message, details)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(), level, component, message,
                    json.dumps(details) if details else None
                ))
                await conn.commit()
                
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to log event: {e}")
            return False

# ===== 异常处理 =====
class TradingSystemError(Exception):
    """交易系统异常基类"""
    pass

class ConfigurationError(TradingSystemError):
    """配置错误"""
    pass

class DatabaseError(TradingSystemError):
    """数据库错误"""
    pass

class APIError(TradingSystemError):
    """API错误"""
    pass

class NetworkError(TradingSystemError):
    """网络错误"""
    pass

def handle_exceptions(func):
    """异常处理装饰器"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logging.error(f"Exception in {func.__name__}: {e}")
            logging.error(traceback.format_exc())
            raise TradingSystemError(f"Error in {func.__name__}: {str(e)}")
    return wrapper

# ===== 网络客户端 =====
class HTTPClient:
    """异步HTTP客户端"""
    
    def __init__(self, base_url: str = "", timeout: int = 30):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()
    
    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """GET请求"""
        if not self.session:
            raise NetworkError("HTTP session not initialized")
            
        try:
            async with self.session.get(f"{self.base_url}{url}", **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json()
                
        except aiohttp.ClientError as e:
            raise NetworkError(f"HTTP GET failed: {e}")
    
    async def post(self, url: str, **kwargs) -> Dict[str, Any]:
        """POST请求"""
        if not self.session:
            raise NetworkError("HTTP session not initialized")
            
        try:
            async with self.session.post(f"{self.base_url}{url}", **kwargs) as resp:
                resp.raise_for_status()
                return await resp.json()
                
        except aiohttp.ClientError as e:
            raise NetworkError(f"HTTP POST failed: {e}")

# ===== 核心系统类 =====
class TradingSystem:
    """核心交易系统"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_manager = ConfigManager(config_path)
        self.db_manager: Optional[DatabaseManager] = None
        self.http_client: Optional[HTTPClient] = None
        self.logger = self._setup_logging()
        
        # 系统状态
        self.running = False
        self.startup_time = datetime.now()
        
        # 组件
        self.components: Dict[str, Any] = {}
        
    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        logger = logging.getLogger("TradingSystem")
        logger.setLevel(logging.INFO)
        
        # 文件处理器
        file_handler = logging.FileHandler(
            log_dir / f"trading_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    async def initialize(self) -> bool:
        """初始化系统"""
        try:
            self.logger.info("Initializing Trading System...")
            
            # 加载配置
            if not self.config_manager.load_config():
                raise ConfigurationError("Failed to load configuration")
            
            # 初始化数据库
            db_url = self.config_manager.get('system.database_url', 'sqlite:///data/trading.db')
            self.db_manager = DatabaseManager(db_url)
            
            if not await self.db_manager.initialize():
                raise DatabaseError("Failed to initialize database")
            
            # 初始化HTTP客户端
            self.http_client = HTTPClient()
            
            # 记录初始化成功
            await self.db_manager.log_event(
                "INFO", "TradingSystem", "System initialized successfully"
            )
            
            self.logger.info("Trading System initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            return False
    
    async def start(self) -> bool:
        """启动系统"""
        try:
            if not await self.initialize():
                return False
            
            self.running = True
            self.startup_time = datetime.now()
            
            # 更新系统状态
            state = TradingState(running=True, last_update=datetime.now())
            await self.db_manager.save_system_state(state)
            
            self.logger.info("Trading System started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start system: {e}")
            return False
    
    async def stop(self):
        """停止系统"""
        try:
            self.running = False
            
            # 停止所有组件
            for name, component in self.components.items():
                if hasattr(component, 'stop'):
                    try:
                        await component.stop()
                        self.logger.info(f"Component {name} stopped")
                    except Exception as e:
                        self.logger.error(f"Error stopping component {name}: {e}")
            
            # 更新系统状态
            if self.db_manager:
                state = TradingState(running=False, last_update=datetime.now())
                await self.db_manager.save_system_state(state)
                
                await self.db_manager.log_event(
                    "INFO", "TradingSystem", "System stopped"
                )
            
            # 关闭HTTP客户端
            if self.http_client:
                await self.http_client.__aexit__(None, None, None)
            
            self.logger.info("Trading System stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error during system shutdown: {e}")
    
    def register_component(self, name: str, component: Any):
        """注册系统组件"""
        self.components[name] = component
        self.logger.info(f"Component registered: {name}")
    
    def get_component(self, name: str) -> Any:
        """获取系统组件"""
        return self.components.get(name)
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            uptime_seconds = (datetime.now() - self.startup_time).total_seconds()
            
            # 检查数据库连接
            db_healthy = False
            if self.db_manager:
                try:
                    await self.db_manager.get_system_state()
                    db_healthy = True
                except:
                    db_healthy = False
            
            # 检查各组件状态
            component_status = {}
            for name, component in self.components.items():
                if hasattr(component, 'health_check'):
                    try:
                        component_status[name] = await component.health_check()
                    except:
                        component_status[name] = {'status': 'unhealthy'}
                else:
                    component_status[name] = {'status': 'unknown'}
            
            health_status = {
                'status': 'healthy' if db_healthy else 'unhealthy',
                'uptime_seconds': int(uptime_seconds),
                'database': 'healthy' if db_healthy else 'unhealthy',
                'components': component_status,
                'timestamp': datetime.now().isoformat()
            }
            
            return health_status
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# ===== 使用示例 =====
async def main():
    """主函数示例"""
    system = TradingSystem("config.yaml")
    
    try:
        if await system.start():
            print("System started successfully")
            
            # 运行系统
            while system.running:
                await asyncio.sleep(1)
                
    except KeyboardInterrupt:
        print("Received interrupt signal")
    finally:
        await system.stop()

if __name__ == "__main__":
    asyncio.run(main())