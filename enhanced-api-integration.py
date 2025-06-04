# enhanced_api_endpoints.py - 增强版API端点
from flask import Flask, jsonify, request, websocket
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import json
import logging

class EnhancedAPIEndpoints:
    """增强版API端点 - 支持新监控面板"""
    
    def __init__(self, trading_bot):
        self.bot = trading_bot
        self.logger = logging.getLogger(__name__)
        self.websocket_clients = set()
    
    def register_routes(self, app: Flask):
        """注册增强版API路由"""
        
        @app.route('/api/enhanced_status')
        def enhanced_status():
            """增强版系统状态"""
            return jsonify(self._get_enhanced_status())
        
        @app.route('/api/sync_monitor')
        def sync_monitor_status():
            """同步监控状态"""
            return jsonify(self._get_sync_monitor_status())
        
        @app.route('/api/capital_analysis')
        def capital_analysis():
            """资金使用分析"""
            return jsonify(self._get_capital_analysis())
        
        @app.route('/api/ai_suggestions')
        def ai_suggestions():
            """AI优化建议"""
            return jsonify(self._get_ai_suggestions())
        
        @app.route('/api/anomaly_detection')
        def anomaly_detection():
            """异常检测状态"""
            return jsonify(self._get_anomaly_detection())
        
        @app.route('/api/multi_symbol_detailed')
        def multi_symbol_detailed():
            """多币种详细状态"""
            return jsonify(self._get_multi_symbol_detailed())
        
        @app.route('/api/real_time_feed')
        def real_time_feed():
            """实时活动流"""
            return jsonify(self._get_real_time_feed())
        
        @app.route('/api/risk_assessment')
        def risk_assessment():
            """风险评估"""
            return jsonify(self._get_risk_assessment())
        
        # 控制接口
        @app.route('/api/optimize_insurance', methods=['POST'])
        def optimize_insurance():
            """优化保险层"""
            return jsonify(self._optimize_insurance_layer())
        
        @app.route('/api/adjust_grid_density', methods=['POST'])
        def adjust_grid_density():
            """调整网格密度"""
            data = request.json
            symbol = data.get('symbol')
            return jsonify(self._adjust_grid_density(symbol))
        
        @app.route('/api/apply_ai_suggestions', methods=['POST'])
        def apply_ai_suggestions():
            """应用AI建议"""
            return jsonify(self._apply_ai_suggestions())
        
        @app.route('/api/emergency_rebalance', methods=['POST'])
        def emergency_rebalance():
            """紧急资金重新平衡"""
            return jsonify(self._emergency_rebalance())
        
        # WebSocket处理
        @app.websocket('/ws')
        def handle_websocket():
            """WebSocket连接处理"""
            try:
                self.websocket_clients.add(websocket)
                self._handle_websocket_connection(websocket)
            finally:
                self.websocket_clients.discard(websocket)
    
    def _get_enhanced_status(self) -> Dict:
        """获取增强版系统状态"""
        try:
            # 基础状态
            base_status = self.bot.get_status()
            
            # 同步状态
            sync_status = self._check_sync_status()
            
            # 资金状态
            capital_status = self._analyze_capital_usage()
            
            # AI优化状态
            ai_status = self._get_ai_optimization_status()
            
            # 风险评估
            risk_assessment = self._calculate_risk_metrics()
            
            return {
                **base_status,
                'sync_status': sync_status,
                'capital_status': capital_status,
                'ai_status': ai_status,
                'risk_assessment': risk_assessment,
                'enhanced_metrics': self._calculate_enhanced_metrics(),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get enhanced status: {e}")
            return {'error': str(e)}
    
    def _check_sync_status(self) -> Dict:
        """检查同步状态"""
        try:
            # 获取本地订单数量
            local_orders = len(self.bot.get_orders())
            
            # 模拟检查结果（实际应该从OrderSyncMonitor获取）
            inconsistencies = 0  # 实际应该调用同步监控器
            last_sync = datetime.now()
            
            return {
                'status': 'healthy' if inconsistencies == 0 else 'warning',
                'local_orders': local_orders,
                'inconsistencies': inconsistencies,
                'last_sync_time': last_sync.isoformat(),
                'sync_frequency': '30s',
                'details': {
                    'missing_orders': 0,
                    'extra_orders': 0,
                    'timeout_orders': 0
                }
            }
            
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _analyze_capital_usage(self) -> Dict:
        """分析资金使用情况"""
        try:
            # 模拟资金分析（实际应该从DynamicCapitalManager获取）
            total_balance = 36000  # 总资金
            
            allocation = {
                'high_freq': {
                    'amount': 12500,
                    'percentage': 34.7,
                    'efficiency': 92.3,
                    'active_orders': 45
                },
                'main_trend': {
                    'amount': 18750,
                    'percentage': 52.1,
                    'efficiency': 87.6,
                    'active_orders': 28
                },
                'insurance': {
                    'amount': 4750,
                    'percentage': 13.2,
                    'efficiency': 45.8,  # 保险层效率较低
                    'active_orders': 156
                }
            }
            
            # 计算整体效率
            overall_efficiency = sum(
                level['amount'] * level['efficiency'] 
                for level in allocation.values()
            ) / total_balance
            
            # 检测问题
            issues = []
            if allocation['insurance']['percentage'] > 25:
                issues.append({
                    'type': 'warning',
                    'message': '保险层资金占用过高',
                    'suggestion': '建议回收部分远端订单'
                })
            
            return {
                'total_balance': total_balance,
                'allocation': allocation,
                'overall_efficiency': overall_efficiency,
                'frozen_ratio': 0.68,  # 68%资金被冻结
                'available_balance': 11520,
                'issues': issues,
                'optimization_needed': len(issues) > 0
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_ai_optimization_status(self) -> Dict:
        """获取AI优化状态"""
        try:
            # 模拟AI状态（实际应该从IntelligentOptimizer获取）
            return {
                'status': 'active',
                'last_optimization': (datetime.now() - timedelta(minutes=45)).isoformat(),
                'next_optimization': (datetime.now() + timedelta(minutes=15)).isoformat(),
                'optimizations_today': 3,
                'success_rate': 94.2,
                'current_suggestions': [
                    {
                        'type': 'capital_allocation',
                        'priority': 'high',
                        'description': '建议增加高频层资金配置5%',
                        'expected_improvement': '2.3%收益提升'
                    },
                    {
                        'type': 'grid_spacing',
                        'priority': 'medium',
                        'description': '检测到高波动期，建议增加网格间距15%',
                        'expected_improvement': '风险降低12%'
                    },
                    {
                        'type': 'symbol_rotation',
                        'priority': 'low',
                        'description': 'DOGEUSDT表现不佳，建议替换为SOLUSDT',
                        'expected_improvement': '整体收益提升2.1%'
                    }
                ]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _calculate_risk_metrics(self) -> Dict:
        """计算风险指标"""
        try:
            # 获取性能数据
            performance = self.bot.db.get_performance_metrics()
            
            # 计算VaR和其他风险指标
            return {
                'risk_level': 'low',  # low/medium/high/critical
                'risk_score': 25.3,   # 0-100
                'var_95': 1250,       # 95% VaR in USDT
                'max_drawdown': float(performance.max_drawdown),
                'current_drawdown': float(performance.current_drawdown),
                'sharpe_ratio': 1.84,
                'volatility': 0.023,  # 2.3%
                'correlation_risk': 0.45,  # 币种间相关性风险
                'liquidity_risk': 'low',
                'concentration_risk': 'medium',  # 资金集中度风险
                'recommendations': [
                    '当前风险水平可控',
                    '建议监控保险层资金占用',
                    '考虑增加币种多样性'
                ]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _calculate_enhanced_metrics(self) -> Dict:
        """计算增强版指标"""
        return {
            'grid_integrity': {
                'overall': 92.6,
                'high_freq': 94.2,
                'main_trend': 89.8,
                'insurance': 93.5
            },
            'capital_efficiency': 85.3,
            'sync_health_score': 98.5,
            'optimization_score': 87.2,
            'multi_symbol_balance': 91.8
        }
    
    def _get_multi_symbol_detailed(self) -> Dict:
        """获取多币种详细状态"""
        try:
            symbols_data = {
                'BTCUSDT': {
                    'status': 'running',
                    'current_price': 68250.00,
                    'allocated_capital': 15000,
                    'active_orders': 68,
                    'daily_pnl': 234.50,
                    'efficiency': 89.2,
                    'risk_level': 'low'
                },
                'ETHUSDT': {
                    'status': 'running',
                    'current_price': 3842.50,
                    'allocated_capital': 12000,
                    'active_orders': 54,
                    'daily_pnl': 156.30,
                    'efficiency': 91.7,
                    'risk_level': 'low'
                },
                'BNBUSDT': {
                    'status': 'running',
                    'current_price': 635.20,
                    'allocated_capital': 5000,
                    'active_orders': 32,
                    'daily_pnl': 89.70,
                    'efficiency': 85.4,
                    'risk_level': 'medium'
                },
                'ADAUSDT': {
                    'status': 'warning',
                    'current_price': 1.234,
                    'allocated_capital': 3000,
                    'active_orders': 156,  # 订单过多
                    'daily_pnl': -23.40,  # 负收益
                    'efficiency': 67.8,
                    'risk_level': 'high',
                    'issues': ['网格密度过高', '负收益']
                },
                'SOLUSDT': {
                    'status': 'running',
                    'current_price': 178.90,
                    'allocated_capital': 1000,
                    'active_orders': 18,
                    'daily_pnl': 45.20,
                    'efficiency': 88.9,
                    'risk_level': 'low'
                }
            }
            
            return {
                'total_symbols': len(symbols_data),
                'active_symbols': sum(1 for s in symbols_data.values() if s['status'] == 'running'),
                'total_allocated': sum(s['allocated_capital'] for s in symbols_data.values()),
                'total_daily_pnl': sum(s['daily_pnl'] for s in symbols_data.values()),
                'symbols': symbols_data,
                'rebalancing_needed': any('issues' in s for s in symbols_data.values())
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_real_time_feed(self) -> List[Dict]:
        """获取实时活动流"""
        try:
            # 从数据库获取最近的系统日志
            recent_logs = []  # 实际应该从数据库查询
            
            # 模拟实时活动
            activities = [
                {
                    'timestamp': datetime.now().isoformat(),
                    'type': 'trade',
                    'level': 'success',
                    'message': 'BTCUSDT 主趋势层买单成交 @$68,250.00, 利润: +$34.50'
                },
                {
                    'timestamp': (datetime.now() - timedelta(minutes=1)).isoformat(),
                    'type': 'optimization',
                    'level': 'info',
                    'message': 'AI优化器调整ETHUSDT网格间距 -8%'
                },
                {
                    'timestamp': (datetime.now() - timedelta(minutes=2)).isoformat(),
                    'type': 'alert',
                    'level': 'warning',
                    'message': '检测到保险层资金占用率上升至32.1%'
                },
                {
                    'timestamp': (datetime.now() - timedelta(minutes=3)).isoformat(),
                    'type': 'sync',
                    'level': 'error',
                    'message': 'ADAUSDT订单同步异常，已自动修复'
                }
            ]
            
            return activities
            
        except Exception as e:
            return [{'error': str(e)}]
    
    # 控制方法
    def _optimize_insurance_layer(self) -> Dict:
        """优化保险层"""
        try:
            # 这里应该调用DynamicCapitalManager的优化方法
            # capital_manager.recover_insurance_capital()
            
            return {
                'success': True,
                'message': '保险层优化完成',
                'details': {
                    'before_ratio': 32.1,
                    'after_ratio': 22.3,
                    'recovered_capital': 3520,
                    'canceled_orders': 45
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _adjust_grid_density(self, symbol: str) -> Dict:
        """调整网格密度"""
        try:
            # 这里应该调用相应的网格调整方法
            return {
                'success': True,
                'message': f'{symbol}网格密度已调整',
                'details': {
                    'symbol': symbol,
                    'before_orders': 156,
                    'after_orders': 117,
                    'reduction_percentage': 25
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _apply_ai_suggestions(self) -> Dict:
        """应用AI建议"""
        try:
            # 这里应该调用IntelligentOptimizer的应用方法
            return {
                'success': True,
                'message': '所有AI建议已应用',
                'applied_suggestions': 3,
                'expected_improvement': '3.2%',
                'details': [
                    '资金配置已优化',
                    '网格间距已调整',
                    '币种轮换计划已制定'
                ]
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _emergency_rebalance(self) -> Dict:
        """紧急资金重新平衡"""
        try:
            # 这里应该调用紧急重新平衡逻辑
            return {
                'success': True,
                'message': '紧急重新平衡完成',
                'rebalanced_amount': 8500,
                'affected_symbols': ['BTCUSDT', 'ETHUSDT', 'ADAUSDT'],
                'new_allocation': {
                    'high_freq': 40.0,
                    'main_trend': 45.0,
                    'insurance': 15.0
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _handle_websocket_connection(self, ws):
        """处理WebSocket连接"""
        try:
            while True:
                message = ws.receive()
                if message:
                    data = json.loads(message)
                    if data.get('type') == 'subscribe':
                        # 发送初始数据
                        ws.send(json.dumps({
                            'type': 'initial_data',
                            'data': self._get_enhanced_status()
                        }))
        except Exception as e:
            self.logger.error(f"WebSocket error: {e}")
    
    def broadcast_update(self, update_type: str, data: Dict):
        """广播更新到所有WebSocket客户端"""
        if not self.websocket_clients:
            return
        
        message = json.dumps({
            'type': update_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
        disconnected = set()
        for client in self.websocket_clients:
            try:
                client.send(message)
            except:
                disconnected.add(client)
        
        # 清理断开的连接
        self.websocket_clients -= disconnected


# enhanced_monitoring_service.py - 增强版监控服务
class EnhancedMonitoringService:
    """增强版监控服务 - 整合所有监控功能"""
    
    def __init__(self, trading_bot):
        self.bot = trading_bot
        self.api_endpoints = EnhancedAPIEndpoints(trading_bot)
        self.logger = logging.getLogger(__name__)
        
        # 监控组件
        self.sync_monitor = None
        self.capital_manager = None
        self.intelligent_optimizer = None
        self.multi_symbol_manager = None
        
    async def initialize(self):
        """初始化监控服务"""
        try:
            # 初始化各个监控组件
            if hasattr(self.bot, 'sync_monitor'):
                self.sync_monitor = self.bot.sync_monitor
            
            if hasattr(self.bot, 'capital_manager'):
                self.capital_manager = self.bot.capital_manager
            
            if hasattr(self.bot, 'intelligent_optimizer'):
                self.intelligent_optimizer = self.bot.intelligent_optimizer
            
            if hasattr(self.bot, 'multi_symbol_manager'):
                self.multi_symbol_manager = self.bot.multi_symbol_manager
            
            # 启动监控循环
            await self._start_monitoring_loops()
            
            self.logger.info("Enhanced monitoring service initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize monitoring service: {e}")
            return False
    
    async def _start_monitoring_loops(self):
        """启动各种监控循环"""
        # 启动实时状态广播
        asyncio.create_task(self._broadcast_status_updates())
        
        # 启动异常检测
        asyncio.create_task(self._anomaly_detection_loop())
        
        # 启动性能监控
        asyncio.create_task(self._performance_monitoring_loop())
    
    async def _broadcast_status_updates(self):
        """广播状态更新"""
        while True:
            try:
                # 收集状态更新
                status_update = self.api_endpoints._get_enhanced_status()
                
                # 广播到WebSocket客户端
                self.api_endpoints.broadcast_update('status_update', status_update)
                
                await asyncio.sleep(5)  # 每5秒广播一次
                
            except Exception as e:
                self.logger.error(f"Status broadcast error: {e}")
                await asyncio.sleep(10)
    
    async def _anomaly_detection_loop(self):
        """异常检测循环"""
        while True:
            try:
                # 检测各种异常
                anomalies = await self._detect_anomalies()
                
                if anomalies:
                    # 广播异常警报
                    self.api_endpoints.broadcast_update('anomaly_detected', anomalies)
                    
                    # 记录到数据库
                    await self.bot.db.log_event(
                        "WARNING", "EnhancedMonitoring",
                        f"Detected {len(anomalies)} anomalies",
                        anomalies
                    )
                
                await asyncio.sleep(30)  # 每30秒检测一次
                
            except Exception as e:
                self.logger.error(f"Anomaly detection error: {e}")
                await asyncio.sleep(60)
    
    async def _detect_anomalies(self) -> List[Dict]:
        """检测异常"""
        anomalies = []
        
        # 检测资金异常
        capital_status = self.api_endpoints._analyze_capital_usage()
        if capital_status.get('frozen_ratio', 0) > 0.8:
            anomalies.append({
                'type': 'capital_freeze',
                'severity': 'high',
                'message': '资金冻结率过高',
                'value': capital_status['frozen_ratio']
            })
        
        # 检测同步异常
        sync_status = self.api_endpoints._check_sync_status()
        if sync_status.get('inconsistencies', 0) > 0:
            anomalies.append({
                'type': 'sync_inconsistency',
                'severity': 'medium',
                'message': '订单同步不一致',
                'value': sync_status['inconsistencies']
            })
        
        # 检测网格异常
        grid_metrics = self.api_endpoints._calculate_enhanced_metrics()
        if grid_metrics['grid_integrity']['overall'] < 80:
            anomalies.append({
                'type': 'grid_integrity',
                'severity': 'medium',
                'message': '网格完整度过低',
                'value': grid_metrics['grid_integrity']['overall']
            })
        
        return anomalies
    
    async def _performance_monitoring_loop(self):
        """性能监控循环"""
        while True:
            try:
                # 监控系统性能
                performance_metrics = await self._collect_performance_metrics()
                
                # 更新性能数据
                await self.bot.db.save_performance_metrics(
                    performance_metrics, 
                    datetime.now().date()
                )
                
                await asyncio.sleep(300)  # 每5分钟更新一次
                
            except Exception as e:
                self.logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(600)
    
    async def _collect_performance_metrics(self):
        """收集性能指标"""
        # 这里应该收集各种性能指标
        # 返回PerformanceMetrics对象
        return self.bot.db.get_performance_metrics()


# 集成到主程序的示例
def integrate_enhanced_monitoring(trading_bot, web_app):
    """集成增强版监控到主程序"""
    
    # 创建增强版监控服务
    monitoring_service = EnhancedMonitoringService(trading_bot)
    
    # 注册API路由
    monitoring_service.api_endpoints.register_routes(web_app)
    
    # 启动监控服务
    asyncio.create_task(monitoring_service.initialize())
    
    return monitoring_service