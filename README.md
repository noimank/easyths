# QuantTrader - 同花顺交易自动化系统

基于pywinauto的同花顺交易软件自动化项目，提供RESTful API接口，确保操作顺序和避免高并发下的操作序列错误。

## 🚀 项目特点

- **操作串行化**：所有GUI操作串行执行，避免并发冲突
- **事务一致性**：确保操作的原子性和一致性
- **插件化架构**：高度可扩展，便于添加新的自动化操作
- **错误恢复**：完整的错误处理和恢复机制
- **实时监控**：详细的日志记录和状态监控
- **RESTful API**：完整的HTTP接口，支持各种语言集成

## 📚 文档

- [📖 快速入门](docs/快速入门.md) - 快速搭建和使用指南
- [🔌 API接口文档](docs/API接口文档.md) - 完整的REST API接口说明
- [🛠️ 开发指南](docs/开发指南.md) - 系统架构和扩展开发方法
- [⚙️ 同花顺客户端设置](docs/同花顺客户端设置.md) - 必要的客户端配置说明

## ⚡ 快速开始

> 详细安装和配置步骤请查看 [快速入门指南](docs/快速入门.md)

### 1. 环境准备
- Windows 10/11
- Python 3.8+
- 同花顺交易客户端

### 2. 安装依赖

```bash
# 克隆项目
git clone https://github.com/your-repo/QuantTrader.git
cd QuantTrader

# 安装依赖
uv sync
```

### 3. 配置系统

复制并编辑配置文件：
```bash
cp .env.example .env
# 编辑 .env 文件，配置同花顺路径和API密钥
```

### 4. 启动服务

```bash
# 启动服务
uv run python -m uvicorn src.main:app --reload

# 或直接运行
uv run python src/main.py
```

服务启动后，访问：
- API文档：http://localhost:7648/docs
- 健康检查：http://localhost:7648/api/v1/system/health

## 💻 主要功能

### 交易操作
- **买入/卖出股票** - 自动执行买卖委托
- **资金查询** - 查询账户资金信息
- **持仓查询** - 获取当前股票持仓
- **批量操作** - 支持顺序或并行执行多个交易

### API 接口
> 完整的API接口文档请参考 [API接口文档](docs/API接口文档.md)

**系统接口**
- `GET /api/v1/system/health` - 系统健康检查
- `GET /api/v1/system/status` - 获取系统状态

**交易接口**
- `POST /api/v1/operations/buy` - 买入股票
- `POST /api/v1/operations/sell` - 卖出股票
- `POST /api/v1/operations/funds_query` - 查询资金
- `POST /api/v1/operations/holding_query` - 查询持仓

**操作管理**
- `GET /api/v1/operations/{id}/status` - 查询操作状态
- `POST /api/v1/operations/batch` - 批量执行操作

### 快速示例

```bash
# 1. 买入股票（需要认证）
curl -X POST http://localhost:7648/api/v1/operations/buy \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"params": {"stock_code": "000001", "price": 10.50, "quantity": 100}}'

# 2. 查询资金
curl -X POST http://localhost:7648/api/v1/operations/funds_query \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"params": {"query_type": "all"}}'
```

## ⚙️ 系统要求

- **操作系统**: Windows 10/11（必须，pywinauto要求）
- **Python**: 3.8+
- **交易软件**: 同花顺交易客户端

## 🏗️ 项目结构

```
QuantTrader/
├── src/
│   ├── api/                    # REST API层
│   ├── automation/             # 自动化层
│   │   └── operations/         # 交易操作插件
│   ├── core/                   # 核心组件（队列、OCR等）
│   ├── models/                 # 数据模型
│   └── utils/                  # 工具函数
├── docs/                       # 文档
├── logs/                       # 日志目录
├── .env.example               # 配置模板
├── pyproject.toml              # 项目配置
└── src/main.py                # 程序入口
```

## ⚠️ 重要提示

### 同花顺客户端设置
> 详细的配置步骤请查看 [同花顺客户端设置指南](docs/同花顺客户端设置.md)

**必须完成的设置**：
1. 关闭悬浮工具栏
2. 关闭所有交易确认对话框
3. 开启"切换页面清空代码"
4. 清空默认买入/卖出价格

这些设置对于自动化交易系统的正常运行至关重要，请务必按照文档完成配置。

### 安全须知
- 本系统仅供学习和研究使用
- 自动化交易存在风险，请谨慎使用
- 建议先在模拟环境测试
- 请保护好API密钥安全

## 🤝 贡献

欢迎提交Issue和Pull Request！详见[开发指南](docs/开发指南.md)。

## 📄 许可证

本项目仅供学习和研究使用，请勿用于实际交易。

## 📞 联系方式

- **作者**: noimank（康康）
- **邮箱**: noimank@163.com

---

<div align="center">
  <p>如果这个项目对您有帮助，请给个 ⭐ Star 支持一下！</p>
</div>