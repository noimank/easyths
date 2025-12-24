"""自动化测试 - 同步操作模式

Author: noimank
Email: noimank@163.com
"""

from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.operations.buy import BuyOperation
from dotenv import load_dotenv

load_dotenv("../.env")


def test_buy_op():
    """测试买入操作 - 同步模式"""
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建买入操作
        buy_op = BuyOperation(automator)

        # 执行买入（同步）
        params = {
            "stock_code": "000001",
            "price": 11.55,
            "quantity": 100
        }

        result = buy_op.run(params)
        print(f"买入结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()


def test_automator_basic():
    """测试自动化器基本功能"""
    automator = TonghuashunAutomator()

    try:
        # 连接
        connected = automator.connect()
        print(f"连接结果: {connected}")

        assert connected, "连接失败"

        # 检查连接状态
        is_connected = automator.is_connected()
        print(f"已连接: {is_connected}")
        assert is_connected, "未连接"

        # 获取主窗口
        main_window = automator.main_window
        print(f"主窗口: {main_window is not None}")
        assert main_window is not None, "主窗口为空"

        # 断开连接
        automator.disconnect()
        print("测试通过!")

    finally:
        pass


if __name__ == "__main__":
    # test_automator_basic()
    test_buy_op()  # 取消注释以测试实际买入操作
