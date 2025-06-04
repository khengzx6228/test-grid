# main.py - 主程序入口
import asyncio
import logging
import signal
import sys
import yaml
import traceback
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import Optional

# 导入项目模块
from data_models import TradingConfig, PerformanceMetrics
from database_manager import DatabaseManager
from grid_engine import GridTradingEngine
from web_interface import WebInterface
from notification_service import NotificationService

class GridTradingBot:
    """网格交易机器人主类"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config: Optional[TradingConfig] = None
        self.logger = self._setup_logging()
        
        # 核心组件
        self.db: Optional[DatabaseManager] = None
        self.binance_client = None
        self.trading_engine: Optional[GridTradingEngine] = None
        self.web_interface: Optional[WebInterface] = None
        self.notification: Optional[NotificationService] = None
        
        # 状态
        self.running = False
        self.start_time = datetime.now()
        
        # 设置信号处理
        self._setup_signal_handlers()
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志"""
        # 创建logs目录
        Path("logs").mkdir(exist_ok=True)
        
        # 配置日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 文件处理器
        file_handler = logging.FileHandler(
            f'logs/grid_trading_{datetime.now().strftime("%Y%m%d")}.log',
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # 配置根日志器
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logging.getLogger(__name__)
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if not Path(self.config_file).exists():
                self.logger.info(f"Config file {self.config_file} not found, creating default config...")
                self._create_default_config()
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 验证配置
            if not self._validate_config(config_data):
                return False
            
            # 创建配置对象
            self.config = TradingConfig(
                symbol=config_data.get('symbol', 'BTCUSDT'),
                leverage=config_data.get('leverage', 1),
                initial_balance=Decimal(str(config_data.get('initial_balance', 1000))),
                
                # 网格配置
                high_freq_range=Decimal(str(config_data.get('high_freq_range', 0.03))),
                high_freq_spacing=Decimal(str(config_data.get('high_freq_spacing', 0.005))),
                high_freq_size=Decimal(str(config_data.get('high_freq_size', 20))),
                
                main_trend_range=Decimal(str(config_data.get('main_trend_range', 0.15))),
                main_trend_spacing=Decimal(str(config_data.get('main_trend_spacing', 0.01))),
                main_trend_size=Decimal(str(config_data.get('main_trend_size', 50))),
                
                insurance_range=Decimal(str(config_data.get('insurance_range', 0.50))),
                insurance_spacing=Decimal(str(config_data.get('insurance_spacing', 0.05))),
                insurance_size=Decimal(str(config_data.get('insurance_size', 100))),
                
                # 风险控制
                max_drawdown=Decimal(str(config_data.get('max_drawdown', 0.20))),
                stop_loss=Decimal(str(config_data.get('stop_loss', 0.15))),
                
                # 系统配置
                check_interval=config_data.get('check_interval', 5),
                web_port=config_data.get('web_port', 8080),
                
                # API配置
                binance_api_key=config_data.get('binance_api_key', ''),
                binance_api_secret=config_data.get('binance_api_secret', ''),
                use_testnet=config_data.get('use_testnet', True),
                
                # 通知配置
                telegram_token=config_data.get('telegram_token', ''),
                telegram_chat_id=config_data.get('telegram_chat_id', ''),
                enable_notifications=config_data.get('enable_notifications', False)
            )
            
            self.logger.info("Configuration loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return False
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            'symbol': 'BTCUSDT',
            'leverage': 1,
            'initial_balance': 1000,
            
            # 网格配置
            'high_freq_range': 0.03,      # ±3%
            'high_freq_spacing': 0.005,   # 0.5%
            'high_freq_size': 20,         # 20 USDT
            
            'main_trend_range': 0.15,     # ±15%
            'main_trend_spacing': 0.01,   # 1%
            'main_trend_size': 50,        # 50 USDT
            
            'insurance_range': 0.50,      # ±50%
            'insurance_spacing': 0.05,    # 5%
            'insurance_size': 100,        # 100 USDT
            
            # 风险控制
            'max_drawdown': 0.20,         # 20%
            'stop_loss': 0.15,            # 15%
            
            # 系统配置
            'check_interval': 5,
            'web_port': 8080,
            
            # API配置 - 需要用户填写
            'binance_api_key': 'YOUR_API_KEY_HERE',
            'binance_api_secret': 'YOUR_API_SECRET_HERE',
            'use_testnet': True,
            
            # 通知配置
            'telegram_token': '',
            'telegram_chat_id': '',
            'enable_notifications': False
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
        
        self.logger.info(f"Created default config file: {self.config_file}")
        print(f"\n⚠️  请编辑 {self.config_file} 文件，填入您的API密钥后重新运行程序\n")
    
    def _validate_config(self, config_data: dict) -> bool:
        """验证配置"""
        # 检查必需的API密钥
        api_key = config_data.get('binance_api_key', '')
        api_secret = config_data.get('binance_api_secret', '')
        
        if api_key == 'YOUR_API_KEY_HERE' or not api_key:
            self.logger.error("请在配置文件中设置有效的 binance_api_key")
            return False
        
        if api_secret == 'YOUR_API_SECRET_HERE' or not api_secret:
            self.logger.error("请在配置文件中设置有效的 binance_api_secret")
            return False
        
        # 检查数值配置
        try:
            initial_balance = float(config_data.get('initial_balance', 1000))
            if initial_balance <= 0:
                self.logger.error("initial_balance 必须大于0")
                return False
        except (ValueError, TypeError):
            self.logger.error("initial_balance 必须是有效数字")
            return False
        
        return True
    
    async def initialize_components(self) -> bool:
        """初始化系统组件"""
        try:
            self.logger.info("Initializing system components...")
            
            # 1. 初始化数据库
            self.db = DatabaseManager()
            self.logger.info("Database initialized")
            
            # 2. 初始化Binance客户端
            from binance import AsyncClient
            self.binance_client = await AsyncClient.create(
                api_key=self.config.binance_api_key,
                api_secret=self.config.binance_api_secret,
                testnet=self.config.use_testnet
            )
            
            # 验证API连接
            await self.binance_client.ping()
            self.logger.info("Binance client initialized and verified")
            
            # 3. 初始化交易引擎
            self.trading_engine = GridTradingEngine(self.config, self.binance_client, self.db)
            
            # 4. 初始化通知服务
            if self.config.enable_notifications:
                self.notification = NotificationService(self.config)
            
            # 5. 初始化Web界面
            self.web_interface = WebInterface(self.config.web_port, self)
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def start(self) -> bool:
        """启动系统"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("🚀 Grid Trading System Starting")
            self.logger.info("=" * 60)
            
            # 加载配置
            if not self.load_config():
                return False
            
            # 初始化组件
            if not await self.initialize_components():
                return False
            
            # 初始化交易引擎
            if not await self.trading_engine.initialize():
                self.logger.error("Failed to initialize trading engine")
                return False
            
            # 启动Web界面
            web_task = asyncio.create_task(self.web_interface.start())
            
            # 发送启动通知
            if self.notification:
                await self.notification.send_message(
                    f"🚀 网格交易系统启动成功\n"
                    f"交易对: {self.config.symbol}\n"
                    f"初始资金: {self.config.initial_balance} USDT\n"
                    f"Web界面: http://localhost:{self.config.web_port}"
                )
            
            self.running = True
            self.logger.info(f"✅ System started successfully!")
            self.logger.info(f"🌐 Web interface: http://localhost:{self.config.web_port}")
            
            # 启动交易循环
            trading_task = asyncio.create_task(self.trading_engine.run_trading_loop())
            
            # 启动监控循环
            monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            # 等待任务完成或中断
            await asyncio.gather(web_task, trading_task, monitoring_task, return_exceptions=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start system: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _monitoring_loop(self):
        """监控循环"""
        while self.running:
            try:
                # 每小时更新一次性能指标和发送报告
                await asyncio.sleep(3600)
                
                if not self.running:
                    break
                
                # 更新性能指标
                await self._update_performance_metrics()
                
                # 发送状态报告
                if self.notification:
                    await self._send_status_report()
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _update_performance_metrics(self):
        """更新性能指标"""
        try:
            metrics = self.db.get_performance_metrics()
            self.db.save_performance_metrics(metrics, datetime.now().date())
            
        except Exception as e:
            self.logger.error(f"Failed to update performance metrics: {e}")
    
    async def _send_status_report(self):
        """发送状态报告"""
        try:
            if not self.notification:
                return
            
            status = self.trading_engine.get_status()
            metrics = self.db.get_performance_metrics()
            
            uptime_hours = status.uptime_seconds / 3600
            
            message = f"""
📊 网格交易系统状态报告

💰 收益概览:
• 总盈亏: {metrics.total_pnl:.2f} USDT
• 今日盈亏: {metrics.realized_pnl:.2f} USDT
• 胜率: {metrics.win_rate:.1f}%

🎯 交易状态:
• 当前价格: ${status.current_price:.2f}
• 活跃订单: {status.active_orders}
• 总交易次数: {metrics.total_trades}

📈 网格状态:
• 高频层: {status.grid_integrity.get('high_freq', 0):.1f}%
• 主趋势: {status.grid_integrity.get('main_trend', 0):.1f}%
• 保险层: {status.grid_integrity.get('insurance', 0):.1f}%

⏱️ 运行时间: {uptime_hours:.1f} 小时
"""
            
            await self.notification.send_message(message.strip())
            
        except Exception as e:
            self.logger.error(f"Failed to send status report: {e}")
    
    async def stop(self):
        """停止系统"""
        self.logger.info("Stopping Grid Trading System...")
        self.running = False
        
        try:
            # 停止交易引擎
            if self.trading_engine:
                self.trading_engine.stop()
            
            # 停止Web界面
            if self.web_interface:
                await self.web_interface.stop()
            
            # 发送停止通知
            if self.notification:
                await self.notification.send_message("🛑 网格交易系统已停止")
            
            # 关闭Binance连接
            if self.binance_client:
                await self.binance_client.close_connection()
            
            # 清理数据库
            if self.db:
                self.db.cleanup_old_data()
            
            self.logger.info("✅ System stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def get_status(self) -> dict:
        """获取系统状态"""
        if not self.trading_engine:
            return {"running": False, "error": "System not initialized"}
        
        status = self.trading_engine.get_status()
        metrics = self.db.get_performance_metrics() if self.db else PerformanceMetrics()
        
        return {
            "running": self.running,
            "start_time": self.start_time.isoformat(),
            "current_price": float(status.current_price),
            "active_orders": status.active_orders,
            "grid_integrity": {level.value: float(integrity) for level, integrity in status.grid_integrity.items()},
            "performance": metrics.to_dict(),
            "uptime_seconds": status.uptime_seconds,
            "last_update": status.last_update.isoformat()
        }
    
    def get_trades(self, days: int = 7) -> list:
        """获取交易记录"""
        if not self.db:
            return []
        
        trades = self.db.get_trades(days)
        return [trade.to_dict() for trade in trades]
    
    def get_orders(self) -> list:
        """获取活跃订单"""
        if not self.db:
            return []
        
        orders = self.db.get_active_orders()
        return [order.to_dict() for order in orders]

# 异步主函数
async def async_main():
    """异步主函数"""
    bot = None
    
    try:
        # 创建机器人实例
        bot = GridTradingBot()
        
        # 启动系统
        success = await bot.start()
        
        if not success:
            return 1
        
        # 等待直到系统停止
        while bot.running:
            await asyncio.sleep(1)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n收到中断信号，正在停止系统...")
        return 0
    except Exception as e:
        print(f"系统发生严重错误: {e}")
        return 1
    finally:
        if bot:
            await bot.stop()

# 主程序入口
def main():
    """主程序入口"""
    print("""
🚀 天地双网格交易系统 v2.0
================================

个人版 - 专为个人交易者优化
- 轻量级部署，一键启动
- 三层网格策略，智能风控
- 实时Web监控，简洁易用

启动中...
""")
    
    # 创建必要目录
    Path("logs").mkdir(exist_ok=True)
    Path("backups").mkdir(exist_ok=True)
    
    # 运行异步主程序
    try:
        exit_code = asyncio.run(async_main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 感谢使用网格交易系统！")
        sys.exit(0)

if __name__ == "__main__":
    main()