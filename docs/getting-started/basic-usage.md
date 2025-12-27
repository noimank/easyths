# 基础用法

## 启动服务

### 方式一：使用 uvx 一键运行（推荐）

```bash
uvx easyths[server]
```

> **提示**：`uvx` 是 uv 工具提供的命令，可以自动下载并运行 Python 包，无需手动安装。

### 方式二：安装后运行

```bash
# 先安装服务端
pip install easyths[server]

# 运行
easyths
```

### 方式三：使用模块运行

```bash
# 开发环境
python -m easyths.main
```

服务默认运行在 `http://127.0.0.1:7648`

## API 文档

启动服务后，访问以下地址查看 API 文档：

- Swagger UI: `http://127.0.0.1:7648/docs`
- ReDoc: `http://127.0.0.1:7648/redoc`

## 命令行选项

### 查看帮助

```bash
easyths --help
```

### 查看版本

```bash
easyths --version
# 或
easyths -v
```

### 完整选项列表

| 选项 | 说明 |
|------|------|
| `--exe_path <path>` | 指定同花顺交易程序路径（优先级高于配置文件） |
| `--config <file>` | 指定 TOML 配置文件路径 |
| `--get_config` | 将示例配置文件复制到当前目录 |
| `--version, -v` | 显示版本信息 |
| `--help` | 显示帮助信息 |

### 使用示例

```bash
# 使用默认配置启动
uvx easyths[server]

# 使用自定义配置文件启动
uvx easyths[server] --config my_config.toml

# 指定交易程序路径启动（优先级最高）
uvx easyths[server] --exe_path "C:/同花顺/xiadan.exe"

# 查看版本
uvx easyths[server] --version

# 生成示例配置文件
uvx easyths[server] --get_config

# 组合使用
uvx easyths[server] --config my_config.toml --exe_path "C:/同花顺/xiadan.exe"
```

## 配置文件

配置文件采用 TOML 格式，包含以下部分：

### [app] 应用程序配置
```toml
[app]
name = "同花顺交易自动化程序"
version = "1.0.0"
```

### [trading] 交易程序配置
```toml
[trading]
app_path = "C:/同花顺远航版/transaction/xiadan.exe"
```

### [queue] 队列配置
```toml
[queue]
max_size = 1000           # 队列最大容量
priority_levels = 5       # 优先级级别数
batch_size = 10          # 批量处理大小
```

### [api] API 服务配置
```toml
[api]
host = "0.0.0.0"           # 服务器地址
port = 7648                # 服务器端口
rate_limit = 10            # 速率限制（请求/分钟）
cors_origins = "*"         # CORS 允许的源
key = ""                   # API 密钥（留空表示不启用）
ip_whitelist = ""          # IP 白名单（留空表示允许所有）
```

### [logging] 日志配置
```toml
[logging]
level = "INFO"             # 日志级别
file = "logs/trading.log"  # 日志文件路径
```

## 完整配置参考

以下是完整的配置文件示例（保存为 `config.toml`）：

```toml
# ============================================
# EasyTHS 配置文件
# ============================================

[app]
name = "同花顺交易自动化程序"
version = "1.0.0"

# ============================================
# 交易程序配置
# ============================================
[trading]
app_path = "C:/同花顺远航版/transaction/xiadan.exe"

# ============================================
# 队列配置
# ============================================
[queue]
max_size = 1000           # 队列最大容量
priority_levels = 5       # 优先级级别数
batch_size = 10          # 批量处理大小

# ============================================
# API 服务配置
# ============================================
[api]
host = "0.0.0.0"           # 服务器地址
port = 7648                # 服务器端口
rate_limit = 10            # 速率限制（请求/分钟）
cors_origins = "*"         # CORS 允许的源
key = ""                   # API 密钥（留空表示不启用）
ip_whitelist = ""          # IP 白名单（留空表示允许所有）

# ============================================
# 日志配置
# ============================================
[logging]
level = "INFO"             # 日志级别：DEBUG, INFO, WARNING, ERROR
file = "logs/trading.log"  # 日志文件路径
```

### 配置优先级

配置项的优先级从高到低为：

1. 命令行参数（如 `--exe_path`）
2. 配置文件（如 `config.toml`）
3. 环境变量
4. 默认值

### 生成示例配置

使用以下命令生成示例配置文件到当前目录：

```bash
uvx easyths[server] --get_config
```

## 更多内容

- [API 服务](api.md)
- [常见问题](faq.md)
