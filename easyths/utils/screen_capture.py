"""屏幕区域截图。

mss 的 Windows 实现将 GDI 设备上下文存于 threading.local，实例与
创建线程绑定，跨线程使用会报 ``'_thread._local' object has no
attribute 'srcdc'``。因此不缓存实例：按次创建、用后即释放，同时
规避线程绑定与 GDI 句柄泄漏。
"""

from typing import Any

import mss


def grab_screen(monitor: dict[str, int]) -> Any:
    """截取指定屏幕区域（monitor 含 top/left/width/height）"""
    with mss.mss() as sct:
        return sct.grab(monitor)
