"""客户端测试

需要运行中的 EasyTHS 服务端，使用 pytest -m integration 运行。

Author: noimank
Email: noimank@163.com
"""

import pytest

from easyths import TradeClient

pytestmark = pytest.mark.integration

client = TradeClient(host="localhost", port=7648, api_key="")


def test_health_check():
    """测试健康检查"""
    res = client.health_check()
    assert res["success"] is True
    print(f"健康检查: {res}")


def test_get_system_status():
    """测试获取系统状态（含版本与插件清单）"""
    res = client.get_system_status()
    assert res["success"] is True
    assert res["data"]["version"] != "1.0.0"
    print(f"系统状态: {res}")


def test_reconnect():
    """测试重连同花顺"""
    res = client.reconnect()
    assert "success" in res
    print(f"重连结果: {res}")


def test_get_queue_stats():
    """测试获取队列统计"""
    res = client.get_queue_stats()
    assert res["success"] is True
    print(f"队列统计: {res}")


def test_list_operations():
    """测试列出所有操作"""
    res = client.list_operations()
    assert res["success"] is True
    assert res["data"]["count"] > 0
    print(f"可用操作: {res}")


def test_buy():
    """测试买入"""
    res = client.buy("000001", 100, 100)
    assert "success" in res
    print(f"买入结果: {res}")


def test_market_buy():
    """测试市价买入"""
    res = client.market_buy("000001", 100, 1)
    assert "success" in res
    print(f"市价买入结果: {res}")


def test_market_sell():
    """测试市价卖出"""
    res = client.market_sell("000001", 100, 1)
    assert "success" in res
    print(f"市价卖出结果: {res}")


def test_sell():
    """测试卖出"""
    res = client.sell("000001", 100, 100)
    assert "success" in res
    print(f"卖出结果: {res}")


def test_cancel_order_all():
    """测试撤销所有委托"""
    res = client.cancel_order()
    assert "success" in res
    print(f"撤销所有委托: {res}")


def test_cancel_order_buy():
    """测试撤销买单"""
    res = client.cancel_order(cancel_type="buy")
    assert "success" in res
    print(f"撤销买单: {res}")


def test_cancel_order_sell():
    """测试撤销卖单"""
    res = client.cancel_order(cancel_type="sell")
    assert "success" in res
    print(f"撤销卖单: {res}")


def test_cancel_order_stock():
    """测试撤销指定股票委托"""
    res = client.cancel_order(stock_code="000001")
    assert "success" in res
    print(f"撤销指定股票委托: {res}")


def test_query_holdings():
    """测试查询持仓（统一 JSON 记录列表交付）"""
    res = client.query_holdings()
    assert "success" in res
    # assert isinstance(res["data"], list)
    print(f"持仓查询: {res}")


def test_query_funds():
    """测试查询资金"""
    res = client.query_funds()
    assert "success" in res
    print(f"资金查询: {res}")


def test_query_orders():
    """测试查询所有委托"""
    res = client.query_orders()
    assert "success" in res
    assert isinstance(res["data"], list)
    print(f"委托查询: {res}")


def test_query_orders_stock():
    """测试查询指定股票委托"""
    res = client.query_orders(stock_code="000001")
    assert "success" in res
    print(f"指定股票委托查询: {res}")


def test_query_historical_commission():
    """测试查询历史委托"""
    res = client.query_historical_commission()
    assert "success" in res
    assert isinstance(res["data"], list)
    print(f"历史委托查询: {res}")


def test_reverse_repo():
    interest_res = client.query_reverse_repo()
    assert "success" in interest_res
    print(f"逆回购查询: {interest_res}")
    interest_res = client.reverse_repo_buy("深圳", "7天期", 1000)
    assert "success" in interest_res
    print(f"逆回购买入: {interest_res}")


def test_condition_bug():
    interest_res = client.condition_buy("000001", 12, 1000)
    assert "success" in interest_res
    print(f"条件买入: {interest_res}")


def test_condition_sell():
    interest_res = client.condition_sell("000001", 12.4, 1000)
    assert "success" in interest_res
    print(f"条件卖出: {interest_res}")


def test_stop_loss_profit():
    interest_res = client.stop_loss_profit("000001", 3.1, 2.5)
    assert "success" in interest_res
    print(f"止盈止损: {interest_res}")


def test_condition_order_query():
    interest_res = client.query_condition_orders()
    assert "success" in interest_res
    assert isinstance(interest_res["data"], list)
    print(f"条件单查询: {interest_res}, 数据：{interest_res['data']}")


def test_condition_order_canel():
    interest_res = client.cancel_condition_orders()
    assert "success" in interest_res
    print(f"删除条件单: {interest_res}")


def test_context_manager():
    """测试上下文管理器"""
    with TradeClient(
        host="localhost", port=8888, api_key="mysuperKey87kiE@iijiu+ojiyu"
    ) as c:
        res = c.health_check()
        assert res["success"] is True
        print(f"上下文管理器测试: {res}")
