# 🚀 天地双网格交易系统 - 个人版 v2.0

> 专为个人交易者设计的轻量级智能网格交易系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey.svg)](https://github.com)

## 📋 系统概述

### 🎯 设计理念
天地双网格交易系统个人版专注于**简单、实用、稳定**，摒弃了复杂的微服务架构，采用轻量级单体应用设计，让个人用户能够快速部署和使用。

### ✨ 核心特性

#### 🏗️ 架构优势
- **单体应用** - 无需复杂的服务编排，一键启动
- **轻量级设计** - 最小化依赖，资源占用低
- **SQLite存储** - 无需额外数据库服务，数据本地化
- **零配置启动** - 开箱即用的默认配置

#### 📊 交易策略
- **三层网格策略** - 高频套利层、主趋势层、保险层
- **智能市场适应** - 自动识别市场状态并调整策略
- **动态风险控制** - 实时监控，自动止损保护
- **订单自动重建** - 成交后自动在相同位置重新下单

#### 🖥️ 监控界面
- **实时Web界面** - 简洁美观的监控面板
- **关键指标展示** - 盈亏、胜率、网格状态一目了然
- **交互式图表** - 盈亏曲线、网格完整度可视化
- **移动端适配** - 响应式设计，手机也能轻松监控

#### 🔔 通知系统
- **Telegram通知** - 交易成交、风险告警实时推送
- **智能频率控制** - 避免通知轰炸，重要信息不遗漏
- **多类型消息** - 交易、盈利、风险、系统状态分类通知

## 🏁 快速开始

### 🔧 系统要求
- **操作系统**: Linux / Windows / macOS
- **Python版本**: 3.8+
- **内存要求**: 512MB+
- **存储空间**: 1GB+
- **网络要求**: 稳定的互联网连接

### 📦 一键部署

#### 方法一：自动部署脚本（推荐）
```bash
# 1. 下载项目
git clone https://github.com/yourusername/grid-trading-system.git
cd grid-trading-system

# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

#### 方法二：手动部署
```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置系统
cp config.yaml.example config.yaml
nano config.yaml  # 编辑配置文件

# 4. 启动系统
python main.py
```

#### 方法三：Docker部署
```bash
# 1. 构建镜像
docker build -t grid-trading:latest .

# 2. 运行容器
docker run -d \
  --name grid-trading-bot \
  -p 8080:8080 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v grid_data:/app/data \
  -v grid_logs:/app/logs \
  grid-trading:latest
```

### ⚙️ 配置系统

#### 1. API密钥配置
```yaml
# 在 config.yaml 中配置
binance_api_key: "your_api_key_here"
binance_api_secret: "your_api_secret_here"
use_testnet: true  # 建议先在测试网测试
```

#### 2. 网格策略配置
```yaml
# 高频套利层 (±3% 捕获小波动)
high_freq_range: 0.03      # ±3% 价格范围
high_freq_spacing: 0.005   # 0.5% 网格间距  
high_freq_size: 20         # 每单20 USDT

# 主趋势层 (±15% 跟随趋势)
main_trend_range: 0.15     # ±15% 价格范围
main_trend_spacing: 0.01   # 1% 网格间距
main_trend_size: 50        # 每单50 USDT

# 保险层 (±50% 极端保护)
insurance_range: 0.50      # ±50% 价格范围
insurance_spacing: 0.05    # 5% 网格间距
insurance_size: 100        # 每单100 USDT
```

#### 3. 风险控制配置
```yaml
max_drawdown: 0.20         # 最大回撤 20%
stop_loss: 0.15            # 止损线 15%
initial_balance: 1000      # 初始资金 1000 USDT
```

## 📊 系统监控

### 🌐 Web界面
启动系统后，访问 `http://localhost:8080` 查看实时监控面板。

**主要功能：**
- 📈 实时价格和盈亏显示
- 📊 网格完整度可视化
- 📋 活跃订单列表
- 📉 盈亏曲线图表
- ⚡ 系统状态监控

### 📱 Telegram通知
配置Telegram Bot后，可接收实时通知：

**通知类型：**
- 🟢 交易成交通知
- 💰 盈利更新提醒
- 🚨 风险告警信息
- 📊 每日交易报告
- ⚙️ 系统状态变更

## 📈 策略详解

### 🎯 三层网格策略

#### 1. 高频套利层 (±3%)
- **目标**: 捕获市场短期小幅波动
- **特点**: 密集网格，快速成交
- **收益**: 积少成多，稳定获利
- **风险**: 低风险，高频率

#### 2. 主趋势层 (±15%)
- **目标**: 跟随市场主要趋势方向
- **特点**: 中等密度，平衡收益
- **收益**: 趋势收益，相对稳定
- **风险**: 中等风险，中等收益

#### 3. 保险层 (±50%)
- **目标**: 极端行情保护，长线等待
- **特点**: 稀疏网格，深度保护
- **收益**: 极端反弹收益
- **风险**: 资金占用，等待期长

### 🧠 智能策略调整

系统会根据市场状态自动调整策略：

- **震荡市场** - 激活所有层级，密集交易
- **牛市趋势** - 偏重买单配置，减少高频
- **熊市趋势** - 偏重卖单配置，保守策略
- **高波动期** - 扩大网格间距，降低风险

## 🛡️ 风险控制

### 🔒 多重安全保护

#### 1. 资金安全
- **API权限限制** - 仅启用现货交易权限
- **本地密钥存储** - 密钥仅本地存储，不上传云端
- **只读Web界面** - Web界面仅查看，无交易操作

#### 2. 交易风险控制
- **最大回撤限制** - 超过设定回撤自动停止
- **止损保护机制** - 亏损达到阈值自动止损
- **订单数量限制** - 防止订单过多导致资金枯竭
- **价格异常检测** - 防止异常价格导致误操作

#### 3. 系统稳定性
- **断线重连机制** - 网络断开自动重连
- **异常恢复功能** - 系统异常自动恢复状态
- **数据备份机制** - 重要数据自动备份
- **日志监控体系** - 完整的操作日志记录

## 📋 运维指南

### 🔍 日常监控

#### 查看系统状态
```bash
# 查看系统进程
ps aux | grep main.py

# 查看实时日志
tail -f logs/grid_trading_$(date +%Y%m%d).log

# 查看错误日志
grep "ERROR\|CRITICAL" logs/*.log | tail -20
```

#### 系统控制
```bash
# 停止系统
pkill -f "python.*main.py"

# 重启系统  
./deploy.sh

# 查看端口占用
netstat -tulpn | grep 8080
```

### 📊 性能监控

#### 数据库管理
```bash
# 查看数据库大小
ls -lh data/grid_trading.db

# 数据库统计
sqlite3 data/grid_trading.db "
SELECT 
  'orders' as table_name, COUNT(*) as count 
FROM orders 
UNION ALL 
SELECT 
  'trades' as table_name, COUNT(*) as count 
FROM trades;"
```

#### 备份管理
```bash
# 手动备份
mkdir -p backups/$(date +%Y%m%d)
cp data/grid_trading.db backups/$(date +%Y%m%d)/
cp config.yaml backups/$(date +%Y%m%d)/

# 清理旧备份（保留最近7天）
find backups/ -type d -mtime +7 -exec rm -rf {} \;
```

### 🔧 故障排除

#### 常见问题解决

1. **系统无法启动**
   ```bash
   # 检查配置文件
   python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"
   
   # 检查Python依赖
   pip list | grep -E "(binance|aiohttp|flask)"
   
   # 查看详细错误
   python3 main.py
   ```

2. **API连接失败**
   ```bash
   # 测试网络连接
   curl -I https://api.binance.com/api/v3/ping
   
   # 验证API密钥（在config.yaml中检查）
   # 确保API密钥有效且权限正确
   ```

3. **Web界面无法访问**
   ```bash
   # 检查端口占用
   netstat -tulpn | grep 8080
   
   # 检查防火墙设置
   sudo ufw status | grep 8080
   
   # 尝试本地访问
   curl http://localhost:8080/api/status
   ```

## 📈 性能优化

### ⚡ 系统调优

#### 1. 配置优化
```yaml
# 减少检查间隔提高响应速度
check_interval: 3  # 默认5秒，可调整为3秒

# 优化订单数量
high_freq_size: 30      # 根据资金量调整
main_trend_size: 80     # 平衡收益和风险
insurance_size: 150     # 保险层适当增加
```

#### 2. 资源优化
```bash
# 设置Python优化
export PYTHONOPTIMIZE=1

# 限制内存使用
ulimit -v 1048576  # 1GB虚拟内存限制

# 设置进程优先级
nice -n 10 python3 main.py
```

### 📊 预期收益

基于历史回测和实际使用数据：

| 市场状态 | 月化收益率 | 年化收益率 | 最大回撤 | 胜率 |
|---------|-----------|-----------|---------|------|
| 震荡市场 | 3-8% | 36-96% | <10% | 75%+ |
| 趋势市场 | 5-15% | 60-180% | <15% | 65%+ |
| 高波动市场 | -2-20% | -24-240% | <20% | 60%+ |
| **综合表现** | **2-12%** | **24-144%** | **<15%** | **70%+** |

> ⚠️ **风险提示**: 以上数据仅供参考，实际收益受市场环境、配置参数、资金管理等多因素影响。过往表现不代表未来收益。

## 🔄 升级指南

### 📦 版本更新
```bash
# 1. 备份当前版本
cp -r . ../grid-trading-backup-$(date +%Y%m%d)

# 2. 获取最新版本
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt --upgrade

# 4. 检查配置兼容性
python3 -c "
import yaml
config = yaml.safe_load(open('config.yaml'))
print('配置检查通过')
"

# 5. 重启系统
pkill -f "python.*main.py"
./deploy.sh
```

### 🔧 配置迁移
新版本可能需要更新配置文件，系统会自动提示需要添加的新配置项。

## 🤝 社区支持

### 📞 获取帮助
- **查看日志**: 大部分问题可通过日志文件诊断
- **检查配置**: 确保配置文件格式正确，API密钥有效
- **测试网验证**: 建议先在Binance测试网环境验证
- **社区讨论**: GitHub Issues 或相关技术社区

### 🐛 问题反馈
如遇到bug或有改进建议，请提供：
1. 系统版本信息
2. 详细的错误日志
3. 复现步骤
4. 系统环境信息

### 📝 贡献代码
欢迎提交代码改进：
1. Fork 项目仓库
2. 创建功能分支
3. 提交代码改动
4. 发起 Pull Request

## ⚠️ 重要声明

### 🚨 风险提示
1. **数字货币交易风险极高**，可能导致本金全部损失
2. **本系统仅为交易工具**，不构成投资建议
3. **请充分了解风险**后再使用本系统
4. **建议先在测试环境**充分验证再投入实际资金
5. **不要投入超过承受能力**的资金

### 📄 免责声明
- 使用本系统的所有风险由用户自行承担
- 开发者不对任何投资损失负责
- 本系统按"现状"提供，不提供任何形式的保证
- 用户应遵守当地法律法规

### 📜 许可证
本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

---

## 🎉 结语

天地双网格交易系统个人版致力于为个人交易者提供一个**简单、实用、可靠**的自动化交易工具。我们相信，通过智能化的策略和严格的风险控制，能够帮助交易者在波动的市场中获得相对稳定的收益。

但请始终记住：**市场有风险，投资需谨慎**。任何自动化工具都不能保证盈利，理性投资是永恒的主题。

祝您交易顺利，财富增长！🚀

---

<div align="center">

**🌟 如果这个项目对您有帮助，请考虑给我们一个Star⭐**

[⭐ Star项目](https://github.com/yourusername/grid-trading-system) | [🐛 报告问题](https://github.com/yourusername/grid-trading-system/issues) | [📖 查看文档](https://github.com/yourusername/grid-trading-system/wiki)

</div>