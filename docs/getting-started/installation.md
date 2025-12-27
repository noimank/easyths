# 安装

## 安装方式

easyths 支持两种安装方式：

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| `easyths` | 客户端安装 | 跨平台，只需调用 API |
| `easyths[server]` | 服务端完整安装 | Windows 上运行服务端，操作同花顺客户端 |

## 使用 pip 安装

### 仅安装客户端（跨平台）

```bash
pip install easyths
```

### 安装完整服务端（Windows）

```bash
pip install easyths[server]
```

## 使用 uv 安装（推荐）

**推荐使用 uv 进行包管理和运行**，这是 Python 最新的现代包管理器，安装速度极快。

### 仅安装客户端（跨平台）

```bash
uv pip install easyths
```

### 安装完整服务端（Windows）

```bash
uv pip install easyths[server]
```

### 使用 uvx 一键运行服务端

```bash
# 直接运行服务端，无需手动安装
uvx easyths[server]
```

## 从源码安装

```bash
# 使用 uv（推荐）
git clone https://github.com/noimank/easyths.git
cd easyths
uv sync --all-extras

# 或使用 pip（服务端完整安装）
git clone https://github.com/noimank/easyths.git
cd easyths
pip install -e ".[server]"
```

## 安装依赖说明

系统会根据安装方式自动安装以下依赖：

**客户端安装 (`easyths`) 仅包含：**

- httpx - HTTP 客户端
- pydantic - 数据验证

**服务端完整安装 (`easyths[server]`) 包含：**

- FastAPI - Web 服务框架
- Uvicorn - ASGI 服务器
- pywinauto - Windows GUI 自动化
- pywin32 - Windows API
- Pydantic - 数据验证
- 更多依赖请查看 [pyproject.toml](https://github.com/noimank/easyths/blob/main/pyproject.toml)

## 验证安装

```bash
$ easyths --version
EasyTHS v1.3.0
```

## 下一步

[同花顺客户端配置](ths-client.md)
