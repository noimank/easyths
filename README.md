<p align="center">
  <a href="https://pypi.org/project/easyths/"><img src="https://img.shields.io/pypi/v/easyths?logo=pypi&logoColor=white&label=PyPI&color=blue" alt="PyPI Version"></a>
  <a href="https://github.com/noimank/easyths"><img src="https://img.shields.io/badge/python-3.12+-blue.svg?logo=python&logoColor=white" alt="Python Version"></a>
  <a href="https://github.com/noimank/easyths/blob/main/LICENSE"><img src="https://img.shields.io/github/license/noimank/easyths?color=green" alt="License"></a>
  <a href="https://github.com/noimank/easyths/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/noimank/easyths/ci.yml?branch=main&label=CI" alt="CI"></a>
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi" alt="FastAPI"></a>
  <a href="https://pywinauto.readthedocs.io/"><img src="https://img.shields.io/badge/pywinauto-0.6.8+-orange?logoColor=white" alt="pywinauto"></a>
  <a href="https://pydantic.dev/"><img src="https://img.shields.io/badge/Pydantic-2.10+-red?logo=pydantic" alt="Pydantic"></a>
  <a href="https://www.uvicorn.org/"><img src="https://img.shields.io/badge/Uvicorn-0.32+-teal?logo=uvicorn&logoColor=white" alt="Uvicorn"></a>
</p>

# EasyTHS - 同花顺交易自动化系统

基于 pywinauto 的同花顺交易软件自动化项目，提供 RESTful API 接口，通过操作队列确保高并发下的操作顺序和一致性。

## 项目特点

- **操作串行化**：所有 GUI 操作串行执行，避免并发冲突
- **队列管理**：支持优先级的任务队列，确保操作顺序
- **错误恢复**：完整的错误处理和恢复机制
- **实时监控**：详细的日志记录和状态监控
- **RESTful API**：完整的 HTTP 接口，支持各种语言集成

## 文档

详细文档请访问：[https://noimank.github.io/easyths/](https://noimank.github.io/easyths/)

- [安装指南](https://noimank.github.io/easyths/getting-started/installation/)
- [基础用法](https://noimank.github.io/easyths/getting-started/basic-usage/)
- [客户端设置](https://noimank.github.io/easyths/getting-started/ths-client/)
- [Client SDK](https://noimank.github.io/easyths/getting-started/client-sdk/) - Python 客户端 SDK
- [API 参考](https://noimank.github.io/easyths/api/)

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.12+
- 同花顺交易客户端

### 安装

```bash
# 使用 uvx 一键运行服务端（推荐）
uvx easyths[server]

# 或使用 pip 安装服务端
pip install easyths[server]
easyths
```

服务默认运行在 `http://127.0.0.1:7648`

更多安装方式请参考 [安装指南](https://noimank.github.io/easyths/getting-started/installation/)。

## 支持的操作

| 操作 | 说明 | 参考操作耗时（秒） |
|------|------|------|
| **买入 (buy)** | 股票买入委托 | 1.5~2.0 |
| **卖出 (sell)** | 股票卖出委托 | 1.5~2.0 |
| **持仓查询 (holding_query)** | 查询当前持仓 | 1.6~3.2 |
| **资金查询 (funds_query)** | 查询账户资金 | 0.6~1.0 |
| **委托查询 (order_query)** | 查询委托记录 | 2.8~3.3 |
| **撤单 (order_cancel)** | 撤销委托 | 1.0~1.6 |
| **历史委托查询 (historical_commission_query)** 模拟账号不支持 | 查询历史成交 | 2.8~3.3 |
| **国债逆回购购买 (reverse_repo_buy)** | 购买国债逆回购 | 1.8~2.2 |
| **国债逆回购年化利率查询 (reverse_repo_query)** | 查询国债逆回购年化利率 | 0.9~1.3 |
| **条件买入 (condition_buy)** | 设置条件买入策略 | 2.4~3.1 |
| **止盈止损 (stop_loss_profit)** | 设置止盈止损策略 | 2.6~3.2 |
| **条件单查询 (condition_order_query)** | 查询现有的条件单 | 1.7~2.1 |
| **条件单删除 (condition_order_cancel)** | 删除指定条件单 | 2.0~2.5 |

详细的 API 接口和参数说明请参考 [API 文档](https://noimank.github.io/easyths/getting-started/api/)。

## 快速示例

### 使用 Python SDK（推荐）

```bash
# 仅安装客户端 SDK（轻量级，跨平台）
pip install easyths
```

```python
from easyths import TradeClient

# 创建客户端
with TradeClient(host="127.0.0.1", port=7648, api_key="your-api-key") as client:
    # 买入股票
    result = client.buy("000001", 10.50, 100)
    if result["data"]["result"]["success"]:
        print("买入成功")

    # 查询持仓
    result = client.query_holdings()
    holdings = result["data"]["result"]["data"]["holdings"]
    print(f"持仓数: {len(holdings)}")
```

更多 SDK 用法请参考 [Client SDK 文档](https://noimank.github.io/easyths/getting-started/client-sdk/)。

### 使用 cURL API

```bash
# 启动服务
uvx easyths[server]

# 买入股票
curl -X POST http://127.0.0.1:7648/api/v1/operations/buy \
  -H "Content-Type: application/json" \
  -d '{"params": {"stock_code": "000001", "price": 10.50, "quantity": 100}}'

# 查询持仓
curl -X POST http://127.0.0.1:7648/api/v1/operations/holding_query \
  -H "Content-Type: application/json" \
  -d '{}'
```

更多使用示例请参考 [基础用法](https://noimank.github.io/easyths/getting-started/basic-usage/)。

## 系统要求

- **操作系统**: Windows 10/11（必须，pywinauto 要求）
- **Python**: 3.12+
- **交易软件**: 同花顺交易客户端

## 同花顺客户端设置

> 详细的配置步骤请查看 [客户端设置指南](https://noimank.github.io/easyths/getting-started/ths-client/)

必须完成的设置：
1. 关闭悬浮工具栏
2. 关闭所有交易确认对话框
3. 开启"切换页面清空代码"
4. 清空默认买入/卖出价格

这些设置对于自动化交易系统的正常运行至关重要，请务必按照文档完成配置。

## 安全须知

- 本系统仅供学习和研究使用
- 自动化交易存在风险，请谨慎使用
- 建议先在模拟环境测试
- 请保护好 API 密钥安全

## 许可证

MIT License

## 联系方式

- **作者**: noimank
- **邮箱**: noimank@163.com
- **仓库**: [https://github.com/noimank/easyths](https://github.com/noimank/easyths)

---

<div align="center">
  <p>如果这个项目对您有帮助，请给个 ⭐ Star 支持一下！</p>
</div>