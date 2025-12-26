"""自动化测试 - 同步操作模式

Author: noimank
Email: noimank@163.com
"""

from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.operations.buy import BuyOperation
from easyths.operations.sell import SellOperation
from easyths.operations.funds_query import FundsQueryOperation
from easyths.operations.order_cancel import OrderCancelOperation
from easyths.operations.holding_query import HoldingQueryOperation
from easyths.operations.order_query import OrderQueryOperation
from easyths.operations.historical_commission_query import HistoricalCommissionQueryOperation
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
            "price": 110.55,
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

def test_sell_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = SellOperation(automator)

        # 执行操作（同步）
        params = {
            "stock_code": "000001",
            "price": 11.55,
            "quantity": 1000
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()

def test_funds_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = FundsQueryOperation(automator)

        # 执行操作（同步）
        params = {

        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()

def test_order_cancel_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = OrderCancelOperation(automator)

        # 执行操作（同步）
        params = {
            "stock_code": "000001",
            "cancel_type": "all"

        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()

def test_holding_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = HoldingQueryOperation(automator)

        # 执行操作（同步）
        params = {
            "return_type": "json",
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()


def test_order_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = OrderQueryOperation(automator)

        # 执行操作（同步）
        params = {
            "return_type": "json",
            "stock_code": "000001"
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()

def test_historical_commission_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = HistoricalCommissionQueryOperation(automator)

        # 执行操作（同步）
        params = {
            "return_type": "json",
            # "stock_code": "000001"
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()



if __name__ == "__main__":
    # test_automator_basic()
    test_buy_op()
    # test_sell_op()
    # test_funds_query_op()
    # test_order_cancel_op()
    # test_holding_query_op()
    # test_order_query_op()
    # test_historical_commission_query_op()