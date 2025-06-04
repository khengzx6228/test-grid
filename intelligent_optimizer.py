# intelligent_optimizer.py - 智能参数动态调优模块
import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from data_models import GridLevel, TradingConfig, MarketState
from database_manager import DatabaseManager

class TechnicalIndicators:
    """技术指标计算器"""
    
    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """计算平均真实波幅 (ATR)"""
        if len(closes) < period + 1:
            return 0.02  # 默认2%
        
        true_ranges = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            
            true_range = max(high_low, high_close, low_close)
            true_ranges.append(true_range)
        
        # 计算ATR
        if len(true_ranges) >= period:
            atr = sum(true_ranges[-period:]) / period
            return atr / closes[-1]  # 转换为百分比
        
        return 0.02
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """计算相对强弱指数 (RSI)"""
        if len(prices) < period + 1:
            return 50.0  # 默认中性
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) >= period:
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        
        return 50.0
    
    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2) -> Tuple[float, float, float]:
        """计算布林带"""
        if len(prices) < period:
            price = prices[-1] if prices else 50000
            return price, price * 1.02, price * 0.98
        
        recent_prices = prices[-period:]
        mean_price = sum(recent_prices) / len(recent_prices)
        
        variance = sum((p - mean_price) ** 2 for p in recent_prices) / len(recent_prices)
        std = variance ** 0.5
        
        upper_band = mean_price + (std_dev * std)
        lower_band = mean_price - (std_dev * std)
        
        return mean_price, upper_band, lower_band
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        """计算指数移动平均线"""
        if len(prices) < period:
            return sum(prices) / len(prices) if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def calculate_macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[float, float, float]:
        """计算MACD"""
        if len(prices) < slow_period:
            return 0, 0, 0
        
        ema_fast = TechnicalIndicators.calculate_ema(prices, fast_period)
        ema_slow = TechnicalIndicators.calculate_ema(prices, slow_period)
        
        macd_line = ema_fast - ema_slow
        
        # 简化的信号线计算
        signal_line = macd_line * 0.9  # 简化处理
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram

class MarketStateAnalyzer:
    """市场状态分析器"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze_market_state(self, market_data: Dict[str, List[float]]) -> Dict[str, any]:
        """综合分析市场状态"""
        prices = market_data.get('closes', [])
        highs = market_data.get('highs', [])
        lows = market_data.get('lows', [])
        volumes = market_data.get('volumes', [])
        
        if not prices:
            return self._default_market_state()
        
        # 计算技术指标
        atr = self.indicators.calculate_atr(highs, lows, prices)
        rsi = self.indicators.calculate_rsi(prices)
        bb_mid, bb_upper, bb_lower = self.indicators.calculate_bollinger_bands(prices)
        macd, signal, histogram = self.indicators.calculate_macd(prices)
        
        # 计算价格位置（相对于布林带）
        current_price = prices[-1]
        bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(prices)
        
        # 计算波动率等级
        volatility_level = self._classify_volatility(atr)
        
        # 计算市场状态
        market_state = self._determine_market_state(rsi, bb_position, macd, trend_strength, volatility_level)
        
        # 计算支撑阻力位
        support_resistance = self._calculate_support_resistance(prices, highs, lows)
        
        return {
            'market_state': market_state,
            'volatility_level': volatility_level,
            'trend_strength': trend_strength,
            'atr_percent': atr * 100,
            'rsi': rsi,
            'bb_position': bb_position,
            'macd_signal': 'bullish' if macd > signal else 'bearish',
            'price_momentum': self._calculate_momentum(prices),
            'support_resistance': support_resistance,
            'volume_trend': self._analyze_volume_trend(volumes),
            'market_efficiency': self._calculate_market_efficiency(prices),
            'recommended_adjustments': self._get_strategy_recommendations(
                market_state, volatility_level, trend_strength, atr
            )
        }
    
    def _default_market_state(self) -> Dict[str, any]:
        """默认市场状态"""
        return {
            'market_state': 'sideways',
            'volatility_level': 'medium',
            'trend_strength': 0.0,
            'atr_percent': 2.0,
            'rsi': 50.0,
            'bb_position': 0.5,
            'macd_signal': 'neutral',
            'recommended_adjustments': {}
        }
    
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """计算趋势强度"""
        if len(prices) < 20:
            return 0.0
        
        # 使用线性回归计算趋势强度
        x = list(range(len(prices)))
        n = len(prices)
        
        sum_x = sum(x)
        sum_y = sum(prices)
        sum_xy = sum(x[i] * prices[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)
        
        # 计算回归系数
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        # 归一化趋势强度
        price_range = max(prices) - min(prices)
        trend_strength = abs(slope * n) / price_range if price_range > 0 else 0
        
        return min(trend_strength, 1.0)
    
    def _classify_volatility(self, atr: float) -> str:
        """分类波动率等级"""
        if atr > 0.08:
            return 'very_high'
        elif atr > 0.05:
            return 'high'
        elif atr > 0.03:
            return 'medium'
        elif atr > 0.015:
            return 'low'
        else:
            return 'very_low'
    
    def _determine_market_state(self, rsi: float, bb_position: float, macd: float, 
                               trend_strength: float, volatility_level: str) -> str:
        """确定市场状态"""
        # 超买超卖判断
        if rsi > 80 or bb_position > 0.9:
            return 'overbought'
        elif rsi < 20 or bb_position < 0.1:
            return 'oversold'
        
        # 趋势判断
        if trend_strength > 0.6:
            if macd > 0:
                return 'strong_uptrend'
            else:
                return 'strong_downtrend'
        elif trend_strength > 0.3:
            if macd > 0:
                return 'uptrend'
            else:
                return 'downtrend'
        
        # 波动率判断
        if volatility_level in ['very_high', 'high']:
            return 'high_volatility'
        
        # 默认震荡
        return 'sideways'
    
    def _calculate_momentum(self, prices: List[float]) -> float:
        """计算价格动量"""
        if len(prices) < 10:
            return 0.0
        
        recent_change = (prices[-1] - prices[-5]) / prices[-5]
        return recent_change * 100
    
    def _calculate_support_resistance(self, prices: List[float], highs: List[float], lows: List[float]) -> Dict[str, float]:
        """计算支撑阻力位"""
        if not prices:
            return {'support': 0, 'resistance': 0}
        
        # 简化的支撑阻力计算
        recent_highs = highs[-20:] if len(highs) >= 20 else highs
        recent_lows = lows[-20:] if len(lows) >= 20 else lows
        
        resistance = max(recent_highs) if recent_highs else prices[-1]
        support = min(recent_lows) if recent_lows else prices[-1]
        
        return {
            'support': support,
            'resistance': resistance,
            'support_strength': self._calculate_level_strength(prices, support),
            'resistance_strength': self._calculate_level_strength(prices, resistance)
        }
    
    def _calculate_level_strength(self, prices: List[float], level: float) -> float:
        """计算支撑/阻力位强度"""
        # 计算价格接近该水平的次数
        tolerance = level * 0.02  # 2%容差
        touches = sum(1 for price in prices if abs(price - level) <= tolerance)
        
        return min(touches / 10, 1.0)  # 归一化到0-1
    
    def _analyze_volume_trend(self, volumes: List[float]) -> str:
        """分析成交量趋势"""
        if len(volumes) < 10:
            return 'neutral'
        
        recent_volume = sum(volumes[-5:]) / 5
        previous_volume = sum(volumes[-10:-5]) / 5
        
        if recent_volume > previous_volume * 1.2:
            return 'increasing'
        elif recent_volume < previous_volume * 0.8:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_market_efficiency(self, prices: List[float]) -> float:
        """计算市场效率（价格连续性）"""
        if len(prices) < 5:
            return 0.5
        
        # 计算价格变化的方差
        changes = [abs(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        if not changes:
            return 0.5
        
        avg_change = sum(changes) / len(changes)
        
        # 效率越高，价格变化越平滑
        efficiency = 1 - min(avg_change * 10, 1.0)
        
        return efficiency
    
    def _get_strategy_recommendations(self, market_state: str, volatility_level: str, 
                                    trend_strength: float, atr: float) -> Dict[str, any]:
        """获取策略调整建议"""
        recommendations = {
            'grid_spacing_multiplier': 1.0,
            'order_size_multiplier': 1.0,
            'grid_range_multiplier': 1.0,
            'enable_levels': [True, True, True],  # [high_freq, main_trend, insurance]
            'risk_adjustment': 1.0
        }
        
        # 根据市场状态调整
        if market_state in ['strong_uptrend', 'strong_downtrend']:
            recommendations['grid_spacing_multiplier'] = 1.3  # 增加间距
            recommendations['order_size_multiplier'] = 0.8   # 减少订单大小
            recommendations['enable_levels'][0] = False      # 关闭高频层
            
        elif market_state in ['overbought', 'oversold']:
            recommendations['grid_spacing_multiplier'] = 0.8  # 减少间距
            recommendations['order_size_multiplier'] = 1.2   # 增加订单大小
            
        elif market_state == 'high_volatility':
            recommendations['grid_spacing_multiplier'] = 1.5  # 大幅增加间距
            recommendations['order_size_multiplier'] = 0.7   # 减少订单大小
            recommendations['risk_adjustment'] = 0.8         # 降低风险
            
        # 根据波动率调整
        volatility_multipliers = {
            'very_low': {'spacing': 0.7, 'size': 1.2},
            'low': {'spacing': 0.8, 'size': 1.1},
            'medium': {'spacing': 1.0, 'size': 1.0},
            'high': {'spacing': 1.3, 'size': 0.8},
            'very_high': {'spacing': 1.6, 'size': 0.6}
        }
        
        if volatility_level in volatility_multipliers:
            mult = volatility_multipliers[volatility_level]
            recommendations['grid_spacing_multiplier'] *= mult['spacing']
            recommendations['order_size_multiplier'] *= mult['size']
        
        # 根据ATR调整网格范围
        if atr > 0.1:  # 高波动
            recommendations['grid_range_multiplier'] = 1.4
        elif atr < 0.02:  # 低波动
            recommendations['grid_range_multiplier'] = 0.8
        
        return recommendations

class IntelligentOptimizer:
    """智能参数优化器"""
    
    def __init__(self, binance_client, db_manager: DatabaseManager):
        self.binance = binance_client
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        self.market_analyzer = MarketStateAnalyzer()
        
        # 优化参数
        self.optimization_interval = 3600  # 1小时优化一次
        self.data_window_hours = 168       # 7天数据窗口
        self.min_trades_for_optimization = 20  # 最少交易次数才进行优化
        
        # 历史表现追踪
        self.parameter_performance_history = {}
        self.last_optimization_time = {}
        
    async def start_optimization(self, symbols: List[str]):
        """启动智能优化"""
        self.logger.info("Starting intelligent parameter optimization...")
        
        while True:
            try:
                for symbol in symbols:
                    await self._optimize_symbol_parameters(symbol)
                
                # 等待下次优化
                await asyncio.sleep(self.optimization_interval)
                
            except Exception as e:
                self.logger.error(f"Optimization error: {e}")
                await asyncio.sleep(600)  # 出错时10分钟后重试
    
    async def _optimize_symbol_parameters(self, symbol: str):
        """优化单个币种的参数"""
        try:
            self.logger.info(f"Optimizing parameters for {symbol}")
            
            # 获取市场数据
            market_data = await self._collect_market_data(symbol)
            
            # 分析市场状态
            market_analysis = self.market_analyzer.analyze_market_state(market_data)
            
            # 获取当前交易表现
            performance_data = await self._get_trading_performance(symbol)
            
            # 检查是否需要优化
            if not self._should_optimize(symbol, performance_data):
                self.logger.debug(f"Skipping optimization for {symbol} - insufficient data")
                return
            
            # 生成优化建议
            optimization_suggestions = await self._generate_optimization_suggestions(
                symbol, market_analysis, performance_data
            )
            
            # 应用优化
            if optimization_suggestions:
                await self._apply_optimizations(symbol, optimization_suggestions)
                
                # 记录优化历史
                await self._record_optimization_history(symbol, optimization_suggestions, market_analysis)
            
            self.last_optimization_time[symbol] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Failed to optimize parameters for {symbol}: {e}")
    
    async def _collect_market_data(self, symbol: str) -> Dict[str, List[float]]:
        """收集市场数据"""
        try:
            # 获取K线数据
            klines = await self.binance.futures_klines(
                symbol=symbol,
                interval='1h',
                limit=self.data_window_hours
            )
            
            market_data = {
                'opens': [float(k[1]) for k in klines],
                'highs': [float(k[2]) for k in klines],
                'lows': [float(k[3]) for k in klines],
                'closes': [float(k[4]) for k in klines],
                'volumes': [float(k[5]) for k in klines]
            }
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Failed to collect market data for {symbol}: {e}")
            return {}
    
    async def _get_trading_performance(self, symbol: str) -> Dict[str, any]:
        """获取交易表现数据"""
        try:
            # 获取最近的交易记录
            trades = self.db.get_trades(days=7)  # 需要扩展支持按symbol筛选
            
            if not trades:
                return {}
            
            # 计算表现指标
            total_trades = len(trades)
            winning_trades = sum(1 for trade in trades if trade.profit > 0)
            total_profit = sum(trade.profit for trade in trades)
            avg_profit_per_trade = total_profit / total_trades if total_trades > 0 else 0
            
            # 按网格层级统计
            level_performance = {}
            for level in GridLevel:
                level_trades = [t for t in trades if t.grid_level == level]
                if level_trades:
                    level_profit = sum(t.profit for t in level_trades)
                    level_performance[level.value] = {
                        'trades': len(level_trades),
                        'profit': float(level_profit),
                        'avg_profit': float(level_profit / len(level_trades))
                    }
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
                'total_profit': float(total_profit),
                'avg_profit_per_trade': float(avg_profit_per_trade),
                'level_performance': level_performance,
                'sharpe_ratio': self._calculate_sharpe_ratio(trades),
                'max_consecutive_losses': self._calculate_max_consecutive_losses(trades)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get trading performance for {symbol}: {e}")
            return {}
    
    def _calculate_sharpe_ratio(self, trades) -> float:
        """计算夏普比率"""
        if len(trades) < 10:
            return 0.0
        
        returns = [float(trade.profit) for trade in trades]
        
        if not returns:
            return 0.0
        
        avg_return = sum(returns) / len(returns)
        
        if len(returns) < 2:
            return 0.0
        
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        # 简化的夏普比率计算
        sharpe = avg_return / std_dev
        
        return sharpe
    
    def _calculate_max_consecutive_losses(self, trades) -> int:
        """计算最大连续亏损次数"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.profit <= 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _should_optimize(self, symbol: str, performance_data: Dict[str, any]) -> bool:
        """判断是否应该进行优化"""
        # 检查是否有足够的交易数据
        if performance_data.get('total_trades', 0) < self.min_trades_for_optimization:
            return False
        
        # 检查距离上次优化的时间
        last_optimization = self.last_optimization_time.get(symbol)
        if last_optimization:
            time_since_optimization = (datetime.now() - last_optimization).total_seconds() / 3600
            if time_since_optimization < self.optimization_interval / 3600:
                return False
        
        # 检查表现是否需要优化
        win_rate = performance_data.get('win_rate', 0)
        avg_profit = performance_data.get('avg_profit_per_trade', 0)
        sharpe_ratio = performance_data.get('sharpe_ratio', 0)
        
        # 如果表现较差，需要优化
        if win_rate < 0.6 or avg_profit < 0 or sharpe_ratio < 0.5:
            return True
        
        # 定期优化
        return True
    
    async def _generate_optimization_suggestions(self, symbol: str, market_analysis: Dict[str, any], 
                                               performance_data: Dict[str, any]) -> Dict[str, any]:
        """生成优化建议"""
        try:
            suggestions = {}
            
            # 从市场分析获取建议
            market_recommendations = market_analysis.get('recommended_adjustments', {})
            
            # 根据交易表现调整
            performance_adjustments = self._analyze_performance_issues(performance_data)
            
            # 合并建议
            suggestions.update(market_recommendations)
            suggestions.update(performance_adjustments)
            
            # 添加币种特定调整
            symbol_specific = await self._get_symbol_specific_adjustments(symbol, market_analysis)
            suggestions.update(symbol_specific)
            
            # 验证建议的合理性
            validated_suggestions = self._validate_suggestions(suggestions)
            
            return validated_suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to generate optimization suggestions: {e}")
            return {}
    
    def _analyze_performance_issues(self, performance_data: Dict[str, any]) -> Dict[str, any]:
        """分析表现问题并提供调整建议"""
        adjustments = {}
        
        win_rate = performance_data.get('win_rate', 0)
        avg_profit = performance_data.get('avg_profit_per_trade', 0)
        max_consecutive_losses = performance_data.get('max_consecutive_losses', 0)
        
        # 胜率过低
        if win_rate < 0.5:
            adjustments['grid_spacing_multiplier'] = 0.8  # 减少间距提高成交率
            adjustments['order_size_multiplier'] = 1.1    # 适当增加订单大小
        
        # 平均利润过低
        if avg_profit < 0:
            adjustments['grid_spacing_multiplier'] = 1.2  # 增加间距提高利润
            adjustments['order_size_multiplier'] = 0.9    # 减少风险
            adjustments['risk_adjustment'] = 0.8          # 降低整体风险
        
        # 连续亏损过多
        if max_consecutive_losses > 5:
            adjustments['grid_spacing_multiplier'] = 1.3  # 大幅增加间距
            adjustments['order_size_multiplier'] = 0.7    # 减少订单大小
            adjustments['risk_adjustment'] = 0.7          # 大幅降低风险
        
        # 分析各层级表现
        level_performance = performance_data.get('level_performance', {})
        
        for level_name, perf in level_performance.items():
            if perf['avg_profit'] < 0:
                # 该层级表现不佳，建议暂时禁用或调整
                level_key = f"{level_name}_enabled"
                adjustments[level_key] = False
        
        return adjustments
    
    async def _get_symbol_specific_adjustments(self, symbol: str, market_analysis: Dict[str, any]) -> Dict[str, any]:
        """获取币种特定调整"""
        adjustments = {}
        
        try:
            # 获取币种的24小时统计
            ticker_24h = await self.binance.futures_24hr_ticker(symbol=symbol)
            
            price_change_percent = float(ticker_24h['priceChangePercent'])
            volume = float(ticker_24h['volume'])
            
            # 根据24小时价格变化调整
            if abs(price_change_percent) > 10:  # 大幅波动
                adjustments['grid_spacing_multiplier'] = 1.5
                adjustments['order_size_multiplier'] = 0.7
            
            # 根据成交量调整
            # 低成交量时更保守
            if volume < 1000000:  # 根据具体币种调整阈值
                adjustments['order_size_multiplier'] = 0.8
                adjustments['risk_adjustment'] = 0.9
            
            # 特定币种的特殊处理
            if symbol == "BTCUSDT":
                # BTC作为主流币种，可以相对激进
                adjustments['order_size_multiplier'] = adjustments.get('order_size_multiplier', 1.0) * 1.1
            elif symbol in ["DOGEUSDT", "SHIBUSDT"]:
                # 高风险币种，更保守
                adjustments['order_size_multiplier'] = adjustments.get('order_size_multiplier', 1.0) * 0.8
                adjustments['risk_adjustment'] = 0.8
            
        except Exception as e:
            self.logger.error(f"Failed to get symbol specific adjustments: {e}")
        
        return adjustments
    
    def _validate_suggestions(self, suggestions: Dict[str, any]) -> Dict[str, any]:
        """验证建议的合理性"""
        validated = {}
        
        # 限制调整幅度
        spacing_multiplier = suggestions.get('grid_spacing_multiplier', 1.0)
        validated['grid_spacing_multiplier'] = max(0.5, min(2.0, spacing_multiplier))
        
        size_multiplier = suggestions.get('order_size_multiplier', 1.0)
        validated['order_size_multiplier'] = max(0.3, min(2.0, size_multiplier))
        
        range_multiplier = suggestions.get('grid_range_multiplier', 1.0)
        validated['grid_range_multiplier'] = max(0.7, min(1.5, range_multiplier))
        
        risk_adjustment = suggestions.get('risk_adjustment', 1.0)
        validated['risk_adjustment'] = max(0.5, min(1.2, risk_adjustment))
        
        # 保留启用/禁用建议
        if 'enable_levels' in suggestions:
            validated['enable_levels'] = suggestions['enable_levels']
        
        # 保留层级特定设置
        for key, value in suggestions.items():
            if key.endswith('_enabled'):
                validated[key] = value
        
        return validated
    
    async def _apply_optimizations(self, symbol: str, suggestions: Dict[str, any]):
        """应用优化建议"""
        try:
            self.logger.info(f"Applying optimizations for {symbol}: {suggestions}")
            
            # 记录优化事件
            await self.db.log_event("INFO", "IntelligentOptimizer",
                                   f"Applying parameter optimizations for {symbol}",
                                   suggestions)
            
            # 这里需要与GridTradingEngine集成，实际应用参数调整
            # 由于我们的架构，这部分需要通过配置更新或直接调用引擎方法实现
            
            # 发送优化通知（如果启用了通知服务）
            await self._send_optimization_notification(symbol, suggestions)
            
        except Exception as e:
            self.logger.error(f"Failed to apply optimizations for {symbol}: {e}")
    
    async def _send_optimization_notification(self, symbol: str, suggestions: Dict[str, any]):
        """发送优化通知"""
        try:
            # 这里可以集成通知服务
            message = f"🔧 参数优化 - {symbol}\n\n"
            
            if 'grid_spacing_multiplier' in suggestions:
                multiplier = suggestions['grid_spacing_multiplier']
                change = "增加" if multiplier > 1 else "减少"
                message += f"• 网格间距: {change} {abs(multiplier - 1) * 100:.0f}%\n"
            
            if 'order_size_multiplier' in suggestions:
                multiplier = suggestions['order_size_multiplier']
                change = "增加" if multiplier > 1 else "减少"
                message += f"• 订单大小: {change} {abs(multiplier - 1) * 100:.0f}%\n"
            
            if 'risk_adjustment' in suggestions:
                adjustment = suggestions['risk_adjustment']
                if adjustment < 1:
                    message += f"• 风险控制: 加强 {(1 - adjustment) * 100:.0f}%\n"
            
            # 实际发送需要集成NotificationService
            self.logger.info(f"Optimization notification: {message}")
            
        except Exception as e:
            self.logger.error(f"Failed to send optimization notification: {e}")
    
    async def _record_optimization_history(self, symbol: str, suggestions: Dict[str, any], 
                                         market_analysis: Dict[str, any]):
        """记录优化历史"""
        try:
            optimization_record = {
                'symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'suggestions': suggestions,
                'market_state': market_analysis.get('market_state'),
                'volatility_level': market_analysis.get('volatility_level'),
                'atr_percent': market_analysis.get('atr_percent')
            }
            
            # 保存到历史记录
            if symbol not in self.parameter_performance_history:
                self.parameter_performance_history[symbol] = []
            
            self.parameter_performance_history[symbol].append(optimization_record)
            
            # 限制历史记录数量
            if len(self.parameter_performance_history[symbol]) > 100:
                self.parameter_performance_history[symbol] = self.parameter_performance_history[symbol][-100:]
            
            # 记录到数据库
            await self.db.log_event("INFO", "IntelligentOptimizer",
                                   f"Parameter optimization history recorded for {symbol}",
                                   optimization_record)
            
        except Exception as e:
            self.logger.error(f"Failed to record optimization history: {e}")
    
    def get_optimization_status(self) -> Dict[str, any]:
        """获取优化状态"""
        return {
            'optimization_interval_hours': self.optimization_interval / 3600,
            'data_window_hours': self.data_window_hours,
            'min_trades_threshold': self.min_trades_for_optimization,
            'symbols_optimized': list(self.last_optimization_time.keys()),
            'last_optimization_times': {
                symbol: time.isoformat() 
                for symbol, time in self.last_optimization_time.items()
            }
        }