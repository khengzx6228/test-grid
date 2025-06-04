# main.py - 修复版主程序入口
import asyncio
import signal
import sys
import logging
from pathlib import Path
from datetime import datetime
import traceback

from core_system import TradingSystem, TradingSystemError
from trading_engine import GridTradingEngine
from web_api_service import WebAPIService, create_web_service

class GridTradingApplication:
    """网格交易应用主类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.trading_system: TradingSystem = None
        self.web_service: WebAPIService = None
        self.running = False
        
        # 设置信号处理
        self._setup_signal_handlers()
        
        # 设置日志
        self.logger = self._setup_application_logging()
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
            
            # 创建停止任务
            if asyncio.get_event_loop().is_running():
                asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Windows平台特殊处理
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, signal_handler)
    
    def _setup_application_logging(self) -> logging.Logger:
        """设置应用级日志"""
        # 确保日志目录存在
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 配置根日志器
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(
                    log_dir / f"application_{datetime.now().strftime('%Y%m%d')}.log",
                    encoding='utf-8'
                ),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        return logging.getLogger("GridTradingApp")
    
    async def initialize(self) -> bool:
        """初始化应用"""
        try:
            self.logger.info("=" * 60)
            self.logger.info("🚀 Grid Trading System Initializing...")
            self.logger.info("=" * 60)
            
            # 检查Python版本
            if sys.version_info < (3, 8):
                raise TradingSystemError("Python 3.8 or higher is required")
            
            # 创建必要目录
            self._create_directories()
            
            # 初始化交易系统
            self.trading_system = TradingSystem(self.config_path)
            
            if not await self.trading_system.start():
                raise TradingSystemError("Failed to start trading system")
            
            # 初始化交易引擎
            trading_engine = GridTradingEngine(
                self.trading_system.config_manager,
                self.trading_system.db_manager
            )
            
            # 注册交易引擎组件
            self.trading_system.register_component('trading_engine', trading_engine)
            
            # 初始化Web服务
            self.web_service = await create_web_service(self.trading_system)
            
            self.logger.info("✅ Application initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Application initialization failed: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    def _create_directories(self):
        """创建必要的目录"""
        directories = [
            "logs",
            "data", 
            "backups",
            "config"
        ]
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True)
            self.logger.debug(f"Created directory: {directory}")
    
    async def start(self) -> int:
        """启动应用"""
        try:
            # 初始化应用
            if not await self.initialize():
                return 1
            
            self.running = True
            
            # 获取Web服务配置
            web_port = self.trading_system.config_manager.get('system.web_port', 8080)
            
            self.logger.info("🌟 Starting services...")
            
            # 创建任务列表
            tasks = []
            
            # 启动Web服务器
            web_task = asyncio.create_task(
                self.web_service.start_server(port=web_port),
                name="web_server"
            )
            tasks.append(web_task)
            
            # 启动应用监控循环
            monitor_task = asyncio.create_task(
                self._application_monitor_loop(),
                name="app_monitor"
            )
            tasks.append(monitor_task)
            
            self.logger.info("=" * 60)
            self.logger.info("🎉 Grid Trading System Started Successfully!")
            self.logger.info(f"🌐 Web Interface: http://localhost:{web_port}")
            self.logger.info(f"📊 API Endpoint: http://localhost:{web_port}/api/v1")
            self.logger.info(f"🔌 WebSocket: ws://localhost:{web_port}/ws")
            self.logger.info("=" * 60)
            
            # 等待所有任务完成或被中断
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                self.logger.error(f"Task execution error: {e}")
            
            return 0
            
        except KeyboardInterrupt:
            self.logger.info("👋 Received keyboard interrupt")
            return 0
        except Exception as e:
            self.logger.error(f"💥 Application startup failed: {e}")
            self.logger.error(traceback.format_exc())
            return 1
        finally:
            await self.shutdown()
    
    async def _application_monitor_loop(self):
        """应用监控循环"""
        self.logger.info("📡 Application monitor started")
        
        health_check_interval = 60  # 1分钟检查一次
        last_health_check = datetime.now()
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # 定期健康检查
                if (current_time - last_health_check).seconds >= health_check_interval:
                    await self._perform_health_check()
                    last_health_check = current_time
                
                # 检查系统状态
                await self._check_system_status()
                
                await asyncio.sleep(10)  # 每10秒检查一次
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(30)  # 出错时等待30秒
    
    async def _perform_health_check(self):
        """执行健康检查"""
        try:
            health_status = await self.trading_system.health_check()
            
            if health_status.get('status') != 'healthy':
                self.logger.warning(f"System health check failed: {health_status}")
                
                # 记录健康检查结果到数据库
                if self.trading_system.db_manager:
                    await self.trading_system.db_manager.log_event(
                        "WARNING", "HealthCheck", 
                        "System health check warning",
                        health_status
                    )
            else:
                self.logger.debug("System health check passed")
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
    
    async def _check_system_status(self):
        """检查系统状态"""
        try:
            # 检查交易引擎状态
            trading_engine = self.trading_system.get_component('trading_engine')
            if trading_engine:
                engine_health = await trading_engine.health_check()
                if engine_health.get('status') != 'healthy':
                    self.logger.warning(f"Trading engine health issue: {engine_health}")
            
            # 检查数据库连接
            if self.trading_system.db_manager:
                try:
                    await self.trading_system.db_manager.get_system_state()
                except Exception as e:
                    self.logger.error(f"Database connection issue: {e}")
            
        except Exception as e:
            self.logger.error(f"System status check failed: {e}")
    
    async def shutdown(self):
        """优雅关闭应用"""
        try:
            self.logger.info("🛑 Shutting down Grid Trading System...")
            self.running = False
            
            # 停止交易系统
            if self.trading_system:
                await self.trading_system.stop()
                self.logger.info("✅ Trading system stopped")
            
            # 清理Web服务（如果需要特殊清理）
            if self.web_service:
                # Web服务的清理会在trading_system.stop()中处理
                self.logger.info("✅ Web service stopped")
            
            self.logger.info("👋 Application shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

# 便捷启动函数
async def run_application(config_path: str = "config.yaml") -> int:
    """运行应用（异步）"""
    app = GridTradingApplication(config_path)
    return await app.start()

def main():
    """主入口函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="Grid Trading System - Advanced Cryptocurrency Trading Bot"
    )
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    parser.add_argument(
        '--check-config',
        action='store_true',
        help='Check configuration and exit'
    )
    parser.add_argument(
        '--version',
        action='store_true',
        help='Show version and exit'
    )
    
    args = parser.parse_args()
    
    # 处理版本显示
    if args.version:
        print("Grid Trading System v2.0")
        print("Advanced Cryptocurrency Trading Bot")
        print("Python version:", sys.version)
        return 0
    
    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 检查配置
    if args.check_config:
        try:
            from core_system import ConfigManager
            config_manager = ConfigManager(args.config)
            if config_manager.load_config():
                print("✅ Configuration is valid")
                return 0
            else:
                print("❌ Configuration validation failed")
                return 1
        except Exception as e:
            print(f"❌ Configuration check failed: {e}")
            return 1
    
    # 显示启动横幅
    print_startup_banner()
    
    # 检查配置文件
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"⚠️  Configuration file not found: {args.config}")
        print("📝 A default configuration will be created on first run")
    
    try:
        # 运行应用
        if sys.platform == "win32":
            # Windows平台特殊处理
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        return asyncio.run(run_application(args.config))
        
    except KeyboardInterrupt:
        print("\n👋 Graceful shutdown completed")
        return 0
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        logging.error(f"Fatal error: {e}")
        logging.error(traceback.format_exc())
        return 1

def print_startup_banner():
    """打印启动横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║    🚀 Grid Trading System v2.0                              ║
║    Advanced Cryptocurrency Trading Bot                       ║
║                                                              ║
║    🔹 Multi-layer Grid Strategy                             ║
║    🔹 Real-time Risk Management                             ║
║    🔹 Web-based Monitoring                                  ║
║    🔹 RESTful API & WebSocket                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

⚠️  RISK WARNING:
   Cryptocurrency trading involves substantial risk of loss.
   This software is for educational and research purposes.
   Trade responsibly and never invest more than you can afford to lose.

"""
    print(banner)

if __name__ == "__main__":
    sys.exit(main())