# Docker 部署

使用 Docker 容器部署 EasyTHS 可以在隔离环境中运行同花顺客户端，避免与主机环境产生冲突。本指南将帮助你使用 Docker 部署完整的 Windows 交易环境。

> **注意**
>
> Docker 部署方式需要宿主机支持虚拟化。推荐使用 Windows 10 镜像，其他系统版本未经测试。

## 前置要求

在开始部署之前，请确保满足以下条件：

### 硬件要求

根据实际使用场景配置资源：

- **CPU**: 支持 VT-x/AMD-V 虚拟化技术（推荐 4 核心以上）
- **内存**: 推荐配置 8GB 或以上，可根据实际需求调整
- **磁盘**: 推荐预留 50GB 或以上，根据使用情况灵活配置

### 软件要求

- **Docker**: 20.10 或更高版本
  - Linux: Docker Engine
  - Windows: Docker Desktop（WSL 2 后端）
- **Docker Compose**: 2.0 或更高版本
- **KVM 支持**: Linux 宿主机需要启用 KVM

### 检查 KVM 支持

```bash
# 检查 KVM 模块是否加载
lsmod | grep kvm

# 检查当前用户是否在 kvm 组中
groups | grep kvm
```

如果未启用 KVM，请执行：

```bash
# 加载 KVM 模块
sudo modprobe kvm
sudo modprobe kvm_intel  # Intel CPU
# 或
sudo modprobe kvm_amd    # AMD CPU

# 将当前用户添加到 kvm 组
sudo usermod -aG kvm $USER
```

## 快速开始

### 1. 创建项目目录

```bash
mkdir -p easyths-docker
cd easyths-docker
```

### 2. 创建 docker-compose.yml

创建 `docker-compose.yml` 文件：

```yaml
services:
  windows:
    image: dockurr/windows
    container_name: windows
    environment:
      VERSION: "10"
      RAM_SIZE: "8G"
      LANGUAGE: "Chinese"
      CPU_CORES: "8"
      USERNAME: "admin"
      PASSWORD: "admin"
    devices:
      - /dev/kvm
      - /dev/net/tun
    cap_add:
      - NET_ADMIN
    ports:
      # Windows 远程桌面
      - 48006:8006
      # RDP 端口
      - 23389:3389/tcp
      - 23389:3389/udp
      # 交易服务端接口
      - 7648:7648
    volumes:
      - ./data:/storage
      - ./share_files:/shared
    restart: always
    stop_grace_period: 2m
```

### 3. 启动容器

```bash
# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f windows
```

### 4. 访问 Windows 系统

容器启动后，可以通过以下方式访问：

- **Web 界面**: 访问 `http://localhost:48006`
- **远程桌面**: 使用 RDP 客户端连接 `localhost:23389`

**默认登录凭据**:
- 用户名: `admin`
- 密码: `admin`

> **首次启动提示**
>
> 首次启动时，Windows 需要完成初始化设置，可能需要 5-10 分钟。请耐心等待直到系统完全启动。

## Windows 系统配置

### 1. 设置中文语言

登录 Windows 系统后，需要配置中文语言环境：

1. 打开 `设置` -> `时间和语言` -> `语言`
2. 点击 `添加语言`，选择 `中文（简体）`
3. 将中文设置为显示语言
4. 重启系统使设置生效

或通过 PowerShell 命令：

```powershell
# 添加中文语言包
$List = Get-WinUserLanguageList
$List.Add("zh-CN")
Set-WinUserLanguageList $List -Force
```

### 2. 安装同花顺客户端

1. 通过浏览器访问 [同花顺官网](https://download.10jqka.com.cn/)
2. 下载 **同花顺远航版** 或 **同花顺标准版**
3. 运行安装程序，按照提示完成安装
4. 启动同花顺并登录账号

### 3. 安装 EasyTHS

打开 PowerShell 或命令提示符：

```powershell
# 使用 pip 安装服务端
pip install easyths[server]

# 验证安装
easyths --version
```

### 4. 配置同花顺客户端

按照 [同花顺客户端配置](ths-client.md) 文档进行配置：

1. 打开交易窗口（F12 或 工具 -> 自动委托程序）
2. 启用新版页面
3. 配置交易参数

### 5. 启动 EasyTHS 服务

```powershell
# 启动 EasyTHS
easyths

# 服务将在 http://localhost:7648 启动
```

### 6. 验证部署

从宿主机访问容器内的 EasyTHS 服务：

```bash
curl http://localhost:7648/api/v1/system/status
```

成功连接后会返回：

```json
{
  "status": "ok",
  "connected": true
}
```

## 配置说明

### 环境变量

docker-compose.yml 中的环境变量说明：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VERSION` | Windows 版本（推荐使用 "10"，其他版本未经测试） | "10" |
| `RAM_SIZE` | 分配内存大小（根据实际需求调整） | "8G" |
| `LANGUAGE` | 系统语言 | "Chinese" |
| `CPU_CORES` | CPU 核心数（根据实际需求调整） | "8" |
| `USERNAME` | 管理员用户名 | "admin" |
| `PASSWORD` | 管理员密码 | "admin" |

### 端口映射

| 容器端口 | 宿主机端口 | 说明 |
|----------|------------|------|
| 8006 | 48006 | Web 界面访问 |
| 3389 | 23389 | RDP 远程桌面 |
| 7648 | 7648 | EasyTHS API 服务 |

### 数据持久化

- `./data`: Windows 系统数据和用户文件
- `./share_files`: 宿主机与容器共享文件目录

可以通过共享文件夹在宿主机和容器之间传输文件：

```bash
# 复制文件到共享目录
cp your_file.txt easyths-docker/share_files/

# 在 Windows 容器中访问
# 文件位于 \\\storage\shared\your_file.txt
```

## 高级配置

### 自定义 Windows ISO

如果需要使用自定义的 Windows ISO 镜像：

```yaml
volumes:
  - ./data:/storage
  - ./share_files:/shared
  - ./iso/win1021h2.iso:/boot.iso  # 添加 ISO 映射
```

### 调整资源限制

根据实际需求调整资源分配：

```yaml
environment:
  RAM_SIZE: "16G"      # 增加内存
  CPU_CORES: "12"      # 增加 CPU 核心数
```

### 网络配置

如果需要自定义网络设置：

```yaml
networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

## 常见问题

### 容器无法启动？

**检查 KVM 支持**:

```bash
# 检查 KVM 设备
ls -la /dev/kvm

# 检查当前用户权限
groups
```

确保当前用户在 `kvm` 组中。

### 性能较慢？

1. 增加分配的 CPU 核心数和内存
2. 确保启用了 KVM 硬件加速
3. 检查宿主机资源使用情况

### 无法访问 EasyTHS 服务？

1. 确认容器内 EasyTHS 服务已启动
2. 检查端口映射是否正确
3. 验证 Windows 防火墙设置

```powershell
# 在 Windows 容器中检查防火墙
netsh advfirewall firewall show rule name=all
```

### 语言设置不生效？

1. 确保正确安装了中文语言包
2. 将中文设置为默认显示语言
3. 重启容器使设置生效

```bash
docker-compose restart windows
```

## 容器管理

### 查看容器状态

```bash
docker-compose ps
```

### 查看日志

```bash
# 查看所有日志
docker-compose logs windows

# 实时查看日志
docker-compose logs -f windows
```

### 停止容器

```bash
docker-compose stop
```

### 启动容器

```bash
docker-compose start
```

### 重启容器

```bash
docker-compose restart
```

### 删除容器

```bash
# 停止并删除容器
docker-compose down

# 删除容器和数据卷（谨慎使用）
docker-compose down -v
```

## 参考资源

- [dockur/windows 官方文档](https://github.com/dockur/windows)
- [Docker 官方文档](https://docs.docker.com/)
- [EasyTHS 项目仓库](https://github.com/noimank/easyths)

## 下一步

[基础用法](basic-usage.md)
