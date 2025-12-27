"""客户端测试

Author: noimank
Email: noimank@163.com
"""
from easyths import TradeClient

client = TradeClient(host='localhost', port=7648, api_key="mysuperKey87kiE@iijiu+ojiyu")


def test_health_check():
    """测试健康检查"""
    res = client.health_check()
    print(f"健康检查: {res}")


def test_get_system_status():
    """测试获取系统状态"""
    res = client.get_system_status()
    print(f"系统状态: {res}")


def test_get_system_info():
    """测试获取系统信息"""
    res = client.get_system_info()
    print(f"系统信息: {res}")


def test_get_queue_stats():
    """测试获取队列统计"""
    res = client.get_queue_stats()
    print(f"队列统计: {res}")


def test_list_operations():
    """测试列出所有操作"""
    res = client.list_operations()
    print(f"可用操作: {res}")


def test_buy():
    """测试买入"""
    res = client.buy("000001", 100, 100)
    print(f"买入结果: {res}")


def test_sell():
    """测试卖出"""
    res = client.sell("000001", 100, 100)
    print(f"卖出结果: {res}")


def test_cancel_order_all():
    """测试撤销所有委托"""
    res = client.cancel_order()
    print(f"撤销所有委托: {res}")


def test_cancel_order_buy():
    """测试撤销买单"""
    res = client.cancel_order(cancel_type="buy")
    print(f"撤销买单: {res}")


def test_cancel_order_sell():
    """测试撤销卖单"""
    res = client.cancel_order(cancel_type="sell")
    print(f"撤销卖单: {res}")


def test_cancel_order_stock():
    """测试撤销指定股票委托"""
    res = client.cancel_order(stock_code="000001")
    print(f"撤销指定股票委托: {res}")


def test_query_holdings():
    """测试查询持仓"""
    res = client.query_holdings()
    print(f"持仓查询: {res}")


def test_query_holdings_markdown():
    """测试查询持仓（markdown 格式）"""
    res = client.query_holdings(return_type="markdown")
    print(f"持仓查询: {res}")


def test_query_funds():
    """测试查询资金"""
    res = client.query_funds()
    print(f"资金查询: {res}")


def test_query_orders():
    """测试查询所有委托"""
    res = client.query_orders()
    print(f"委托查询: {res}")


def test_query_orders_stock():
    """测试查询指定股票委托"""
    res = client.query_orders(stock_code="000001")
    print(f"指定股票委托查询: {res}")

def test_reverse_repo():
    interest_res = client.query_reverse_repo(20)
    print(f"逆回购查询: {interest_res}")
    interest_res = client.reverse_repo_buy("深圳", "7天期", 1000)
    print(f"逆回购买入: {interest_res}")

def test_condition_bug():
    interest_res = client.condition_buy("000001", 12, 1000)
    print(f"条件买入: {interest_res}")

def test_stop_loss_profit():
    interest_res = client.stop_loss_profit("000001", 3.1, 2.5)
    print(f"止盈止损: {interest_res}")



def test_context_manager():
    """测试上下文管理器"""
    with TradeClient(host='localhost', port=8888, api_key="mysuperKey87kiE@iijiu+ojiyu") as c:
        res = c.health_check()
        print(f"上下文管理器测试: {res}")


if __name__ == '__main__':
    # 系统管理测试
    print("=== 系统管理测试 ===")
    test_health_check()
    test_get_system_status()
    test_get_system_info()
    test_get_queue_stats()
    test_list_operations()

    # 交易操作测试
    print("\n=== 交易操作测试 ===")
    # test_buy()
    # test_sell()
    # test_reverse_repo()
    test_condition_bug()
    test_stop_loss_profit()

    # 撤单操作测试
    print("\n=== 撤单操作测试 ===")
    # test_cancel_order_all()
    # test_cancel_order_buy()
    # test_cancel_order_sell()
    # test_cancel_order_stock()

    # 查询操作测试
    # print("\n=== 查询操作测试 ===")
    # test_query_holdings()
    # test_query_holdings_markdown()
    # test_query_funds()
    # test_query_orders()
    # test_query_orders_stock()
    #
    # # 上下文管理器测试
    # print("\n=== 上下文管理器测试 ===")
    # test_context_manager()
