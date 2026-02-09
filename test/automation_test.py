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
from easyths.operations.reverse_repo_buy import ReverseRepoBuyOperation
from easyths.operations.reverse_repo_query import ReverseRepoQueryOperation
from easyths.operations.condition_buy import ConditionBuyOperation
from easyths.operations.stop_loss_profit import StopLossProfitOperation
from easyths.operations.condition_order_query import ConditionOrderQueryOperation
from easyths.operations.condition_order_cancel import ConditionOrderCancelOperation
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

def test_reverse_repo_buy_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = ReverseRepoBuyOperation(automator)


        # 执行操作（同步）
        params = {
            # 交易市场   ["上海", "深圳"],
            "market": "上海",
            # 回购期限   ["1天期", "2天期", "3天期", "4天期", "7天期"]
            "time_range": "1天期",
            "amount": 100000
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()
def test_reverse_repo_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = ReverseRepoQueryOperation(automator)


        # 执行操作（同步）
        params = {
            # 交易市场   ["上海", "深圳"],
            "market": "上海",
            # 回购期限   ["1天期", "2天期", "3天期", "4天期", "7天期"]
            "time_range": "1天期",
            "amount": 100000
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()

def test_condition_buy_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = ConditionBuyOperation(automator)


        # 执行操作（同步）
        params = {
            "stock_code": "000001",
            "target_price": 12.1,
            "quantity": 100
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()


def test_stop_loss_profit_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = StopLossProfitOperation(automator)


        # 执行操作（同步）
        params = {
            "stock_code": "000001",
            "stop_loss_percent": 3.1,
            "stop_profit_percent": 5.6,
            "quantity": 100,
            "expire_days": 1
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()


def test_condition_order_query_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = ConditionOrderQueryOperation(automator)

        # 执行操作（同步）
        params = {
            "return_type": "json"
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()


def test_condition_order_cancel_op():
    # 创建自动化器
    automator = TonghuashunAutomator()

    # 连接
    automator.connect()

    try:
        # 创建操作
        op = ConditionOrderCancelOperation(automator)

        # 执行操作（同步）
        params = {
            # "stock_code": "000001",
            # "order_type": "买入"
        }

        result = op.run(params)
        print(f"操作结果: {result.success}, data: {result.data}")

    finally:
        # 断开连接
        automator.disconnect()



if __name__ == "__main__":
    # test_automator_basic()
    test_buy_op()
    test_sell_op()
    test_funds_query_op()
    test_order_cancel_op()
    test_holding_query_op()
    test_order_query_op()
    test_historical_commission_query_op()
    # test_reverse_repo_buy_op()
    # test_reverse_repo_query_op()
    # test_condition_buy_op()
    # test_stop_loss_profit_op()
    # test_condition_order_query_op()
    # test_condition_order_cancel_op()