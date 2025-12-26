import threading
import mss

# 线程局部存储 - 每个线程拥有独立的 mss 实例
_thread_local = threading.local()

def get_mss_instance():
    """获取当前线程的 mss 实例（每个线程只创建一次，后续复用）"""
    if not hasattr(_thread_local, 'mss_instance'):
        _thread_local.mss_instance = mss.mss()
    return _thread_local.mss_instance
