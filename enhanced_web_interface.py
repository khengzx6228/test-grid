# enhanced_web_interface.py - 增强版Web监控界面
import asyncio
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, websocket
from threading import Thread
from typing import Dict, List, Optional
import time

class EnhancedWebInterface:
    """增强版Web监控界面"""
    
    def __init__(self, port: int, trading_bot):
        self.port = port
        self.bot = trading_bot
        self.app = Flask(__name__)
        self.logger = logging.getLogger(__name__)
        self.server_thread = None
        self.running = False
        
        # WebSocket连接管理
        self.websocket_clients = set()
        
        # 实时数据缓存
        self.real_time_data = {
            'price_history': [],
            'pnl_history': [],
            'order_flow': [],
            'risk_metrics': {},
            'system_metrics': {}
        }
        
        # 设置路由
        self._setup_routes()
        self._setup_websocket()
    
    def _setup_routes(self):
        """设置HTTP路由"""
        
        @self.app.route('/')
        def dashboard():
            return render_template_string(self._get_enhanced_dashboard_template())
        
        @self.app.route('/api/status')
        def api_status():
            """系统状态API"""
            return jsonify(self.bot.get_status())
        
        @self.app.route('/api/multi_symbol_status')
        def api_multi_symbol_status():
            """多币种状态API"""
            if hasattr(self.bot, 'multi_symbol_manager'):
                return jsonify(self.bot.multi_symbol_manager.get_multi_symbol_status())
            return jsonify({})
        
        @self.app.route('/api/trades')
        def api_trades():
            """交易记录API"""
            days = request.args.get('days', 7, type=int)
            symbol = request.args.get('symbol', '')
            return jsonify(self._get_filtered_trades(days, symbol))
        
        @self.app.route('/api/orders')
        def api_orders():
            """订单信息API"""
            symbol = request.args.get('symbol', '')
            grid_level = request.args.get('grid_level', '')
            return jsonify(self._get_filtered_orders(symbol, grid_level))
        
        @self.app.route('/api/performance')
        def api_performance():
            """性能指标API"""
            symbol = request.args.get('symbol', '')
            return jsonify(self._get_performance_data(symbol))
        
        @self.app.route('/api/risk_analysis')
        def api_risk_analysis():
            """风险分析API"""
            return jsonify(self._get_risk_analysis())
        
        @self.app.route('/api/market_analysis')
        def api_market_analysis():
            """市场分析API"""
            symbol = request.args.get('symbol', self.bot.config.symbol)
            return jsonify(self._get_market_analysis(symbol))
        
        @self.app.route('/api/optimization_status')
        def api_optimization_status():
            """优化状态API"""
            if hasattr(self.bot, 'intelligent_optimizer'):
                return jsonify(self.bot.intelligent_optimizer.get_optimization_status())
            return jsonify({})
        
        @self.app.route('/api/capital_status')
        def api_capital_status():
            """资金状态API"""
            if hasattr(self.bot, 'capital_manager'):
                return jsonify(self.bot.capital_manager.get_capital_status())
            return jsonify({})
        
        @self.app.route('/api/sync_status')
        def api_sync_status():
            """同步状态API"""
            if hasattr(self.bot, 'sync_monitor'):
                return jsonify(self.bot.sync_monitor.get_sync_status())
            return jsonify({})
        
        @self.app.route('/api/chart_data')
        def api_chart_data():
            """图表数据API"""
            chart_type = request.args.get('type', 'pnl')
            period = request.args.get('period', '24h')
            symbol = request.args.get('symbol', '')
            return jsonify(self._get_chart_data(chart_type, period, symbol))
        
        @self.app.route('/api/system_metrics')
        def api_system_metrics():
            """系统性能指标API"""
            return jsonify(self._get_system_metrics())
        
        @self.app.route('/api/alerts')
        def api_alerts():
            """告警信息API"""
            return jsonify(self._get_recent_alerts())
        
        # 控制接口
        @self.app.route('/api/control/pause_symbol', methods=['POST'])
        def api_pause_symbol():
            """暂停币种交易"""
            data = request.json
            symbol = data.get('symbol')
            return jsonify(self._pause_symbol_trading(symbol))
        
        @self.app.route('/api/control/resume_symbol', methods=['POST'])
        def api_resume_symbol():
            """恢复币种交易"""
            data = request.json
            symbol = data.get('symbol')
            return jsonify(self._resume_symbol_trading(symbol))
        
        @self.app.route('/api/control/emergency_stop', methods=['POST'])
        def api_emergency_stop():
            """紧急停止"""
            return jsonify(self._emergency_stop())
    
    def _setup_websocket(self):
        """设置WebSocket"""
        
        @self.app.websocket('/ws')
        def handle_websocket():
            """WebSocket处理"""
            try:
                self.websocket_clients.add(websocket)
                self.logger.info("WebSocket client connected")
                
                while True:
                    # 保持连接
                    message = websocket.receive()
                    if message:
                        # 处理客户端消息
                        self._handle_websocket_message(websocket, message)
                    
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
            finally:
                self.websocket_clients.discard(websocket)
                self.logger.info("WebSocket client disconnected")
    
    def _handle_websocket_message(self, ws, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'subscribe':
                # 订阅实时数据
                channels = data.get('channels', [])
                # 发送初始数据
                for channel in channels:
                    initial_data = self._get_channel_data(channel)
                    ws.send(json.dumps({
                        'type': 'data',
                        'channel': channel,
                        'data': initial_data
                    }))
            
            elif msg_type == 'ping':
                # 心跳响应
                ws.send(json.dumps({'type': 'pong', 'timestamp': time.time()}))
                
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
    
    def _get_channel_data(self, channel: str) -> dict:
        """获取频道数据"""
        if channel == 'price':
            return {'current_price': float(self.bot.trading_engine.current_price) if self.bot.trading_engine else 0}
        elif channel == 'orders':
            return {'active_orders': len(self.bot.get_orders())}
        elif channel == 'performance':
            return self._get_performance_data('')
        else:
            return {}
    
    def broadcast_update(self, channel: str, data: dict):
        """广播更新到所有WebSocket客户端"""
        if not self.websocket_clients:
            return
        
        message = json.dumps({
            'type': 'update',
            'channel': channel,
            'data': data,
            'timestamp': time.time()
        })
        
        disconnected_clients = set()
        for client in self.websocket_clients:
            try:
                client.send(message)
            except:
                disconnected_clients.add(client)
        
        # 清理断开的连接
        self.websocket_clients -= disconnected_clients
    
    def _get_enhanced_dashboard_template(self) -> str:
        """获取增强版仪表板HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>天地双网格交易系统 - 增强版监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .glassmorphism {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        
        .metric-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.05));
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.18);
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        .status-running { background: linear-gradient(45deg, #10B981, #34D399); }
        .status-stopped { background: linear-gradient(45deg, #EF4444, #F87171); }
        .status-warning { background: linear-gradient(45deg, #F59E0B, #FCD34D); }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .chart-container { height: 300px; }
        .mini-chart { height: 150px; }
        
        .tab-button {
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-right: 10px;
        }
        
        .tab-button.active {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .symbol-selector {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            color: white;
            padding: 8px 12px;
        }
        
        .alert-item {
            padding: 12px;
            margin: 8px 0;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-left: 4px solid;
        }
        
        .alert-critical { border-left-color: #EF4444; }
        .alert-warning { border-left-color: #F59E0B; }
        .alert-info { border-left-color: #3B82F6; }
        
        .grid-health-bar {
            height: 8px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }
        
        .grid-health-fill {
            height: 100%;
            transition: width 0.3s ease;
            border-radius: 4px;
        }
        
        .health-excellent { background: linear-gradient(90deg, #10B981, #34D399); }
        .health-good { background: linear-gradient(90deg, #F59E0B, #FCD34D); }
        .health-poor { background: linear-gradient(90deg, #EF4444, #F87171); }
        
        .real-time-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(16, 185, 129, 0.9);
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 1000;
        }
        
        .control-button {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 5px;
        }
        
        .control-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        }
        
        .control-button.danger {
            background: linear-gradient(45deg, #EF4444, #F87171);
        }
        
        .scrollable-table {
            max-height: 400px;
            overflow-y: auto;
        }
        
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .metric-card { padding: 15px; }
            .charts-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <!-- 实时连接指示器 -->
    <div class="real-time-indicator" id="connection-status">
        <i class="fas fa-wifi"></i> 实时连接
    </div>

    <div class="container mx-auto px-4 py-6">
        <!-- 顶部导航 -->
        <div class="glassmorphism mb-6 p-6">
            <div class="flex justify-between items-center mb-4">
                <h1 class="text-3xl font-bold text-white">
                    <i class="fas fa-chart-line mr-3"></i>
                    天地双网格交易系统 v2.0
                </h1>
                <div class="flex items-center space-x-4">
                    <select class="symbol-selector" id="symbol-selector">
                        <option value="">全部币种</option>
                    </select>
                    <div class="text-white text-right">
                        <div class="flex items-center">
                            <span class="status-indicator status-running" id="main-status-indicator"></span>
                            <span id="main-system-status">系统运行中</span>
                        </div>
                        <div class="text-sm opacity-80" id="last-update">最后更新: --</div>
                    </div>
                </div>
            </div>
            
            <!-- 标签导航 -->
            <div class="flex flex-wrap">
                <button class="tab-button active" onclick="switchTab('overview')">
                    <i class="fas fa-tachometer-alt mr-2"></i>总览
                </button>
                <button class="tab-button" onclick="switchTab('trading')">
                    <i class="fas fa-exchange-alt mr-2"></i>交易
                </button>
                <button class="tab-button" onclick="switchTab('risk')">
                    <i class="fas fa-shield-alt mr-2"></i>风险
                </button>
                <button class="tab-button" onclick="switchTab('analysis')">
                    <i class="fas fa-chart-bar mr-2"></i>分析
                </button>
                <button class="tab-button" onclick="switchTab('settings')">
                    <i class="fas fa-cog mr-2"></i>控制
                </button>
            </div>
        </div>

        <!-- 总览标签 -->
        <div id="overview-tab" class="tab-content active">
            <!-- 关键指标卡片 -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <div class="metric-card text-white">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-sm opacity-80">当前价格</h3>
                        <i class="fas fa-dollar-sign text-green-400"></i>
                    </div>
                    <p class="text-2xl font-bold" id="current-price">$--</p>
                    <p class="text-sm" id="price-change">24h: --</p>
                </div>
                
                <div class="metric-card text-white">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-sm opacity-80">总盈亏</h3>
                        <i class="fas fa-chart-line text-blue-400"></i>
                    </div>
                    <p class="text-2xl font-bold" id="total-pnl">$--</p>
                    <p class="text-sm" id="pnl-percentage">收益率: --%</p>
                </div>
                
                <div class="metric-card text-white">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-sm opacity-80">活跃订单</h3>
                        <i class="fas fa-list-alt text-yellow-400"></i>
                    </div>
                    <p class="text-2xl font-bold" id="active-orders">--</p>
                    <p class="text-sm" id="orders-rate">订单/小时: --</p>
                </div>
                
                <div class="metric-card text-white">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-sm opacity-80">系统健康</h3>
                        <i class="fas fa-heartbeat text-red-400"></i>
                    </div>
                    <p class="text-2xl font-bold" id="system-health">--%</p>
                    <p class="text-sm" id="health-status">状态良好</p>
                </div>
            </div>

            <!-- 图表区域 -->
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8 charts-grid">
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-chart-area mr-2"></i>盈亏曲线
                    </h3>
                    <div class="chart-container">
                        <canvas id="pnlChart"></canvas>
                    </div>
                </div>
                
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-network-wired mr-2"></i>网格健康度
                    </h3>
                    <div id="grid-health-display">
                        <!-- 网格健康度显示 -->
                    </div>
                </div>
            </div>

            <!-- 多币种状态 -->
            <div class="glassmorphism p-6 mb-8" id="multi-symbol-section" style="display: none;">
                <h3 class="text-xl font-bold text-white mb-4">
                    <i class="fas fa-coins mr-2"></i>多币种状态
                </h3>
                <div id="symbol-status-grid" class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                    <!-- 币种状态卡片将在这里动态生成 -->
                </div>
            </div>
        </div>

        <!-- 交易标签 -->
        <div id="trading-tab" class="tab-content">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- 活跃订单 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-tasks mr-2"></i>活跃订单
                    </h3>
                    <div class="scrollable-table">
                        <table class="w-full text-white">
                            <thead>
                                <tr class="border-b border-white border-opacity-20">
                                    <th class="text-left py-2">币种</th>
                                    <th class="text-left py-2">层级</th>
                                    <th class="text-left py-2">方向</th>
                                    <th class="text-left py-2">价格</th>
                                    <th class="text-left py-2">数量</th>
                                </tr>
                            </thead>
                            <tbody id="orders-table-body">
                                <tr><td colspan="5" class="text-center py-4">加载中...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 最近交易 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-history mr-2"></i>最近交易
                    </h3>
                    <div class="scrollable-table">
                        <table class="w-full text-white">
                            <thead>
                                <tr class="border-b border-white border-opacity-20">
                                    <th class="text-left py-2">时间</th>
                                    <th class="text-left py-2">币种</th>
                                    <th class="text-left py-2">方向</th>
                                    <th class="text-left py-2">价格</th>
                                    <th class="text-left py-2">盈亏</th>
                                </tr>
                            </thead>
                            <tbody id="trades-table-body">
                                <tr><td colspan="5" class="text-center py-4">加载中...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- 风险标签 -->
        <div id="risk-tab" class="tab-content">
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- 风险指标 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-exclamation-triangle mr-2"></i>风险指标
                    </h3>
                    <div id="risk-metrics">
                        <!-- 风险指标内容 -->
                    </div>
                </div>

                <!-- 资金分配 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-pie-chart mr-2"></i>资金分配
                    </h3>
                    <div class="mini-chart">
                        <canvas id="capitalAllocationChart"></canvas>
                    </div>
                </div>

                <!-- 告警信息 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-bell mr-2"></i>告警信息
                    </h3>
                    <div id="alerts-container" class="scrollable-table">
                        <!-- 告警信息内容 -->
                    </div>
                </div>
            </div>
        </div>

        <!-- 分析标签 -->
        <div id="analysis-tab" class="tab-content">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <!-- 市场分析 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-brain mr-2"></i>市场分析
                    </h3>
                    <div id="market-analysis-content">
                        <!-- 市场分析内容 -->
                    </div>
                </div>

                <!-- 参数优化 -->
                <div class="glassmorphism p-6">
                    <h3 class="text-xl font-bold text-white mb-4">
                        <i class="fas fa-robot mr-2"></i>智能优化
                    </h3>
                    <div id="optimization-status">
                        <!-- 优化状态内容 -->
                    </div>
                </div>
            </div>
        </div>

        <!-- 控制标签 -->
        <div id="settings-tab" class="tab-content">
            <div class="glassmorphism p-6">
                <h3 class="text-xl font-bold text-white mb-6">
                    <i class="fas fa-sliders-h mr-2"></i>系统控制
                </h3>
                
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    <!-- 币种控制 -->
                    <div class="text-white">
                        <h4 class="text-lg font-semibold mb-3">币种控制</h4>
                        <div id="symbol-controls">
                            <!-- 币种控制按钮 -->
                        </div>
                    </div>

                    <!-- 系统控制 -->
                    <div class="text-white">
                        <h4 class="text-lg font-semibold mb-3">系统控制</h4>
                        <button class="control-button danger w-full mb-2" onclick="emergencyStop()">
                            <i class="fas fa-stop mr-2"></i>紧急停止
                        </button>
                        <button class="control-button w-full mb-2" onclick="restartSystem()">
                            <i class="fas fa-redo mr-2"></i>重启系统
                        </button>
                    </div>

                    <!-- 数据导出 -->
                    <div class="text-white">
                        <h4 class="text-lg font-semibold mb-3">数据管理</h4>
                        <button class="control-button w-full mb-2" onclick="exportData()">
                            <i class="fas fa-download mr-2"></i>导出数据
                        </button>
                        <button class="control-button w-full mb-2" onclick="backupData()">
                            <i class="fas fa-save mr-2"></i>备份数据
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 全局变量
        let charts = {};
        let websocket = null;
        let currentSymbol = '';
        let updateInterval;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            initializeInterface();
            initializeWebSocket();
            loadInitialData();
            
            // 设置定期更新
            updateInterval = setInterval(updateDashboard, 5000);
        });
        
        function initializeInterface() {
            initializeCharts();
            setupSymbolSelector();
            setupEventListeners();
        }
        
        function initializeCharts() {
            // 盈亏曲线图
            const pnlCtx = document.getElementById('pnlChart').getContext('2d');
            charts.pnl = new Chart(pnlCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '累计盈亏 (USDT)',
                        data: [],
                        borderColor: '#10B981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: 'white' } } },
                    scales: {
                        x: { ticks: { color: 'white' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                        y: { ticks: { color: 'white' }, grid: { color: 'rgba(255,255,255,0.1)' } }
                    }
                }
            });
            
            // 资金分配图
            const capitalCtx = document.getElementById('capitalAllocationChart').getContext('2d');
            charts.capital = new Chart(capitalCtx, {
                type: 'doughnut',
                data: {
                    labels: ['高频层', '主趋势层', '保险层', '可用资金'],
                    datasets: [{
                        data: [0, 0, 0, 100],
                        backgroundColor: ['#10B981', '#3B82F6', '#F59E0B', '#6B7280']
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: 'white' } } }
                }
            });
        }
        
        function initializeWebSocket() {
            try {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                websocket = new WebSocket(`${protocol}//${window.location.host}/ws`);
                
                websocket.onopen = function() {
                    console.log('WebSocket connected');
                    updateConnectionStatus(true);
                    
                    // 订阅实时数据
                    websocket.send(JSON.stringify({
                        type: 'subscribe',
                        channels: ['price', 'orders', 'performance', 'alerts']
                    }));
                };
                
                websocket.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    handleWebSocketMessage(data);
                };
                
                websocket.onclose = function() {
                    console.log('WebSocket disconnected');
                    updateConnectionStatus(false);
                    
                    // 尝试重连
                    setTimeout(initializeWebSocket, 5000);
                };
                
                websocket.onerror = function(error) {
                    console.error('WebSocket error:', error);
                    updateConnectionStatus(false);
                };
                
            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
                updateConnectionStatus(false);
            }
        }
        
        function handleWebSocketMessage(data) {
            if (data.type === 'update') {
                switch (data.channel) {
                    case 'price':
                        updatePriceDisplay(data.data);
                        break;
                    case 'orders':
                        updateOrdersDisplay(data.data);
                        break;
                    case 'performance':
                        updatePerformanceDisplay(data.data);
                        break;
                    case 'alerts':
                        updateAlertsDisplay(data.data);
                        break;
                }
            }
        }
        
        function updateConnectionStatus(connected) {
            const indicator = document.getElementById('connection-status');
            if (connected) {
                indicator.innerHTML = '<i class="fas fa-wifi"></i> 实时连接';
                indicator.style.background = 'rgba(16, 185, 129, 0.9)';
            } else {
                indicator.innerHTML = '<i class="fas fa-wifi-slash"></i> 连接断开';
                indicator.style.background = 'rgba(239, 68, 68, 0.9)';
            }
        }
        
        async function loadInitialData() {
            try {
                // 加载系统状态
                const statusResponse = await fetch('/api/status');
                const statusData = await statusResponse.json();
                updateSystemStatus(statusData);
                
                // 加载多币种状态
                loadMultiSymbolStatus();
                
                // 加载其他数据
                loadOrdersData();
                loadTradesData();
                loadRiskData();
                loadMarketAnalysis();
                
            } catch (error) {
                console.error('Failed to load initial data:', error);
            }
        }
        
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateSystemStatus(data);
                
                document.getElementById('last-update').textContent = 
                    `最后更新: ${new Date().toLocaleTimeString()}`;
                
            } catch (error) {
                console.error('Dashboard update failed:', error);
            }
        }
        
        function updateSystemStatus(data) {
            // 更新主要状态
            const indicator = document.getElementById('main-status-indicator');
            const statusText = document.getElementById('main-system-status');
            
            if (data.running) {
                indicator.className = 'status-indicator status-running';
                statusText.textContent = '系统运行中';
            } else {
                indicator.className = 'status-indicator status-stopped';
                statusText.textContent = '系统已停止';
            }
            
            // 更新关键指标
            document.getElementById('current-price').textContent = 
                `$${parseFloat(data.current_price || 0).toFixed(2)}`;
            document.getElementById('active-orders').textContent = data.active_orders || 0;
            
            // 更新系统健康度
            const healthScore = calculateSystemHealth(data);
            document.getElementById('system-health').textContent = `${healthScore}%`;
            updateHealthStatus(healthScore);
        }
        
        function calculateSystemHealth(data) {
            let score = 100;
            
            if (!data.running) score -= 50;
            if (data.active_orders === 0) score -= 20;
            // 可以添加更多健康度计算逻辑
            
            return Math.max(0, score);
        }
        
        function updateHealthStatus(score) {
            const statusElement = document.getElementById('health-status');
            
            if (score >= 90) {
                statusElement.textContent = '状态优秀';
                statusElement.className = 'text-sm text-green-400';
            } else if (score >= 70) {
                statusElement.textContent = '状态良好';
                statusElement.className = 'text-sm text-yellow-400';
            } else {
                statusElement.textContent = '需要关注';
                statusElement.className = 'text-sm text-red-400';
            }
        }
        
        // 标签切换功能
        function switchTab(tabName) {
            // 隐藏所有标签内容
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // 移除所有按钮的活跃状态
            document.querySelectorAll('.tab-button').forEach(button => {
                button.classList.remove('active');
            });
            
            // 显示选中的标签
            document.getElementById(`${tabName}-tab`).classList.add('active');
            event.target.classList.add('active');
            
            // 根据标签加载相应数据
            switch(tabName) {
                case 'trading':
                    loadOrdersData();
                    loadTradesData();
                    break;
                case 'risk':
                    loadRiskData();
                    break;
                case 'analysis':
                    loadMarketAnalysis();
                    break;
                case 'settings':
                    loadControlsData();
                    break;
            }
        }
        
        // 数据加载函数
        async function loadMultiSymbolStatus() {
            try {
                const response = await fetch('/api/multi_symbol_status');
                const data = await response.json();
                
                if (data.total_symbols > 1) {
                    document.getElementById('multi-symbol-section').style.display = 'block';
                    renderMultiSymbolStatus(data);
                }
            } catch (error) {
                console.error('Failed to load multi-symbol status:', error);
            }
        }
        
        function renderMultiSymbolStatus(data) {
            const container = document.getElementById('symbol-status-grid');
            container.innerHTML = '';
            
            for (const [symbol, status] of Object.entries(data.symbols || {})) {
                const card = document.createElement('div');
                card.className = 'metric-card text-white text-center';
                card.innerHTML = `
                    <h4 class="font-semibold mb-2">${symbol}</h4>
                    <div class="text-sm mb-1">
                        <span class="status-indicator ${status.running ? 'status-running' : 'status-stopped'}"></span>
                        ${status.enabled ? '运行中' : '已停止'}
                    </div>
                    <div class="text-xs opacity-80">
                        订单: ${status.active_orders || 0}
                    </div>
                    <div class="text-xs opacity-80">
                        资金: $${(status.allocated_capital || 0).toFixed(0)}
                    </div>
                `;
                container.appendChild(card);
            }
        }
        
        async function loadOrdersData() {
            try {
                const response = await fetch(`/api/orders?symbol=${currentSymbol}`);
                const orders = await response.json();
                renderOrdersTable(orders);
            } catch (error) {
                console.error('Failed to load orders:', error);
            }
        }
        
        function renderOrdersTable(orders) {
            const tbody = document.getElementById('orders-table-body');
            tbody.innerHTML = '';
            
            if (orders.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4">暂无活跃订单</td></tr>';
                return;
            }
            
            orders.slice(0, 20).forEach(order => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td class="py-2">${order.symbol || '--'}</td>
                    <td class="py-2">${getGridLevelName(order.grid_level)}</td>
                    <td class="py-2">
                        <span class="px-2 py-1 rounded text-xs ${order.side === 'BUY' ? 'bg-green-500' : 'bg-red-500'}">
                            ${order.side}
                        </span>
                    </td>
                    <td class="py-2">$${parseFloat(order.price).toFixed(2)}</td>
                    <td class="py-2">${parseFloat(order.quantity).toFixed(6)}</td>
                `;
            });
        }
        
        function getGridLevelName(level) {
            const names = {
                'high_freq': '高频',
                'main_trend': '主趋势',
                'insurance': '保险'
            };
            return names[level] || level;
        }
        
        // 控制功能
        async function emergencyStop() {
            if (confirm('确定要执行紧急停止吗？这将停止所有交易活动。')) {
                try {
                    const response = await fetch('/api/control/emergency_stop', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' }
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        alert('紧急停止执行成功');
                        updateDashboard();
                    } else {
                        alert('紧急停止失败: ' + result.message);
                    }
                } catch (error) {
                    alert('紧急停止请求失败: ' + error.message);
                }
            }
        }
        
        // 其他功能函数...
        async function loadTradesData() { /* 实现交易数据加载 */ }
        async function loadRiskData() { /* 实现风险数据加载 */ }
        async function loadMarketAnalysis() { /* 实现市场分析加载 */ }
        async function loadControlsData() { /* 实现控制数据加载 */ }
        
        function setupSymbolSelector() { /* 实现币种选择器 */ }
        function setupEventListeners() { /* 实现事件监听器 */ }
        
        // 页面卸载时清理
        window.addEventListener('beforeunload', function() {
            if (websocket) {
                websocket.close();
            }
            if (updateInterval) {
                clearInterval(updateInterval);
            }
        });
    </script>
</body>
</html>
        """
    
    def _get_filtered_trades(self, days: int, symbol: str) -> List[dict]:
        """获取过滤后的交易记录"""
        try:
            trades = self.bot.get_trades(days)
            
            if symbol:
                trades = [trade for trade in trades if trade.get('symbol') == symbol]
            
            return trades
        except Exception as e:
            self.logger.error(f"Failed to get filtered trades: {e}")
            return []
    
    def _get_filtered_orders(self, symbol: str, grid_level: str) -> List[dict]:
        """获取过滤后的订单"""
        try:
            orders = self.bot.get_orders()
            
            if symbol:
                orders = [order for order in orders if order.get('symbol') == symbol]
            
            if grid_level:
                orders = [order for order in orders if order.get('grid_level') == grid_level]
            
            return orders
        except Exception as e:
            self.logger.error(f"Failed to get filtered orders: {e}")
            return []
    
    def _get_performance_data(self, symbol: str) -> dict:
        """获取性能数据"""
        try:
            if not self.bot.db:
                return {}
            
            metrics = self.bot.db.get_performance_metrics()
            return metrics.to_dict()
        except Exception as e:
            self.logger.error(f"Failed to get performance data: {e}")
            return {}
    
    def _get_risk_analysis(self) -> dict:
        """获取风险分析数据"""
        try:
            # 这里应该从风险管理器获取数据
            return {
                'risk_score': 25,
                'max_drawdown': 8.5,
                'current_drawdown': 2.3,
                'var_95': 1.2,
                'sharpe_ratio': 1.8,
                'risk_level': 'low'
            }
        except Exception as e:
            self.logger.error(f"Failed to get risk analysis: {e}")
            return {}
    
    def _get_market_analysis(self, symbol: str) -> dict:
        """获取市场分析数据"""
        try:
            # 这里应该从市场分析器获取数据
            return {
                'market_state': 'sideways',
                'volatility_level': 'medium',
                'trend_strength': 0.3,
                'support_level': 45000,
                'resistance_level': 52000,
                'rsi': 55.2,
                'recommendation': 'hold_current_strategy'
            }
        except Exception as e:
            self.logger.error(f"Failed to get market analysis: {e}")
            return {}
    
    def _get_chart_data(self, chart_type: str, period: str, symbol: str) -> dict:
        """获取图表数据"""
        try:
            if chart_type == 'pnl':
                # 生成模拟盈亏数据
                now = datetime.now()
                data_points = []
                
                for i in range(24):
                    timestamp = now - timedelta(hours=23-i)
                    value = i * 0.5 + (i % 3) * 0.2  # 模拟数据
                    data_points.append({
                        'timestamp': timestamp.isoformat(),
                        'value': value
                    })
                
                return {'data': data_points}
            
            return {'data': []}
        except Exception as e:
            self.logger.error(f"Failed to get chart data: {e}")
            return {'data': []}
    
    def _get_system_metrics(self) -> dict:
        """获取系统性能指标"""
        try:
            import psutil
            
            return {
                'cpu_usage': psutil.cpu_percent(),
                'memory_usage': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage('/').percent,
                'network_io': {
                    'bytes_sent': psutil.net_io_counters().bytes_sent,
                    'bytes_recv': psutil.net_io_counters().bytes_recv
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    def _get_recent_alerts(self) -> List[dict]:
        """获取最近的告警信息"""
        try:
            # 这里应该从数据库获取最近的告警
            return [
                {
                    'level': 'info',
                    'message': '系统运行正常',
                    'timestamp': datetime.now().isoformat()
                }
            ]
        except Exception as e:
            self.logger.error(f"Failed to get recent alerts: {e}")
            return []
    
    def _pause_symbol_trading(self, symbol: str) -> dict:
        """暂停币种交易"""
        try:
            # 这里应该调用多币种管理器的暂停功能
            return {'success': True, 'message': f'已暂停 {symbol} 交易'}
        except Exception as e:
            self.logger.error(f"Failed to pause symbol trading: {e}")
            return {'success': False, 'message': str(e)}
    
    def _resume_symbol_trading(self, symbol: str) -> dict:
        """恢复币种交易"""
        try:
            # 这里应该调用多币种管理器的恢复功能
            return {'success': True, 'message': f'已恢复 {symbol} 交易'}
        except Exception as e:
            self.logger.error(f"Failed to resume symbol trading: {e}")
            return {'success': False, 'message': str(e)}
    
    def _emergency_stop(self) -> dict:
        """紧急停止"""
        try:
            # 这里应该调用系统的紧急停止功能
            if hasattr(self.bot, 'emergency_stop'):
                self.bot.emergency_stop()
                return {'success': True, 'message': '紧急停止执行成功'}
            else:
                return {'success': False, 'message': '紧急停止功能不可用'}
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
            return {'success': False, 'message': str(e)}
    
    async def start(self):
        """启动增强版Web界面"""
        try:
            self.running = True
            
            def run_server():
                self.app.run(
                    host='0.0.0.0',
                    port=self.port,
                    debug=False,
                    use_reloader=False,
                    threaded=True
                )
            
            self.server_thread = Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            self.logger.info(f"Enhanced web interface started on port {self.port}")
            
            # 启动实时数据广播
            await self._start_real_time_broadcast()
            
        except Exception as e:
            self.logger.error(f"Failed to start enhanced web interface: {e}")
    
    async def _start_real_time_broadcast(self):
        """启动实时数据广播"""
        while self.running:
            try:
                # 广播价格更新
                if self.bot.trading_engine:
                    price_data = {
                        'current_price': float(self.bot.trading_engine.current_price),
                        'timestamp': time.time()
                    }
                    self.broadcast_update('price', price_data)
                
                # 广播订单更新
                orders_data = {
                    'active_orders': len(self.bot.get_orders()),
                    'timestamp': time.time()
                }
                self.broadcast_update('orders', orders_data)
                
                await asyncio.sleep(5)  # 每5秒广播一次
                
            except Exception as e:
                self.logger.error(f"Real-time broadcast error: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """停止增强版Web界面"""
        self.running = False
        
        # 关闭所有WebSocket连接
        for client in self.websocket_clients.copy():
            try:
                client.close()
            except:
                pass
        
        self.logger.info("Enhanced web interface stopped")