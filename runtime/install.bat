@echo off
chcp 65001 >nul
REM ============================================================
REM easyths golden image 裁剪脚本(dockur 装机最后一步自动执行)
REM 原则:只做与性能、GUI 自动化可靠性直接相关的裁剪;
REM       软件全部联网安装(python.org / 阿里源 PyPI),不要求本地备料
REM ============================================================

REM ---- 时区 ----
tzutil /s "China Standard Time" >nul

REM ---- 电源:高性能计划,禁睡眠/关闭显示器/休眠 ----
REM 锁屏或黑屏会令 GDI(mss)采集失效,这是 VM 里跑 GUI 自动化的硬约束
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c >nul 2>&1
powercfg /change standby-timeout-ac 0 >nul
powercfg /change monitor-timeout-ac 0 >nul
powercfg /change hibernate-timeout-ac 0 >nul
powercfg /hibernate off >nul 2>&1

REM ---- 屏保关闭(锁屏黑屏同因)----
reg add "HKCU\Control Panel\Desktop" /v ScreenSaveActive /t REG_SZ /d 0 /f >nul

REM ---- 视觉效果:调整为最佳性能(下次登录生效)----
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects" /v VisualFXSetting /t REG_DWORD /d 2 /f >nul

REM ---- Windows Update:登录时不自动重启(升级窗口由运维控制)----
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f >nul

REM ---- 搜索索引:关闭(GUI 专用机无用,省空闲 IO/CPU)----
sc stop WSearch >nul 2>&1
sc config WSearch start= disabled >nul 2>&1

REM ---- 空闲裁剪:GUI 专用机用不到的后台活动(空闲 CPU/IO 抖动直接干扰截屏与操作时序)----
REM tiny10 已裁掉大部分组件;此处对仍存在的逐项关闭,命令全部容错。
REM wuauserv/DoSvc 禁用 = Update 后台扫描/下载一并停,补丁走运维窗口:
REM   sc config wuauserv start= demand && sc start wuauserv
for %%s in (SysMain DiagTrack DoSvc wuauserv) do (
    sc stop %%s >nul 2>&1
    sc config %%s start= disabled >nul 2>&1
)
schtasks /change /tn "\Microsoft\Windows\Defrag\ScheduledDefrag" /disable >nul 2>&1
schtasks /change /tn "\Microsoft\Windows\Windows Error Reporting\QueueReporting" /disable >nul 2>&1
schtasks /change /tn "\Microsoft\Windows\Customer Experience Improvement Program\Consolidator" /disable >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting" /v Disabled /t REG_DWORD /d 1 /f >nul

REM ---- Defender:排除应用目录与 Python 进程(实时扫描是 GUI 场景主要卡顿源)----
REM 排除路径须与部署目录一致;整体关闭留待 POC 结论决定
powershell -NoProfile -Command "Add-MpPreference -ExclusionPath 'C:\Apps'; Add-MpPreference -ExclusionPath 'C:\Python312'; Add-MpPreference -ExclusionProcess 'python.exe'" >nul 2>&1

REM ---- VC++ 运行库(onnxruntime 依赖;缺失时报 ImportError: DLL load failed)----
REM 尽力而为:若系统缺失则联网下载并静默安装;失败(如第三方精简系统限制)不影响装机流程,
REM 手动补救见 README「已知问题」
if not exist "C:\Windows\System32\msvcp140.dll" (
    curl -sSLf -o C:\OEM\vcredist.exe https://aka.ms/vs/17/release/vc_redist.x64.exe
    "C:\OEM\vcredist.exe" /install /quiet /norestart
)

REM ---- Python 3.12 + easyths(全程联网;装过则跳过,可安全重跑)----
if not exist "C:\Python312\python.exe" (
    curl -sSLf -o C:\OEM\python-installer.exe https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
    "C:\OEM\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 TargetDir=C:\Python312
)
if not exist "C:\Python312\Lib\site-packages\easyths" (
    "C:\Python312\python.exe" -m pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ "easyths[server]"
)

REM ---- 同花顺客户端:不自动装(无公开静默包,手动安装,见 README 清单)----

REM ---- 完成标记(C:\OEM\done.txt,进 VM 里确认;FAILED = 联网装机失败,勿复用该盘)----
if exist "C:\Python312\Lib\site-packages\easyths" (
    echo %date% %time% install.bat done > C:\OEM\done.txt
) else (
    echo %date% %time% install.bat FAILED: easyths not installed > C:\OEM\done.txt
)
