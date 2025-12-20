
from src.automation.operation_manager import OperationManager
from src.automation.tonghuashun_automator import TonghuashunAutomator
from src.utils.env_config import get_settings
from src.automation.operations.buy_operation import BuyOperation
from src.automation.operations.sell_operation import SellOperation
from src.automation.operations.funds_query_operation import FundsQueryOperation
from src.automation.operations.holding_query_operation import HoldingQueryOperation
from src.automation.operations.order_cancel_operation import OrderCancelOperation
from src.automation.operations.order_query_operation import OrderQueryOperation
import asyncio
from dotenv import load_dotenv

PROJECT_DIR = "D:/ProgramCodes/QuantTrader"
load_dotenv(PROJECT_DIR + "/.env")

settings = get_settings()
config = settings.to_dict()


# print(config.get('trading', {}))
automator = TonghuashunAutomator(config.get('trading', {}))

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







