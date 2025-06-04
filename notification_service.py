# notification_service.py - 通知服务
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional
from data_models import TradingConfig

class NotificationService:
    """简化的通知服务"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.last_notification_times = {}
        self.rate_limit_seconds = 60  # 1分钟内同类型消息只发送一次
    
    async def send_message(self, message: str, message_type: str = "info") -> bool:
        """发送消息"""
        if not self.config.enable_notifications or not self.config.telegram_token:
            return False
        
        # 检查频率限制
        if not self._should_send_notification(message_type):
            return False
        
        try:
            success = await self._send_telegram_message(message)
            if success:
                self._update_notification_time(message_type)
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            return False
    
    async def send_trade_notification(self, trade_data: dict) -> bool:
        """发送交易通知"""
        side_emoji = "🟢" if trade_data["side"] == "BUY" else "🔴"
        grid_emoji = self._get_grid_emoji(trade_data.get("grid_level", ""))
        
        message = f"""
{side_emoji} *交易成交* {grid_emoji}

💱 *交易对:* `{trade_data.get("symbol", "")}`
📊 *方向:* `{trade_data["side"]}`
💰 *价格:* `${trade_data["price"]:.2f}`
📈 *数量:* `{trade_data["quantity"]:.6f}`
💵 *金额:* `${trade_data["price"] * trade_data["quantity"]:.2f}`
🎯 *网格:* `{self._get_grid_name(trade_data.get("grid_level", ""))}`

⏰ `{datetime.now().strftime('%H:%M:%S')}`
        """
        
        return await self.send_message(message.strip(), "trade")
    
    async def send_profit_notification(self, profit_data: dict) -> bool:
        """发送盈利通知"""
        profit = profit_data.get("profit", 0)
        emoji = "🎉" if profit > 0 else "📉"
        
        message = f"""
{emoji} *盈利更新*

💰 *实现盈亏:* `{profit:+.2f} USDT`
📊 *累计盈亏:* `{profit_data.get("total_pnl", 0):+.2f} USDT`
📈 *胜率:* `{profit_data.get("win_rate", 0):.1f}%`
🎯 *总交易:* `{profit_data.get("total_trades", 0)}` 笔

⏰ `{datetime.now().strftime('%H:%M:%S')}`
        """
        
        return await self.send_message(message.strip(), "profit")
    
    async def send_risk_alert(self, risk_data: dict) -> bool:
        """发送风险告警"""
        level = risk_data.get("level", "medium")
        emoji = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}.get(level, "⚠️")
        
        message = f"""
{emoji} *风险告警*

🚨 *级别:* `{level.upper()}`
📝 *详情:* {risk_data.get("message", "无详细信息")}
💰 *当前回撤:* `{risk_data.get("drawdown", 0):.2f}%`
🛡️ *建议:* {risk_data.get("suggestion", "请检查系统状态")}

⏰ `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
        """
        
        return await self.send_message(message.strip(), "risk")
    
    async def send_system_notification(self, system_data: dict) -> bool:
        """发送系统通知"""
        status = system_data.get("status", "unknown")
        emoji = {"starting": "🚀", "running": "✅", "stopping": "🛑", "error": "❌"}.get(status, "ℹ️")
        
        message = f"""
{emoji} *系统状态*

📊 *状态:* `{system_data.get("message", status)}`
💰 *当前价格:* `${system_data.get("current_price", 0):.2f}`
🎯 *活跃订单:* `{system_data.get("active_orders", 0)}` 个
⏱️ *运行时间:* `{self._format_uptime(system_data.get("uptime_seconds", 0))}`

⏰ `{datetime.now().strftime('%H:%M:%S')}`
        """
        
        return await self.send_message(message.strip(), "system")
    
    async def send_daily_report(self, report_data: dict) -> bool:
        """发送日报"""
        total_pnl = report_data.get("total_pnl", 0)
        daily_pnl = report_data.get("daily_pnl", 0)
        emoji = "📈" if daily_pnl >= 0 else "📉"
        
        message = f"""
{emoji} *每日交易报告*

💰 *今日盈亏:* `{daily_pnl:+.2f} USDT`
📊 *累计盈亏:* `{total_pnl:+.2f} USDT`
📈 *日收益率:* `{report_data.get("daily_return", 0):+.2f}%`

🎯 *交易数据:*
• 今日交易: `{report_data.get("daily_trades", 0)}` 笔
• 累计交易: `{report_data.get("total_trades", 0)}` 笔
• 整体胜率: `{report_data.get("win_rate", 0):.1f}%`

🏷️ *网格状态:*
• 高频层: `{report_data.get("high_freq_integrity", 0):.1f}%`
• 主趋势: `{report_data.get("main_trend_integrity", 0):.1f}%`
• 保险层: `{report_data.get("insurance_integrity", 0):.1f}%`

🛡️ *风险指标:*
• 最大回撤: `{report_data.get("max_drawdown", 0):.2f}%`
• 当前回撤: `{report_data.get("current_drawdown", 0):.2f}%`

⏰ `{datetime.now().strftime('%Y-%m-%d')}`
        """
        
        return await self.send_message(message.strip(), "daily_report")
    
    async def _send_telegram_message(self, message: str) -> bool:
        """发送Telegram消息"""
        try:
            url = f"https://api.telegram.org/bot{self.config.telegram_token}/sendMessage"
            data = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        self.logger.info("Telegram message sent successfully")
                        return True
                    else:
                        response_text = await response.text()
                        self.logger.error(f"Telegram API error: {response.status} - {response_text}")
                        return False
                        
        except asyncio.TimeoutError:
            self.logger.error("Telegram message timeout")
            return False
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    def _should_send_notification(self, message_type: str) -> bool:
        """检查是否应该发送通知（频率限制）"""
        current_time = datetime.now()
        last_time = self.last_notification_times.get(message_type)
        
        if last_time is None:
            return True
        
        time_diff = (current_time - last_time).total_seconds()
        
        # 不同类型的消息有不同的频率限制
        limits = {
            "trade": 30,        # 交易通知30秒间隔
            "profit": 300,      # 盈利通知5分钟间隔
            "risk": 60,         # 风险告警1分钟间隔
            "system": 60,       # 系统通知1分钟间隔
            "daily_report": 3600, # 日报1小时间隔
            "info": 60          # 普通信息1分钟间隔
        }
        
        limit = limits.get(message_type, self.rate_limit_seconds)
        return time_diff >= limit
    
    def _update_notification_time(self, message_type: str):
        """更新通知时间"""
        self.last_notification_times[message_type] = datetime.now()
    
    def _get_grid_emoji(self, grid_level: str) -> str:
        """获取网格层级对应的emoji"""
        emojis = {
            "high_freq": "⚡",
            "main_trend": "🎯", 
            "insurance": "🛡️"
        }
        return emojis.get(grid_level, "📊")
    
    def _get_grid_name(self, grid_level: str) -> str:
        """获取网格层级名称"""
        names = {
            "high_freq": "高频套利层",
            "main_trend": "主趋势层",
            "insurance": "保险层"
        }
        return names.get(grid_level, grid_level)
    
    def _format_uptime(self, seconds: int) -> str:
        """格式化运行时间"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}小时{minutes}分钟"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}天{hours}小时"
    
    def test_connection(self) -> bool:
        """测试Telegram连接"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_message("🔧 Telegram连接测试成功！", "test"))
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
            return False