import mss

#直接全局单例模式，在fastapi中关闭时销毁
mss_screen_capture_instance = mss.mss()
