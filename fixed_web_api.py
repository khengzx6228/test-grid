# web_api_service.py - 修复版Web API服务
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any
from decimal import Decimal
import weakref

from quart import Quart, jsonify, request, websocket, render_template_string
from quart_cors import cors
import asyncio_mqtt
from hypercorn.config import Config
from hypercorn.asyncio import serve

from core_system import (
    TradingSystem, DatabaseManager, ConfigManager, OrderStatus,
    GridLevel, TradingSystemError
)
from trading_engine import GridTradingEngine

class WebSocketManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.connections: Set[Any] = set()
        self.logger = logging.getLogger(__name__)
        
    def add_connection(self, ws):
        """添加WebSocket连接"""
        self.connections.add(ws)
        self.logger.info(f"WebSocket connected. Total connections: {len(self.connections)}")
    
    def remove_connection(self, ws):
        """移除WebSocket连接"""
        self.connections.discard(ws)
        self.logger.info(f"WebSocket disconnected. Total connections: {len(self.connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接"""
        if not self.connections:
            return
        
        message_json = json.dumps(message)
        dead_connections = set()
        
        for ws in self.connections.copy():
            try:
                await ws.send(message_json)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.add(ws)
        
        # 清理死连接
        for ws in dead_connections:
            self.remove_connection(ws)
    
    async def send_to_connection(self, ws, message: Dict[str, Any]):
        """发送消息到特定连接"""
        try:
            await ws.send(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Failed to send message to WebSocket: {e}")
            self.remove_connection(ws)

class APIResponseFormatter:
    """API响应格式化器"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """成功响应格式"""
        response = {
            "success": True,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if data is not None:
            response["data"] = data
        return response
    
    @staticmethod
    def error(message: str, error_code: str = "UNKNOWN_ERROR", 
              details: Any = None) -> Dict[str, Any]:
        """错误响应格式"""
        response = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            },
            "timestamp": datetime.now().isoformat()
        }
        if details is not None:
            response["error"]["details"] = details
        return response
    
    @staticmethod
    def paginated(data: List[Any], page: int, page_size: int, 
                  total: int) -> Dict[str, Any]:
        """分页响应格式"""
        return {
            "success": True,
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            },
            "timestamp": datetime.now().isoformat()
        }

class WebAPIService:
    """Web API服务"""
    
    def __init__(self, trading_system: TradingSystem):
        self.trading_system = trading_system
        self.logger = logging.getLogger(__name__)
        
        # 创建Quart应用
        self.app = Quart(__name__)
        self.app = cors(self.app, allow_origin="*")
        
        # WebSocket管理器
        self.ws_manager = WebSocketManager()
        
        # 响应格式化器
        self.formatter = APIResponseFormatter()
        
        # 注册路由
        self._register_routes()
        
        # 定时任务
        self._setup_background_tasks()
    
    def _register_routes(self):
        """注册API路由"""
        
        # 基础路由
        @self.app.route('/')
        async def index():
            """主页"""
            return await render_template_string(self._get_dashboard_html())
        
        @self.app.route('/health')
        async def health_check():
            """健康检查"""
            try:
                health_status = await self.trading_system.health_check()
                return jsonify(self.formatter.success(health_status, "Health check completed"))
            except Exception as e:
                return jsonify(self.formatter.error(f"Health check failed: {str(e)}", "HEALTH_CHECK_ERROR"))
        
        # 系统状态API
        @self.app.route('/api/v1/status')
        async def get_system_status():
            """获取系统状态"""
            try:
                trading_engine = self.trading_system.get_component('trading_engine')
                if not trading_engine:
                    return jsonify(self.formatter.error("Trading engine not found", "ENGINE_NOT_FOUND"))
                
                status = await trading_engine.get_status()
                
                # 获取数据库状态
                db_manager = self.trading_system.db_manager
                if db_manager:
                    system_state = await db_manager.get_system_state()
                    status.update({
                        "total_balance": float(system_state.total_balance),
                        "available_balance": float(system_state.available_balance),
                        "total_pnl": float(system_state.total_pnl)
                    })
                
                return jsonify(self.formatter.success(status, "System status retrieved"))
                
            except Exception as e:
                self.logger.error(f"Failed to get system status: {e}")
                return jsonify(self.formatter.error(str(e), "STATUS_ERROR"))
        
        # 订单管理API
        @self.app.route('/api/v1/orders')
        async def get_orders():
            """获取订单列表"""
            try:
                # 获取查询参数
                status_param = request.args.get('status')
                symbol = request.args.get('symbol')
                page = int(request.args.get('page', 1))
                page_size = min(int(request.args.get('page_size', 50)), 100)
                
                # 转换状态参数
                status_filter = None
                if status_param:
                    try:
                        status_filter = OrderStatus(status_param.upper())
                    except ValueError:
                        return jsonify(self.formatter.error("Invalid status parameter", "INVALID_PARAMETER"))
                
                db_manager = self.trading_system.db_manager
                if not db_manager:
                    return jsonify(self.formatter.error("Database not available", "DB_ERROR"))
                
                # 获取订单
                orders = await db_manager.get_orders(status=status_filter, symbol=symbol)
                
                # 分页处理
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                page_orders = orders[start_idx:end_idx]
                
                # 转换为字典格式
                orders_data = [order.to_dict() for order in page_orders]
                
                return jsonify(self.formatter.paginated(orders_data, page, page_size, len(orders)))
                
            except Exception as e:
                self.logger.error(f"Failed to get orders: {e}")
                return jsonify(self.formatter.error(str(e), "ORDERS_ERROR"))
        
        @self.app.route('/api/v1/orders/<order_id>')
        async def get_order_detail(order_id: str):
            """获取订单详情"""
            try:
                db_manager = self.trading_system.db_manager
                if not db_manager:
                    return jsonify(self.formatter.error("Database not available", "DB_ERROR"))
                
                # 这里需要扩展数据库管理器以支持按ID查询
                orders = await db_manager.get_orders()
                order = next((o for o in orders if o.id == order_id), None)
                
                if not order:
                    return jsonify(self.formatter.error("Order not found", "ORDER_NOT_FOUND"))
                
                return jsonify(self.formatter.success(order.to_dict(), "Order retrieved"))
                
            except Exception as e:
                self.logger.error(f"Failed to get order detail: {e}")
                return jsonify(self.formatter.error(str(e), "ORDER_DETAIL_ERROR"))
        
        # 交易控制API
        @self.app.route('/api/v1/trading/start', methods=['POST'])
        async def start_trading():
            """启动交易"""
            try:
                trading_engine = self.trading_system.get_component('trading_engine')
                if not trading_engine:
                    return jsonify(self.formatter.error("Trading engine not found", "ENGINE_NOT_FOUND"))
                
                if trading_engine.running:
                    return jsonify(self.formatter.error("Trading is already running", "ALREADY_RUNNING"))
                
                # 启动交易引擎
                success = await trading_engine.initialize()
                if not success:
                    return jsonify(self.formatter.error("Failed to initialize trading engine", "INIT_FAILED"))
                
                # 在后台启动交易循环
                asyncio.create_task(trading_engine.run_trading_loop())
                
                # 广播状态更新
                await self.ws_manager.broadcast({
                    "type": "trading_status",
                    "data": {"running": True},
                    "timestamp": datetime.now().isoformat()
                })
                
                return jsonify(self.formatter.success({"running": True}, "Trading started successfully"))
                
            except Exception as e:
                self.logger.error(f"Failed to start trading: {e}")
                return jsonify(self.formatter.error(str(e), "START_TRADING_ERROR"))
        
        @self.app.route('/api/v1/trading/stop', methods=['POST'])
        async def stop_trading():
            """停止交易"""
            try:
                trading_engine = self.trading_system.get_component('trading_engine')
                if not trading_engine:
                    return jsonify(self.formatter.error("Trading engine not found", "ENGINE_NOT_FOUND"))
                
                await trading_engine.stop()
                
                # 广播状态更新
                await self.ws_manager.broadcast({
                    "type": "trading_status",
                    "data": {"running": False},
                    "timestamp": datetime.now().isoformat()
                })
                
                return jsonify(self.formatter.success({"running": False}, "Trading stopped successfully"))
                
            except Exception as e:
                self.logger.error(f"Failed to stop trading: {e}")
                return jsonify(self.formatter.error(str(e), "STOP_TRADING_ERROR"))
        
        # 配置管理API
        @self.app.route('/api/v1/config')
        async def get_config():
            """获取配置"""
            try:
                config_manager = self.trading_system.config_manager
                
                # 返回非敏感配置信息
                safe_config = {
                    "trading": config_manager.get('trading', {}),
                    "system": config_manager.get('system', {}),
                    "features": config_manager.get('features', {})
                }
                
                # 移除敏感信息
                if 'api' in safe_config:
                    del safe_config['api']
                
                return jsonify(self.formatter.success(safe_config, "Configuration retrieved"))
                
            except Exception as e:
                self.logger.error(f"Failed to get config: {e}")
                return jsonify(self.formatter.error(str(e), "CONFIG_ERROR"))
        
        @self.app.route('/api/v1/config', methods=['PUT'])
        async def update_config():
            """更新配置"""
            try:
                data = await request.get_json()
                if not data:
                    return jsonify(self.formatter.error("No data provided", "NO_DATA"))
                
                config_manager = self.trading_system.config_manager
                
                # 更新配置
                for key, value in data.items():
                    if key not in ['api']:  # 不允许通过API更新敏感配置
                        config_manager.update(key, value)
                
                return jsonify(self.formatter.success(None, "Configuration updated successfully"))
                
            except Exception as e:
                self.logger.error(f"Failed to update config: {e}")
                return jsonify(self.formatter.error(str(e), "CONFIG_UPDATE_ERROR"))
        
        # 统计信息API
        @self.app.route('/api/v1/statistics')
        async def get_statistics():
            """获取统计信息"""
            try:
                db_manager = self.trading_system.db_manager
                trading_engine = self.trading_system.get_component('trading_engine')
                
                if not db_manager:
                    return jsonify(self.formatter.error("Database not available", "DB_ERROR"))
                
                # 获取系统状态
                system_state = await db_manager.get_system_state()
                
                # 获取订单统计
                all_orders = await db_manager.get_orders()
                filled_orders = [o for o in all_orders if o.status == OrderStatus.FILLED]
                
                # 计算统计信息
                statistics = {
                    "system": {
                        "uptime_seconds": int((datetime.now() - self.trading_system.startup_time).total_seconds()),
                        "running": system_state.running,
                        "current_price": float(system_state.current_price),
                        "total_balance": float(system_state.total_balance),
                        "total_pnl": float(system_state.total_pnl)
                    },
                    "trading": {
                        "total_orders": len(all_orders),
                        "active_orders": len([o for o in all_orders if o.status == OrderStatus.NEW]),
                        "filled_orders": len(filled_orders),
                        "fill_rate": len(filled_orders) / len(all_orders) * 100 if all_orders else 0
                    },
                    "performance": {
                        "total_profit": sum(float(o.profit) for o in filled_orders),
                        "average_profit_per_trade": sum(float(o.profit) for o in filled_orders) / len(filled_orders) if filled_orders else 0,
                        "profitable_trades": len([o for o in filled_orders if o.profit > 0]),
                        "win_rate": len([o for o in filled_orders if o.profit > 0]) / len(filled_orders) * 100 if filled_orders else 0
                    }
                }
                
                # 添加引擎统计
                if trading_engine:
                    engine_status = await trading_engine.get_status()
                    statistics["engine"] = {
                        "orders_created": engine_status.get("orders_created", 0),
                        "orders_filled": engine_status.get("orders_filled", 0),
                        "uptime_seconds": engine_status.get("uptime_seconds", 0)
                    }
                
                return jsonify(self.formatter.success(statistics, "Statistics retrieved"))
                
            except Exception as e:
                self.logger.error(f"Failed to get statistics: {e}")
                return jsonify(self.formatter.error(str(e), "STATISTICS_ERROR"))
        
        # WebSocket端点
        @self.app.websocket('/ws')
        async def websocket_endpoint():
            """WebSocket端点"""
            self.ws_manager.add_connection(websocket._get_current_object())
            
            try:
                # 发送初始状态
                await self._send_initial_status(websocket._get_current_object())
                
                # 处理客户端消息
                async for message in websocket:
                    await self._handle_websocket_message(websocket._get_current_object(), message)
                    
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
            finally:
                self.ws_manager.remove_connection(websocket._get_current_object())
        
        # 错误处理
        @self.app.errorhandler(404)
        async def not_found(error):
            return jsonify(self.formatter.error("Resource not found", "NOT_FOUND")), 404
        
        @self.app.errorhandler(500)
        async def internal_error(error):
            return jsonify(self.formatter.error("Internal server error", "INTERNAL_ERROR")), 500
    
    async def _send_initial_status(self, ws):
        """发送初始状态到WebSocket"""
        try:
            trading_engine = self.trading_system.get_component('trading_engine')
            if trading_engine:
                status = await trading_engine.get_status()
                await self.ws_manager.send_to_connection(ws, {
                    "type": "initial_status",
                    "data": status,
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Failed to send initial status: {e}")
    
    async def _handle_websocket_message(self, ws, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.ws_manager.send_to_connection(ws, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            elif message_type == 'subscribe':
                # 处理订阅请求
                channels = data.get('channels', [])
                await self._handle_subscription(ws, channels)
            elif message_type == 'get_status':
                # 发送当前状态
                await self._send_initial_status(ws)
            else:
                await self.ws_manager.send_to_connection(ws, {
                    "type": "error",
                    "message": f"Unknown message type: {message_type}",
                    "timestamp": datetime.now().isoformat()
                })
                
        except json.JSONDecodeError:
            await self.ws_manager.send_to_connection(ws, {
                "type": "error",
                "message": "Invalid JSON message",
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_subscription(self, ws, channels: List[str]):
        """处理订阅请求"""
        try:
            # 发送订阅确认
            await self.ws_manager.send_to_connection(ws, {
                "type": "subscription_confirmed",
                "channels": channels,
                "timestamp": datetime.now().isoformat()
            })
            
            # 根据订阅的频道发送相应数据
            for channel in channels:
                if channel == 'status':
                    await self._send_initial_status(ws)
                elif channel == 'orders':
                    await self._send_orders_update(ws)
                # 可以添加更多频道
                
        except Exception as e:
            self.logger.error(f"Error handling subscription: {e}")
    
    async def _send_orders_update(self, ws):
        """发送订单更新"""
        try:
            db_manager = self.trading_system.db_manager
            if db_manager:
                orders = await db_manager.get_orders(status=OrderStatus.NEW)
                orders_data = [order.to_dict() for order in orders[:20]]  # 限制数量
                
                await self.ws_manager.send_to_connection(ws, {
                    "type": "orders_update",
                    "data": orders_data,
                    "timestamp": datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.error(f"Failed to send orders update: {e}")
    
    def _setup_background_tasks(self):
        """设置后台任务"""
        async def status_broadcaster():
            """状态广播任务"""
            while True:
                try:
                    await asyncio.sleep(10)  # 每10秒广播一次
                    
                    trading_engine = self.trading_system.get_component('trading_engine')
                    if trading_engine and self.ws_manager.connections:
                        status = await trading_engine.get_status()
                        await self.ws_manager.broadcast({
                            "type": "status_update",
                            "data": status,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    self.logger.error(f"Status broadcaster error: {e}")
                    await asyncio.sleep(30)
        
        # 启动后台任务
        asyncio.create_task(status_broadcaster())
    
    def _get_dashboard_html(self) -> str:
        """获取仪表板HTML"""
        return '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>网格交易系统监控面板</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { 
            background: rgba(255, 255, 255, 0.1); 
            border-radius: 15px; 
            padding: 20px; 
            margin: 20px 0; 
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .status-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
        }
        .status-indicator { 
            width: 12px; 
            height: 12px; 
            border-radius: 50%; 
            display: inline-block; 
            margin-right: 8px; 
        }
        .status-running { background: #10B981; }
        .status-stopped { background: #EF4444; }
        .btn { 
            padding: 10px 20px; 
            border: none; 
            border-radius: 8px; 
            cursor: pointer; 
            margin: 5px; 
            background: rgba(255, 255, 255, 0.2);
            color: white;
            transition: all 0.3s ease;
        }
        .btn:hover { background: rgba(255, 255, 255, 0.3); }
        .btn-primary { background: #3B82F6; }
        .btn-danger { background: #EF4444; }
        #log { 
            background: rgba(0, 0, 0, 0.3); 
            padding: 15px; 
            border-radius: 8px; 
            height: 200px; 
            overflow-y: auto; 
            font-family: monospace; 
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 网格交易系统监控面板</h1>
        
        <div class="status-grid">
            <div class="card">
                <h3>系统状态</h3>
                <div id="system-status">
                    <span class="status-indicator status-stopped"></span>
                    <span>未连接</span>
                </div>
                <div style="margin-top: 10px;">
                    <button class="btn btn-primary" onclick="startTrading()">启动交易</button>
                    <button class="btn btn-danger" onclick="stopTrading()">停止交易</button>
                </div>
            </div>
            
            <div class="card">
                <h3>交易信息</h3>
                <div>当前价格: $<span id="current-price">--</span></div>
                <div>活跃订单: <span id="active-orders">--</span></div>
                <div>总盈亏: $<span id="total-pnl">--</span></div>
            </div>
            
            <div class="card">
                <h3>账户信息</h3>
                <div>总余额: $<span id="total-balance">--</span></div>
                <div>可用余额: $<span id="available-balance">--</span></div>
                <div>运行时间: <span id="uptime">--</span></div>
            </div>
        </div>
        
        <div class="card">
            <h3>系统日志</h3>
            <div id="log"></div>
        </div>
    </div>

    <script>
        let ws = null;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = function() {
                addLog('WebSocket连接已建立');
                ws.send(JSON.stringify({type: 'subscribe', channels: ['status', 'orders']}));
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                addLog('WebSocket连接已断开，5秒后重连...');
                setTimeout(connectWebSocket, 5000);
            };
            
            ws.onerror = function(error) {
                addLog('WebSocket错误: ' + error);
            };
        }
        
        function handleWebSocketMessage(data) {
            switch(data.type) {
                case 'initial_status':
                case 'status_update':
                    updateStatus(data.data);
                    break;
                case 'trading_status':
                    updateTradingStatus(data.data.running);
                    break;
                default:
                    addLog(`收到消息: ${data.type}`);
            }
        }
        
        function updateStatus(status) {
            document.getElementById('current-price').textContent = status.current_price || '--';
            document.getElementById('total-balance').textContent = status.total_balance || '--';
            document.getElementById('available-balance').textContent = status.available_balance || '--';
            document.getElementById('total-pnl').textContent = status.total_pnl || '--';
            
            if (status.uptime_seconds) {
                document.getElementById('uptime').textContent = formatUptime(status.uptime_seconds);
            }
            
            updateTradingStatus(status.running);
        }
        
        function updateTradingStatus(running) {
            const statusElement = document.getElementById('system-status');
            if (running) {
                statusElement.innerHTML = '<span class="status-indicator status-running"></span><span>运行中</span>';
            } else {
                statusElement.innerHTML = '<span class="status-indicator status-stopped"></span><span>已停止</span>';
            }
        }
        
        function formatUptime(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return `${hours}小时${minutes}分钟`;
        }
        
        function addLog(message) {
            const log = document.getElementById('log');
            const time = new Date().toLocaleTimeString();
            log.innerHTML += `[${time}] ${message}<br>`;
            log.scrollTop = log.scrollHeight;
        }
        
        async function startTrading() {
            try {
                const response = await fetch('/api/v1/trading/start', {method: 'POST'});
                const data = await response.json();
                if (data.success) {
                    addLog('交易启动成功');
                } else {
                    addLog('交易启动失败: ' + data.error.message);
                }
            } catch (error) {
                addLog('启动交易请求失败: ' + error.message);
            }
        }
        
        async function stopTrading() {
            try {
                const response = await fetch('/api/v1/trading/stop', {method: 'POST'});
                const data = await response.json();
                if (data.success) {
                    addLog('交易停止成功');
                } else {
                    addLog('交易停止失败: ' + data.error.message);
                }
            } catch (error) {
                addLog('停止交易请求失败: ' + error.message);
            }
        }
        
        // 页面加载时连接WebSocket
        window.onload = function() {
            connectWebSocket();
            addLog('监控面板已加载');
        };
    </script>
</body>
</html>
        '''
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """启动Web服务器"""
        try:
            config = Config()
            config.bind = [f"{host}:{port}"]
            config.use_reloader = False
            config.access_log_format = "%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\""
            
            self.logger.info(f"Starting web server on http://{host}:{port}")
            
            await serve(self.app, config)
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
            raise TradingSystemError(f"Web server startup failed: {e}")

# 使用示例
async def create_web_service(trading_system: TradingSystem) -> WebAPIService:
    """创建Web API服务"""
    web_service = WebAPIService(trading_system)
    return web_service