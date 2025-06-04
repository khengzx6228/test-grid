# web_interface.py - Web监控界面
import asyncio
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request
from threading import Thread
import time

class WebInterface:
    """Web监控界面"""
    
    def __init__(self, port: int, trading_bot):
        self.port = port
        self.bot = trading_bot
        self.app = Flask(__name__)
        self.logger = logging.getLogger(__name__)
        self.server_thread = None
        self.running = False
        
        # 设置路由
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.route('/')
        def dashboard():
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/api/status')
        def api_status():
            return jsonify(self.bot.get_status())
        
        @self.app.route('/api/trades')
        def api_trades():
            days = request.args.get('days', 7, type=int)
            return jsonify(self.bot.get_trades(days))
        
        @self.app.route('/api/orders')
        def api_orders():
            return jsonify(self.bot.get_orders())
        
        @self.app.route('/api/performance')
        def api_performance():
            if not self.bot.db:
                return jsonify({})
            
            metrics = self.bot.db.get_performance_metrics()
            return jsonify(metrics.to_dict())
        
        @self.app.route('/api/chart_data')
        def api_chart_data():
            return jsonify(self._get_chart_data())
        
        @self.app.route('/api/grid_status')
        def api_grid_status():
            return jsonify(self._get_grid_status())
        
        @self.app.route('/api/system_info')
        def api_system_info():
            return jsonify(self._get_system_info())
    
    def _get_dashboard_template(self) -> str:
        """获取仪表板HTML模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>天地双网格交易系统 - 监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        .status-running { background-color: #10B981; }
        .status-stopped { background-color: #EF4444; }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
        }
        
        .metric-title {
            font-size: 14px;
            color: #6B7280;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        .metric-value {
            font-size: 28px;
            font-weight: bold;
            color: #1F2937;
            margin-bottom: 5px;
        }
        
        .metric-change {
            font-size: 12px;
            font-weight: 500;
        }
        
        .positive { color: #10B981; }
        .negative { color: #EF4444; }
        .neutral { color: #6B7280; }
        
        .charts-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .chart-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .chart-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #1F2937;
        }
        
        .table-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #E5E7EB;
        }
        
        th {
            background-color: #F9FAFB;
            font-weight: 600;
            color: #374151;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
        }
        
        .badge-success { background-color: #D1FAE5; color: #065F46; }
        .badge-warning { background-color: #FEF3C7; color: #92400E; }
        .badge-danger { background-color: #FEE2E2; color: #991B1B; }
        .badge-info { background-color: #DBEAFE; color: #1E40AF; }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #6B7280;
        }
        
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: background 0.3s ease;
        }
        
        .refresh-btn:hover {
            background: #5a67d8;
        }
        
        @media (max-width: 768px) {
            .charts-container {
                grid-template-columns: 1fr;
            }
            .container {
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 标题栏 -->
        <div class="header">
            <h1 style="font-size: 28px; margin-bottom: 10px;">🚀 天地双网格交易系统</h1>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span class="status-indicator status-running" id="status-indicator"></span>
                    <span id="system-status" style="font-weight: 500;">系统运行中</span>
                    <span style="margin-left: 20px; color: #6B7280;" id="last-update">最后更新: --</span>
                </div>
                <button class="refresh-btn" onclick="refreshData()">刷新数据</button>
            </div>
        </div>

        <!-- 关键指标 -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">当前价格</div>
                <div class="metric-value" id="current-price">$--</div>
                <div class="metric-change neutral" id="price-change">24h: --</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">总盈亏</div>
                <div class="metric-value" id="total-pnl">$--</div>
                <div class="metric-change neutral" id="pnl-percentage">收益率: --%</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">活跃订单</div>
                <div class="metric-value" id="active-orders">--</div>
                <div class="metric-change neutral" id="total-trades">总交易: --</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-title">胜率</div>
                <div class="metric-value" id="win-rate">--%</div>
                <div class="metric-change neutral" id="winning-trades">胜利: -- / --</div>
            </div>
        </div>

        <!-- 图表区域 -->
        <div class="charts-container">
            <div class="chart-card">
                <div class="chart-title">盈亏曲线</div>
                <canvas id="pnlChart" width="400" height="200"></canvas>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">网格完整度</div>
                <canvas id="gridChart" width="400" height="200"></canvas>
            </div>
        </div>

        <!-- 订单表格 -->
        <div class="table-container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 class="chart-title" style="margin: 0;">活跃订单</h3>
                <span id="orders-count" style="color: #6B7280;">加载中...</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>网格层级</th>
                        <th>方向</th>
                        <th>价格</th>
                        <th>数量</th>
                        <th>状态</th>
                        <th>创建时间</th>
                    </tr>
                </thead>
                <tbody id="orders-table">
                    <tr>
                        <td colspan="6" class="loading">加载中...</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 全局变量
        let pnlChart, gridChart;
        let lastUpdateTime = new Date();
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            initializeCharts();
            loadData();
            
            // 定期更新数据
            setInterval(loadData, 10000); // 10秒更新一次
        });
        
        function initializeCharts() {
            // 盈亏曲线图
            const pnlCtx = document.getElementById('pnlChart').getContext('2d');
            pnlChart = new Chart(pnlCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: '累计盈亏 (USDT)',
                        data: [],
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: false,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
            
            // 网格完整度图
            const gridCtx = document.getElementById('gridChart').getContext('2d');
            gridChart = new Chart(gridCtx, {
                type: 'doughnut',
                data: {
                    labels: ['高频套利层', '主趋势层', '保险层'],
                    datasets: [{
                        data: [0, 0, 0],
                        backgroundColor: [
                            '#10B981',
                            '#667eea',
                            '#F59E0B'
                        ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }
        
        async function loadData() {
            try {
                // 加载系统状态
                const statusResponse = await fetch('/api/status');
                const statusData = await statusResponse.json();
                updateSystemStatus(statusData);
                
                // 加载性能数据
                const perfResponse = await fetch('/api/performance');
                const perfData = await perfResponse.json();
                updatePerformanceMetrics(perfData, statusData);
                
                // 加载订单数据
                loadOrdersData();
                
                // 更新图表
                updateCharts(statusData);
                
                lastUpdateTime = new Date();
                document.getElementById('last-update').textContent = 
                    `最后更新: ${lastUpdateTime.toLocaleTimeString()}`;
                
            } catch (error) {
                console.error('加载数据失败:', error);
                showError('数据加载失败，请检查网络连接');
            }
        }
        
        function updateSystemStatus(data) {
            const indicator = document.getElementById('status-indicator');
            const statusText = document.getElementById('system-status');
            
            if (data.running) {
                indicator.className = 'status-indicator status-running';
                statusText.textContent = '系统运行中';
            } else {
                indicator.className = 'status-indicator status-stopped';
                statusText.textContent = '系统已停止';
            }
            
            // 更新当前价格
            document.getElementById('current-price').textContent = 
                `$${parseFloat(data.current_price || 0).toFixed(2)}`;
            
            // 更新活跃订单数
            document.getElementById('active-orders').textContent = data.active_orders || 0;
        }
        
        function updatePerformanceMetrics(perfData, statusData) {
            // 总盈亏
            const totalPnl = parseFloat(perfData.total_pnl || 0);
            document.getElementById('total-pnl').textContent = 
                `${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)} USDT`;
            
            // 收益率
            const returnRate = parseFloat(perfData.daily_return || 0);
            const pnlElement = document.getElementById('pnl-percentage');
            pnlElement.textContent = `收益率: ${returnRate >= 0 ? '+' : ''}${returnRate.toFixed(2)}%`;
            pnlElement.className = `metric-change ${returnRate >= 0 ? 'positive' : 'negative'}`;
            
            // 胜率
            const winRate = parseFloat(perfData.win_rate || 0);
            document.getElementById('win-rate').textContent = `${winRate.toFixed(1)}%`;
            
            // 交易统计
            document.getElementById('total-trades').textContent = 
                `总交易: ${perfData.total_trades || 0}`;
            document.getElementById('winning-trades').textContent = 
                `胜利: ${perfData.winning_trades || 0} / ${perfData.total_trades || 0}`;
        }
        
        async function loadOrdersData() {
            try {
                const response = await fetch('/api/orders');
                const orders = await response.json();
                
                const tbody = document.getElementById('orders-table');
                tbody.innerHTML = '';
                
                document.getElementById('orders-count').textContent = `共 ${orders.length} 个订单`;
                
                if (orders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="loading">暂无活跃订单</td></tr>';
                    return;
                }
                
                orders.slice(0, 20).forEach(order => { // 只显示前20个订单
                    const row = tbody.insertRow();
                    
                    // 网格层级
                    const levelMap = {
                        'high_freq': '高频',
                        'main_trend': '主趋势',
                        'insurance': '保险'
                    };
                    row.insertCell(0).textContent = levelMap[order.grid_level] || order.grid_level;
                    
                    // 方向
                    const sideCell = row.insertCell(1);
                    const sideBadge = order.side === 'BUY' ? 'badge-success' : 'badge-danger';
                    sideCell.innerHTML = `<span class="badge ${sideBadge}">${order.side}</span>`;
                    
                    // 价格
                    row.insertCell(2).textContent = `$${parseFloat(order.price).toFixed(2)}`;
                    
                    // 数量
                    row.insertCell(3).textContent = parseFloat(order.quantity).toFixed(6);
                    
                    // 状态
                    const statusCell = row.insertCell(4);
                    const statusBadge = order.status === 'NEW' ? 'badge-info' : 'badge-warning';
                    statusCell.innerHTML = `<span class="badge ${statusBadge}">${order.status}</span>`;
                    
                    // 创建时间
                    const createTime = new Date(order.created_at).toLocaleString();
                    row.insertCell(5).textContent = createTime;
                });
                
            } catch (error) {
                console.error('加载订单数据失败:', error);
            }
        }
        
        function updateCharts(statusData) {
            // 更新网格完整度图
            if (statusData.grid_integrity) {
                const integrity = statusData.grid_integrity;
                gridChart.data.datasets[0].data = [
                    parseFloat(integrity.high_freq || 0),
                    parseFloat(integrity.main_trend || 0),
                    parseFloat(integrity.insurance || 0)
                ];
                gridChart.update('none');
            }
            
            // 更新盈亏曲线（模拟数据，实际项目中应该从后端获取历史数据）
            const now = new Date();
            if (pnlChart.data.labels.length > 20) {
                pnlChart.data.labels.shift();
                pnlChart.data.datasets[0].data.shift();
            }
            
            pnlChart.data.labels.push(now.toLocaleTimeString());
            
            // 从性能数据获取总盈亏（这里模拟，实际应该获取历史数据）
            fetch('/api/performance')
                .then(response => response.json())
                .then(data => {
                    pnlChart.data.datasets[0].data.push(parseFloat(data.total_pnl || 0));
                    pnlChart.update('none');
                });
        }
        
        function refreshData() {
            loadData();
        }
        
        function showError(message) {
            // 这里可以添加错误提示的UI
            console.error(message);
        }
    </script>
</body>
</html>
        """
    
    def _get_chart_data(self) -> dict:
        """获取图表数据"""
        try:
            # 获取最近24小时的数据点（模拟数据）
            now = datetime.now()
            chart_data = {
                'pnl_history': [],
                'volume_history': [],
                'price_history': []
            }
            
            # 生成最近24小时的数据点
            for i in range(24):
                timestamp = now - timedelta(hours=23-i)
                
                # 这里应该从数据库获取真实的历史数据
                # 现在使用模拟数据
                chart_data['pnl_history'].append({
                    'timestamp': timestamp.isoformat(),
                    'value': float(i * 0.5)  # 模拟盈亏数据
                })
            
            return chart_data
            
        except Exception as e:
            self.logger.error(f"Failed to get chart data: {e}")
            return {}
    
    def _get_grid_status(self) -> dict:
        """获取网格状态"""
        try:
            if not self.bot.trading_engine:
                return {}
            
            status = self.bot.trading_engine.get_status()
            return {
                'grid_integrity': {level.value: float(integrity) for level, integrity in status.grid_integrity.items()},
                'active_orders_by_level': self._get_orders_by_level()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get grid status: {e}")
            return {}
    
    def _get_orders_by_level(self) -> dict:
        """按网格层级获取订单数量"""
        try:
            orders = self.bot.get_orders()
            by_level = {}
            
            for order in orders:
                level = order['grid_level']
                if level not in by_level:
                    by_level[level] = {'buy': 0, 'sell': 0, 'total': 0}
                
                side = order['side'].lower()
                by_level[level][side] += 1
                by_level[level]['total'] += 1
            
            return by_level
            
        except Exception as e:
            self.logger.error(f"Failed to get orders by level: {e}")
            return {}
    
    def _get_system_info(self) -> dict:
        """获取系统信息"""
        try:
            info = {
                'version': '2.0.0',
                'start_time': self.bot.start_time.isoformat() if hasattr(self.bot, 'start_time') else None,
                'uptime_seconds': int(time.time() - self.bot.start_time.timestamp()) if hasattr(self.bot, 'start_time') else 0,
                'database_stats': {}
            }
            
            # 获取数据库统计
            if self.bot.db:
                info['database_stats'] = self.bot.db.get_database_stats()
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get system info: {e}")
            return {}
    
    async def start(self):
        """启动Web服务器"""
        try:
            self.running = True
            
            # 在单独线程中运行Flask应用
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
            
            self.logger.info(f"Web interface started on port {self.port}")
            
            # 保持运行
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Failed to start web interface: {e}")
    
    async def stop(self):
        """停止Web服务器"""
        self.running = False
        self.logger.info("Web interface stopped")