# 安装

## 安装方式

easyths 支持两种安装方式：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| `easyths` | 全量安装 | 作为服务端运行，需要操作同花顺客户端 |
| `easyths[client]` | 仅客户端 | 只需调用 API，不运行服务端 |

## 使用 uv 安装（推荐）

**推荐使用 uv 进行包管理和运行**，这是 Python 最新的现代包管理器，安装速度极快。

### 安装全量版本（服务端）

```bash
uv pip install easyths
```

### 仅安装客户端

```bash
uv pip install easyths[client]
```

### 使用 uvx 一键运行服务端

```bash
# 直接运行，无需手动安装
uvx easyths
```

## 使用 pip 安装

### 安装全量版本（服务端）

```bash
pip install easyths
```

### 仅安装客户端

```bash
pip install easyths[client]
```

## 从源码安装

```bash
# 使用 uv（推荐）
git clone https://github.com/noimank/easyths.git
cd easyths
uv sync

# 或使用 pip
git clone https://github.com/noimank/easyths.git
cd easyths
pip install -e .
```

## 安装依赖说明

系统会根据安装方式自动安装以下依赖：

**全量安装 (`easyths`) 包含：**

- FastAPI - Web 服务框架

- pywinauto - Windows GUI 自动化

- Uvicorn - ASGI 服务器

- Pydantic - 数据验证

- 更多依赖请查看 [pyproject.toml](https://github.com/noimank/easyths/blob/main/pyproject.toml)

**客户端安装 (`easyths[client]`) 仅包含：**

- httpx - HTTP 客户端

- pydantic - 数据验证

## 验证安装

```bash
$ easyths --version
EasyTHS v1.0.1
```

## 下一步

[同花顺客户端配置](ths-client.md)
