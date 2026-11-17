# 轻量运行时部署 {#轻量运行时部署}

EasyTHS 在仓库 [runtime/](https://github.com/noimank/easyths/blob/main/runtime/) 目录中提供一套专用 Windows 运行时：基于 [dockur/windows](https://github.com/dockur/windows) 全自动装机，装机最后一步自动执行 [install.bat](https://github.com/noimank/easyths/blob/main/runtime/install.bat) 完成系统裁剪与软件安装。目标是 **1 台虚拟机 = 1 个同花顺客户端 + 1 个 EasyTHS 实例**（GUI 自动化单桌面单客户端）。

与通用 [Docker 部署](docker-deployment.md)相比：

- 系统固定为 tiny10 精简系统，资源占用更低（4 核 / 4GB 内存 / 32GB 磁盘即可）
- 装机、系统裁剪、Python 与 EasyTHS 服务端安装全自动，无需逐项手动配置
- 测试通过的系统盘可直接复制为 golden 镜像复用，新实例免重新装机

> **注意**
>
> 该方案目前处于 POC 阶段，POC 成败点（虚拟显卡软渲染下的图表表现）见下方[验证清单](#验证清单)。tiny10 为第三方裁剪系统，激活/更新风险自担。如需使用官方 Windows 10 镜像，请参见 [Docker 部署](docker-deployment.md)。

## 前置要求 {#前置要求}

与 Docker 部署一致：宿主机需支持虚拟化并启用 KVM，Docker / Docker Compose 版本要求与 KVM 检查方法见 [Docker 部署 · 检查 KVM 支持](docker-deployment.md#检查-kvm-支持)。

## 快速开始 {#快速开始}

### 1. 启动自动装机 {#启动自动装机}

```bash
cd runtime
docker compose up -d
```

浏览器打开 `http://localhost:8006`（noVNC）观察全自动装机过程，约 30–60 分钟。装机最后一步会自动执行 `install.bat`：高性能电源（禁睡眠/锁屏/屏保，GDI 采集硬约束）、关闭搜索索引与后台空闲活动、Defender 排除应用目录与 Python 进程，并联网安装 Python 3.12.10 与 `easyths[server]`（PyPI 发布版，本地改码需发版后重建镜像）。全部步骤带 `if not exist` 守卫，可安全重跑。

### 2. 手动补齐业务软件并验证 {#手动补齐业务软件并验证}

同花顺客户端无公开静默安装包，需手动安装；EasyTHS 的 `config.toml` 也需自行配置：

1. RDP 连接 `localhost:13389`（用户名/密码 `admin`/`admin`），确认 `C:\OEM\done.txt` 存在（装机完成标志）
2. 手动安装同花顺客户端，并按 [同花顺客户端配置](ths-client.md) 完成配置
3. 配置 `config.toml`（`host = "0.0.0.0"` 以便宿主机访问），启动 EasyTHS 并跑通下方[验证清单](#验证清单)
4. EasyTHS 服务端从宿主机经 `localhost:7648` 访问（compose 已转发）

### 3. 保存 golden 镜像 {#保存-golden-镜像}

验证通过后停止容器，`storage/data.img` 即系统盘，复制留作 golden：

```bash
docker compose stop
```

之后部署新实例时直接复用 golden 系统盘，无需重新装机。

## 端口与目录 {#端口与目录}

| 端口 | 说明 |
|------|------|
| 8006 | noVNC 网页（观察装机与日常观察窗口） |
| 13389 | RDP 远程桌面（运维入口） |
| 7648 | EasyTHS API 服务 |

| 路径 | 说明 |
|------|------|
| `runtime/storage/` | 系统盘镜像（`data.img`），golden 镜像来源 |
| `runtime/share_files/` | 宿主机与虚拟机共享文件目录 |
| `runtime/compose.yml` | 资源配额（`RAM_SIZE`/`CPU_CORES`）与端口按需直接修改 |

## 验证清单 {#验证清单}

- [ ] **同花顺 K 线/分时图表渲染正常**（虚拟显卡软渲染，整个方案唯一硬风险）
- [ ] mss 截屏非黑屏（屏保/锁屏/睡眠已被 install.bat 关闭，失败先查电源设置）
- [ ] 验证码识别（onnxruntime）+ 查询/最小量下单全链路
- [ ] 记录基线：空闲 RAM/CPU、mss 采集延迟

## 常见问题 {#常见问题}

### onnxruntime DLL 加载失败 {#onnxruntime-dll-加载失败}

onnxruntime 依赖 VC++ 运行库（msvcp140/vcruntime140），缺失时报 `ImportError: DLL load failed`。install.bat 会在缺失时自动下载安装；若自动安装失败（tiny10 上实测静默模式会被系统限制挡住），手动补救：RDP 进虚拟机，下载 [vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe) 双击安装，装完用 `python -c "import onnxruntime"` 验证。通用 Windows 环境下的排查见 [常见问题](faq.md#onnxruntime-dll-加载失败)。

### RDP 断开后 mss 采集失效 {#rdp-断开后-mss-采集失效}

RDP 断开会锁会话，导致 mss 采集失效。日常观察用 noVNC（`:8006`），RDP 仅运维时进入，退出前确认会话未锁。另外 noVNC 合成键盘存在兼容性问题（quirks），输入类操作请走 EasyTHS API 或 RDP，noVNC 只做观察窗。

### 中文环境 {#中文环境}

默认装机为英文系统；需要中文环境时，将本地中文 ISO 挂载为 `/custom.iso`（compose.yml 的 volumes 已留注释行），挂载后 `VERSION` 环境变量不再生效。

## 参考资源 {#参考资源}

- [dockur/windows 官方文档](https://github.com/dockur/windows)（换系统、高级配置）
- [runtime/ 目录](https://github.com/noimank/easyths/blob/main/runtime/)（compose.yml、install.bat 与 POC 备注）

## 下一步 {#下一步}

[基础用法](basic-usage.md)
