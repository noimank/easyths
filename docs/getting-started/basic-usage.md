# 基础用法

## 启动服务

### 方式一：使用 uvx 一键运行（推荐）

```bash
uvx 'easyths[server]'
```

> **提示**：`uvx` 是 uv 工具提供的命令，可以自动下载并运行 Python 包，无需手动安装。

### 方式二：安装后运行

```bash
# 先安装服务端
pip install 'easyths[server]'

# 运行
easyths
```

### 方式三：使用模块运行

```bash
# 开发环境
python -m easyths.main
```

服务默认运行在 `http://127.0.0.1:7648`。启动后可在浏览器打开
Swagger UI（`/docs`）或 ReDoc（`/redoc`）查看交互式 API 文档，
完整接口说明见 [API 服务](api.md)。

## 命令行选项

| 选项 | 说明 |
|------|------|
| `--exe_path <path>` | 指定同花顺交易程序路径（优先级高于配置文件） |
| `--config <file>` | 指定 TOML 配置文件路径 |
| `--get_config` | 将示例配置文件复制到当前目录 |
| `--version, -v` | 显示版本信息 |
| `--help` | 显示帮助信息 |

```bash
# 使用自定义配置文件启动
uvx 'easyths[server]' --config my_config.toml

# 指定交易程序路径启动（免费版或其他版本）
uvx 'easyths[server]' --exe_path "C:/同花顺/xiadan.exe"

# 生成示例配置文件
uvx 'easyths[server]' --get_config

# 组合使用
uvx 'easyths[server]' --config my_config.toml --exe_path "C:/同花顺/xiadan.exe"
```

## 配置文件

配置文件采用 TOML 格式，分为应用程序、交易程序、队列、API 服务与日志五个部分。
以下为完整示例，也可通过 `uvx 'easyths[server]' --get_config` 生成到当前目录：

```toml
[app]
# 自定义验证码识别模型目录（留空使用内置模型）
# 目录下必须包含 captcha_ocr.onnx 和 captcha_ocr.onnx.data 两个文件
onnx_model_dir = ""
# 是否保存识别错误的验证码图片（保存于 C:/Users/你的用户名/easyths/captcha_error/）
save_error_captcha_image = true

[trading]
app_path = "C:/同花顺远航版/transaction/xiadan.exe"

[queue]
max_size = 1000           # 队列最大容量
# 单操作执行硬超时（秒）：超时后操作以 timeout 失败收尾并自动断开同花顺连接，
# 后续操作将快速失败，需恢复客户端后调用 /api/v1/system/reconnect 重连
operation_timeout = 10.0

[api]
host = "0.0.0.0"           # 服务器地址
port = 7648                # 服务器端口
mcp_server_type = "streamable-http"  # MCP 传输类型: http, streamable-http, sse
rate_limit = 100           # 速率限制（请求/秒）
cors_origins = "*"         # CORS 允许的源（* 表示所有，逗号分隔多个）
key = ""                   # API 密钥（留空不启用；启用后请求需带 Authorization: Bearer <key>）
ip_whitelist = ""          # IP 白名单（留空允许所有，逗号分隔，支持通配符如 192.168.1.*）

[logging]
level = "INFO"             # 日志级别：DEBUG, INFO, WARNING, ERROR
file = ""                  # 日志文件路径（默认 C:/Users/你的用户名/easyths/log.txt）
```

> `mcp_server_type` 配置 MCP 服务的传输协议，详见 [MCP 服务](mcp-service.md)。

### 配置优先级

配置项的优先级从高到低为：

1. 命令行参数（如 `--exe_path`）
2. 配置文件（如 `config.toml`）
3. 默认值

## 更多内容

- [API 服务](api.md)
- [MCP 服务](mcp-service.md)
- [常见问题](faq.md)
