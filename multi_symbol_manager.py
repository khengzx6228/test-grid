# multi_symbol_manager.py - 多币种支持模块
import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from decimal import Decimal
from data_models import TradingConfig, GridLevel, OrderInfo, PerformanceMetrics
from database_manager import DatabaseManager
from grid_engine import GridTradingEngine

class SymbolConfig:
    """单个币种配置"""
    
    def __init__(self, symbol: str, base_config: TradingConfig):
        self.symbol = symbol
        self.enabled = True
        
        # 继承基础配置
        self.leverage = base_config.leverage
        self.check_interval = base_config.check_interval
        
        # 币种特定配置（可以针对不同币种调整）
        self.high_freq_range = base_config.high_freq_range
        self.high_freq_spacing = base_config.high_freq_spacing
        self.high_freq_size = base_config.high_freq_size
        
        self.main_trend_range = base_config.main_trend_range
        self.main_trend_spacing = base_config.main_trend_spacing
        self.main_trend_size = base_config.main_trend_size
        
        self.insurance_range = base_config.insurance_range
        self.insurance_spacing = base_config.insurance_spacing
        self.insurance_size = base_config.insurance_size
        
        # 风险控制
        self.max_drawdown = base_config.max_drawdown
        self.stop_loss = base_config.stop_loss
        
        # 币种特定参数
        self.min_notional = Decimal("5")  # 最小订单价值
        self.price_precision = 2  # 价格精度
        self.quantity_precision = 6  # 数量精度
        
        # 资金分配比例
        self.capital_allocation_ratio = Decimal("1.0")  # 默认等比例分配

class MultiSymbolManager:
    """多币种管理器"""
    
    def __init__(self, base_config: TradingConfig, binance_client, db_manager: DatabaseManager):
        self.base_config = base_config
        self.binance = binance_client
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # 币种管理
        self.symbol_configs: Dict[str, SymbolConfig] = {}
        self.symbol_engines: Dict[str, GridTradingEngine] = {}
        self.symbol_tasks: Dict[str, asyncio.Task] = {}
        
        # 全局状态
        self.running = False
        self.total_capital = Decimal("0")
        self.symbol_capital_allocation: Dict[str, Decimal] = {}
        
        # 默认支持的币种列表
        self.default_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT",
            "DOTUSDT", "MATICUSDT", "AVAXUSDT", "ATOMUSDT", "LINKUSDT"
        ]
        
    async def initialize(self, symbols: Optional[List[str]] = None):
        """初始化多币种管理器"""
        try:
            self.logger.info("Initializing multi-symbol manager...")
            
            # 获取总资金
            account_info = await self.binance.futures_account()
            self.total_capital = Decimal(account_info['totalWalletBalance'])
            
            # 确定要交易的币种
            target_symbols = symbols or [self.base_config.symbol]
            
            # 验证币种有效性
            valid_symbols = await self._validate_symbols(target_symbols)
            
            # 为每个币种创建配置
            await self._create_symbol_configs(valid_symbols)
            
            # 分配资金
            await self._allocate_capital()
            
            # 创建交易引擎
            await self._create_trading_engines()
            
            self.logger.info(f"Multi-symbol manager initialized for {len(valid_symbols)} symbols")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize multi-symbol manager: {e}")
            return False
    
    async def _validate_symbols(self, symbols: List[str]) -> List[str]:
        """验证币种有效性"""
        try:
            # 获取交易所支持的币种信息
            exchange_info = await self.binance.futures_exchange_info()
            valid_symbols_info = {s['symbol']: s for s in exchange_info['symbols'] if s['status'] == 'TRADING'}
            
            validated_symbols = []
            for symbol in symbols:
                if symbol in valid_symbols_info:
                    validated_symbols.append(symbol)
                    self.logger.info(f"Symbol {symbol} validated successfully")
                else:
                    self.logger.warning(f"Symbol {symbol} not available for trading")
            
            return validated_symbols
            
        except Exception as e:
            self.logger.error(f"Symbol validation failed: {e}")
            return [self.base_config.symbol]  # 回退到默认币种
    
    async def _create_symbol_configs(self, symbols: List[str]):
        """为每个币种创建配置"""
        try:
            for symbol in symbols:
                # 获取币种特定信息
                symbol_info = await self._get_symbol_info(symbol)
                
                # 创建币种配置
                config = SymbolConfig(symbol, self.base_config)
                
                # 应用币种特定设置
                if symbol_info:
                    config.price_precision = symbol_info.get('pricePrecision', 2)
                    config.quantity_precision = symbol_info.get('quantityPrecision', 6)
                    config.min_notional = Decimal(str(symbol_info.get('minNotional', 5)))
                
                # 根据币种特性调整参数
                config = await self._adjust_symbol_parameters(config, symbol)
                
                self.symbol_configs[symbol] = config
                
                self.logger.info(f"Created config for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to create symbol configs: {e}")
    
    async def _get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """获取币种信息"""
        try:
            exchange_info = await self.binance.futures_exchange_info()
            for s in exchange_info['symbols']:
                if s['symbol'] == symbol:
                    return s
            return None
        except Exception as e:
            self.logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None
    
    async def _adjust_symbol_parameters(self, config: SymbolConfig, symbol: str) -> SymbolConfig:
        """根据币种特性调整参数"""
        try:
            # 获取币种的历史价格数据分析波动性
            klines = await self.binance.futures_klines(
                symbol=symbol,
                interval='1d',
                limit=30
            )
            
            # 计算30天波动率
            prices = [Decimal(kline[4]) for kline in klines]
            volatility = self._calculate_volatility(prices)
            
            # 根据波动率调整参数
            if volatility > Decimal("0.15"):  # 高波动币种
                config.high_freq_spacing *= Decimal("1.5")  # 增加间距
                config.main_trend_spacing *= Decimal("1.3")
                config.insurance_spacing *= Decimal("1.2")
                
                # 减少订单大小
                config.high_freq_size *= Decimal("0.8")
                config.main_trend_size *= Decimal("0.8")
                config.insurance_size *= Decimal("0.8")
                
                self.logger.info(f"Adjusted parameters for high volatility symbol {symbol}")
                
            elif volatility < Decimal("0.05"):  # 低波动币种
                config.high_freq_spacing *= Decimal("0.8")  # 减少间距
                config.main_trend_spacing *= Decimal("0.9")
                
                # 可以增加订单大小
                config.high_freq_size *= Decimal("1.1")
                config.main_trend_size *= Decimal("1.1")
                
                self.logger.info(f"Adjusted parameters for low volatility symbol {symbol}")
            
            # 根据市值/流动性调整
            # 主流币种（BTC, ETH）可以分配更多资金
            if symbol in ["BTCUSDT", "ETHUSDT"]:
                config.capital_allocation_ratio = Decimal("1.5")
            elif symbol in ["BNBUSDT", "ADAUSDT", "SOLUSDT"]:
                config.capital_allocation_ratio = Decimal("1.2")
            else:
                config.capital_allocation_ratio = Decimal("0.8")
            
            return config
            
        except Exception as e:
            self.logger.error(f"Failed to adjust parameters for {symbol}: {e}")
            return config
    
    def _calculate_volatility(self, prices: List[Decimal]) -> Decimal:
        """计算价格波动率"""
        if len(prices) < 2:
            return Decimal("0.05")
        
        returns = []
        for i in range(1, len(prices)):
            ret = (prices[i] - prices[i-1]) / prices[i-1]
            returns.append(ret)
        
        if not returns:
            return Decimal("0.05")
        
        mean_return = sum(returns) / len(returns)
        variance = sum((ret - mean_return) ** 2 for ret in returns) / len(returns)
        volatility = variance ** Decimal("0.5")
        
        return volatility
    
    async def _allocate_capital(self):
        """分配资金到各币种"""
        try:
            # 计算总权重
            total_weight = sum(config.capital_allocation_ratio for config in self.symbol_configs.values())
            
            # 为每个币种分配资金
            for symbol, config in self.symbol_configs.items():
                allocation_ratio = config.capital_allocation_ratio / total_weight
                allocated_capital = self.total_capital * allocation_ratio
                
                self.symbol_capital_allocation[symbol] = allocated_capital
                
                self.logger.info(f"Allocated {allocated_capital:.2f} USDT to {symbol} ({allocation_ratio:.1%})")
            
        except Exception as e:
            self.logger.error(f"Capital allocation failed: {e}")
    
    async def _create_trading_engines(self):
        """为每个币种创建交易引擎"""
        try:
            for symbol, config in self.symbol_configs.items():
                # 创建币种特定的配置对象
                symbol_trading_config = self._create_symbol_trading_config(config)
                
                # 创建交易引擎
                engine = GridTradingEngine(
                    symbol_trading_config, 
                    self.binance, 
                    self.db
                )
                
                self.symbol_engines[symbol] = engine
                
                self.logger.info(f"Created trading engine for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Failed to create trading engines: {e}")
    
    def _create_symbol_trading_config(self, symbol_config: SymbolConfig) -> TradingConfig:
        """为币种创建TradingConfig对象"""
        return TradingConfig(
            symbol=symbol_config.symbol,
            leverage=symbol_config.leverage,
            initial_balance=self.symbol_capital_allocation[symbol_config.symbol],
            
            high_freq_range=symbol_config.high_freq_range,
            high_freq_spacing=symbol_config.high_freq_spacing,
            high_freq_size=symbol_config.high_freq_size,
            
            main_trend_range=symbol_config.main_trend_range,
            main_trend_spacing=symbol_config.main_trend_spacing,
            main_trend_size=symbol_config.main_trend_size,
            
            insurance_range=symbol_config.insurance_range,
            insurance_spacing=symbol_config.insurance_spacing,
            insurance_size=symbol_config.insurance_size,
            
            max_drawdown=symbol_config.max_drawdown,
            stop_loss=symbol_config.stop_loss,
            check_interval=symbol_config.check_interval,
            
            # 继承基础配置
            web_port=self.base_config.web_port,
            binance_api_key=self.base_config.binance_api_key,
            binance_api_secret=self.base_config.binance_api_secret,
            use_testnet=self.base_config.use_testnet,
            telegram_token=self.base_config.telegram_token,
            telegram_chat_id=self.base_config.telegram_chat_id,
            enable_notifications=self.base_config.enable_notifications
        )
    
    async def start_all_symbols(self):
        """启动所有币种的交易"""
        try:
            self.running = True
            self.logger.info("Starting trading for all symbols...")
            
            for symbol, engine in self.symbol_engines.items():
                if self.symbol_configs[symbol].enabled:
                    # 初始化引擎
                    if await engine.initialize():
                        # 启动交易任务
                        task = asyncio.create_task(
                            self._run_symbol_trading(symbol, engine),
                            name=f"trading_{symbol}"
                        )
                        self.symbol_tasks[symbol] = task
                        
                        self.logger.info(f"Started trading for {symbol}")
                    else:
                        self.logger.error(f"Failed to initialize engine for {symbol}")
            
            # 启动全局监控任务
            global_monitor_task = asyncio.create_task(
                self._global_monitoring_loop(),
                name="global_monitor"
            )
            
            # 等待所有任务
            await asyncio.gather(*self.symbol_tasks.values(), global_monitor_task, return_exceptions=True)
            
        except Exception as e:
            self.logger.error(f"Failed to start multi-symbol trading: {e}")
    
    async def _run_symbol_trading(self, symbol: str, engine: GridTradingEngine):
        """运行单个币种的交易"""
        try:
            self.logger.info(f"Starting trading loop for {symbol}")
            await engine.run_trading_loop()
            
        except Exception as e:
            self.logger.error(f"Trading loop error for {symbol}: {e}")
            
            # 标记币种暂时禁用
            self.symbol_configs[symbol].enabled = False
            
            # 记录错误
            await self.db.log_event("ERROR", "MultiSymbolManager", 
                                   f"Trading stopped for {symbol} due to error: {e}")
    
    async def _global_monitoring_loop(self):
        """全局监控循环"""
        while self.running:
            try:
                # 监控各币种状态
                await self._monitor_symbol_performance()
                
                # 检查资金分配是否需要调整
                await self._check_capital_rebalancing()
                
                # 检查是否有币种需要重启
                await self._check_symbol_recovery()
                
                # 每5分钟检查一次
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Global monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_symbol_performance(self):
        """监控各币种表现"""
        try:
            performance_summary = {}
            
            for symbol in self.symbol_configs.keys():
                # 获取币种性能数据
                metrics = self.db.get_performance_metrics()  # 需要扩展支持按symbol查询
                
                performance_summary[symbol] = {
                    "total_pnl": float(metrics.total_pnl),
                    "win_rate": float(metrics.win_rate),
                    "total_trades": metrics.total_trades,
                    "enabled": self.symbol_configs[symbol].enabled
                }
            
            # 记录综合性能
            await self.db.log_event("INFO", "MultiSymbolManager", 
                                   "Multi-symbol performance summary", 
                                   performance_summary)
            
        except Exception as e:
            self.logger.error(f"Performance monitoring failed: {e}")
    
    async def _check_capital_rebalancing(self):
        """检查是否需要资金再平衡"""
        try:
            # 获取当前账户总资金
            account_info = await self.binance.futures_account()
            current_total = Decimal(account_info['totalWalletBalance'])
            
            # 如果总资金变化超过10%，重新分配
            capital_change_ratio = abs(current_total - self.total_capital) / self.total_capital
            
            if capital_change_ratio > Decimal("0.10"):
                self.logger.info(f"Capital changed by {capital_change_ratio:.1%}, rebalancing...")
                
                self.total_capital = current_total
                await self._allocate_capital()
                
                # 通知各引擎调整
                for symbol, engine in self.symbol_engines.items():
                    # 这里需要引擎支持动态调整资金分配
                    pass
            
        except Exception as e:
            self.logger.error(f"Capital rebalancing check failed: {e}")
    
    async def _check_symbol_recovery(self):
        """检查是否有币种需要恢复交易"""
        try:
            for symbol, config in self.symbol_configs.items():
                if not config.enabled:
                    # 检查币种是否可以恢复
                    if await self._can_recover_symbol(symbol):
                        await self._recover_symbol_trading(symbol)
            
        except Exception as e:
            self.logger.error(f"Symbol recovery check failed: {e}")
    
    async def _can_recover_symbol(self, symbol: str) -> bool:
        """检查币种是否可以恢复交易"""
        try:
            # 检查API连接
            ticker = await self.binance.futures_symbol_ticker(symbol=symbol)
            
            # 检查价格是否正常
            price = Decimal(ticker['price'])
            if price <= 0:
                return False
            
            # 检查距离上次错误的时间
            # 这里可以添加更多恢复条件
            
            return True
            
        except Exception as e:
            self.logger.error(f"Recovery check failed for {symbol}: {e}")
            return False
    
    async def _recover_symbol_trading(self, symbol: str):
        """恢复币种交易"""
        try:
            self.logger.info(f"Attempting to recover trading for {symbol}")
            
            # 重新启用币种
            self.symbol_configs[symbol].enabled = True
            
            # 重新初始化引擎
            engine = self.symbol_engines[symbol]
            if await engine.initialize():
                # 启动新的交易任务
                task = asyncio.create_task(
                    self._run_symbol_trading(symbol, engine),
                    name=f"trading_{symbol}_recovery"
                )
                self.symbol_tasks[symbol] = task
                
                self.logger.info(f"Successfully recovered trading for {symbol}")
            else:
                self.symbol_configs[symbol].enabled = False
                self.logger.error(f"Failed to recover trading for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Symbol recovery failed for {symbol}: {e}")
            self.symbol_configs[symbol].enabled = False
    
    async def stop_all_symbols(self):
        """停止所有币种交易"""
        try:
            self.logger.info("Stopping all symbol trading...")
            self.running = False
            
            # 停止所有交易引擎
            for symbol, engine in self.symbol_engines.items():
                engine.stop()
            
            # 取消所有任务
            for task in self.symbol_tasks.values():
                if not task.done():
                    task.cancel()
            
            # 等待任务完成
            await asyncio.gather(*self.symbol_tasks.values(), return_exceptions=True)
            
            self.logger.info("All symbol trading stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop symbol trading: {e}")
    
    def add_symbol(self, symbol: str) -> bool:
        """动态添加新币种"""
        try:
            if symbol in self.symbol_configs:
                self.logger.warning(f"Symbol {symbol} already exists")
                return False
            
            # 创建配置
            config = SymbolConfig(symbol, self.base_config)
            self.symbol_configs[symbol] = config
            
            # 重新分配资金
            asyncio.create_task(self._allocate_capital())
            
            self.logger.info(f"Added new symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add symbol {symbol}: {e}")
            return False
    
    def remove_symbol(self, symbol: str) -> bool:
        """动态移除币种"""
        try:
            if symbol not in self.symbol_configs:
                self.logger.warning(f"Symbol {symbol} not found")
                return False
            
            # 停止交易
            if symbol in self.symbol_engines:
                self.symbol_engines[symbol].stop()
            
            # 取消任务
            if symbol in self.symbol_tasks:
                self.symbol_tasks[symbol].cancel()
            
            # 移除配置
            del self.symbol_configs[symbol]
            if symbol in self.symbol_engines:
                del self.symbol_engines[symbol]
            if symbol in self.symbol_tasks:
                del self.symbol_tasks[symbol]
            if symbol in self.symbol_capital_allocation:
                del self.symbol_capital_allocation[symbol]
            
            self.logger.info(f"Removed symbol: {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove symbol {symbol}: {e}")
            return False
    
    def get_multi_symbol_status(self) -> Dict[str, any]:
        """获取多币种状态"""
        try:
            status = {
                "total_symbols": len(self.symbol_configs),
                "active_symbols": sum(1 for config in self.symbol_configs.values() if config.enabled),
                "total_capital": float(self.total_capital),
                "symbols": {}
            }
            
            for symbol, config in self.symbol_configs.items():
                engine = self.symbol_engines.get(symbol)
                
                status["symbols"][symbol] = {
                    "enabled": config.enabled,
                    "allocated_capital": float(self.symbol_capital_allocation.get(symbol, 0)),
                    "allocation_ratio": float(config.capital_allocation_ratio),
                    "running": engine.running if engine else False,
                    "current_price": float(engine.current_price) if engine else 0,
                    "active_orders": len(self.db.get_active_orders()) if engine else 0  # 需要按symbol过滤
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get multi-symbol status: {e}")
            return {}

# 使用示例配置
MULTI_SYMBOL_CONFIG = {
    "symbols": [
        "BTCUSDT",   # 比特币
        "ETHUSDT",   # 以太坊
        "BNBUSDT",   # BNB
        "ADAUSDT",   # 卡尔达诺
        "SOLUSDT",   # Solana
    ],
    "capital_distribution": "auto",  # auto / manual
    "max_concurrent_symbols": 5,
    "symbol_rotation_enabled": True,  # 是否启用币种轮换
    "performance_threshold": 0.02     # 表现阈值，低于此值考虑轮换
}