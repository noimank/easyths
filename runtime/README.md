# runtime — easyths 专用 Windows 运行时

参考 [dockur/windows](https://github.com/dockur/windows):装机交给它的全自动安装,裁剪交给 [install.bat](install.bat),测完的系统盘直接当 golden 复用。目标:1 VM = 1 同花顺客户端 + 1 easyths 实例(GUI 自动化单桌面单客户端)。

## 本机测试(3 步)

```bash
cd runtime
docker compose up -d
# 浏览器 http://localhost:8006 看自动装机(约 30–60 分钟)
```

1. RDP `localhost:13389`(admin/admin,与 compose 的 USERNAME/PASSWORD 一致)进桌面,确认 `C:\OEM\done.txt` 内容为 `install.bat done`;若为 `FAILED: easyths not installed`,说明联网装 Python/easyths 失败,删除 `storage/data.img` 重建即可(脚本幂等,装过的组件自动跳过)
2. 手动装同花顺客户端 + easyths(`pip install` 或 wheel,配 `config.toml`,`host = "0.0.0.0"`),跑通验证清单;easyths 服务端从宿主经 `localhost:7648` 访问(compose 已转发)
3. `docker compose stop`,`storage/data.img` 即系统盘,复制留作 golden

系统固定 tiny10;换系统参考 [dockur/windows](https://github.com/dockur/windows) 官方仓库。资源配额按需直接改 compose.yml 的 `RAM_SIZE`/`CPU_CORES`。

## 验证清单(POC 成败点)

- [ ] **同花顺 K 线/分时图表渲染正常**(虚拟显卡软渲染,整个方案唯一硬风险)
- [ ] mss 截屏非黑屏(屏保/锁屏/睡眠已被 install.bat 关闭,失败先查电源设置)
- [ ] 验证码识别(onnxruntime)+ 查询/最小量下单全链路
- [ ] 记录基线:空闲 RAM/CPU、mss 采集延迟

> **2026-11-16 本机端到端验证通过**:`compose up` → 自动装机 → install.bat 全链路生效
> (高性能电源 / WSearch 停止 / Python 3.12.10 / easyths[server] 已装好)→ 桌面可用。
> 空闲裁剪段为该次验证后新增,待下次装机复核。中文环境挂 `storage/tiny10_zh.iso` 为 `/custom.iso`(compose volumes 已留注释行);
> tiny10 为第三方裁剪系统,激活/更新风险自担。

## install.bat 做了什么

高性能电源+禁睡眠/锁屏(GDI 采集硬约束)、关屏保、视觉最优、关搜索索引、空闲裁剪(SysMain/DiagTrack/wuauserv+DoSvc/碎片整理/WER/CEIP,tiny10 缺的组件自动跳过;补丁走运维窗口,见脚本注释)、Defender 排除 `C:\Apps`/`C:\Python312` 与 python.exe 进程;联网静默装 Python 3.12.10 与 `easyths[server]`(PyPI 发布版,本地改码需发版后重建镜像);同花顺客户端不自动装(手动)。`if not exist` 守卫,可安全重跑;完成标记按 easyths 是否装上写 `done`/`FAILED`。

## 已知问题:VC++ 运行库(onnxruntime 依赖)

onnxruntime 需要 VC++ 运行库(msvcp140/vcruntime140),缺失时报:

```
ImportError: DLL load failed while importing onnxruntime_pybind11_state: 找不到指定的模块。
```

install.bat 会在缺失时自动下载安装(aka.ms 直链,静默)。**若自动安装失败**(tiny10 上实测静默模式会被系统限制挡住),手动补救:RDP 进 VM,浏览器打开 <https://aka.ms/vs/17/release/vc_redist.x64.exe> 下载后双击安装(或命令行 `vcredist.exe /install /quiet /norestart`),装完重跑 `python -c "import onnxruntime"` 验证。

## 运维备注

- **RDP 断开会锁会话 → mss 采集失效**:日常观察用 noVNC(`:8006`),RDP 仅运维时进,退出前确认会话未锁。
- **noVNC 合成键盘有 quirks**:输入类操作走 easyths API 或 RDP,noVNC 只做观察窗。
