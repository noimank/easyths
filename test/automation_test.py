
from easyths.core.tonghuashun_automator import TonghuashunAutomator
from easyths.operations.buy import BuyOperation
from easyths.operations.sell import SellOperation
from easyths.operations.funds_query import FundsQueryOperation
from easyths.operations.holding_query import HoldingQueryOperation
from easyths.operations.order_cancel import OrderCancelOperation
from easyths.operations.order_query import OrderQueryOperation
from easyths.operations.historical_commission_query import HistoricalCommissionQueryOperation
import asyncio
from dotenv import load_dotenv

load_dotenv("../.env")


# print(config.get('trading', {}))
automator = TonghuashunAutomator()
config = None
loop = asyncio.get_event_loop()
loop.run_until_complete(automator.connect())

def test_init():
    app = automator.app
    assert app is not None



def test_buy_op():
    app = automator.app
    params = {
        "stock_code": "000001",
        "price": 11.55,
        "quantity": 100

    }
    buy_op = BuyOperation(automator, config)
    loop.run_until_complete( buy_op.run(params))
    loop.run_until_complete(automator.disconnect())


def test_sell_op():
    app = automator.app
    params = {
        "stock_code": "000001",
        "price": 11.55,
        "quantity": 100

    }
    sell_op = SellOperation(automator, config)
    loop.run_until_complete( sell_op.run(params))
    loop.run_until_complete(automator.disconnect())

def test_fund_query():
    app = automator.app
    params = {
        "stock_code": "000001",
        "price": 11.55,
        "quantity": 100
    }
    query_op = FundsQueryOperation(automator, config)
    loop.run_until_complete( query_op.run(params))
    loop.run_until_complete(automator.disconnect())

def test_hoding_query():
    app = automator.app
    # 返回格式 str、dict、markdown、df、json
    params = {
        "return_type": "json"
    }
    query_op = HoldingQueryOperation(automator, config)
    loop.run_until_complete( query_op.run(params))
    loop.run_until_complete(automator.disconnect())

def test_order_cancel():
    app = automator.app
    params = {
        # "stock_code": "159813",
        "cancel_type": "all"
    }
    op = OrderCancelOperation(automator, config)
    loop.run_until_complete(op.run(params))
    loop.run_until_complete(automator.disconnect())

def test_order_query():
    app = automator.app
    # 返回格式 str、dict、markdown、df、json
    params = {
        "return_type": "json",
        # "stock_code": "159814"
    }
    op = OrderQueryOperation(automator, config)
    loop.run_until_complete(op.run(params))
    loop.run_until_complete(automator.disconnect())

def test_historical_commission_query():
    app = automator.app
    # 返回格式 str、dict、markdown、df、json
    params = {
        # "return_type": "json",
        # "stock_code": "000001",
        "time_range": "近一月"
    }
    op = HistoricalCommissionQueryOperation(automator, config)
    loop.run_until_complete(op.run(params))
    loop.run_until_complete(automator.disconnect())







