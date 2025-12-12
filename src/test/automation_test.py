
from src.automation.operation_manager import OperationManager
from src.automation.tonghuashun_automator import TonghuashunAutomator
from src.utils.config_loader import load_config
from src.automation.operations.buy_operation import BuyOperation
import asyncio

PROJECT_DIR = "D:/ProgramCodes/QuantTrader"


config = load_config(f"{PROJECT_DIR}/config/trading_config.yaml")


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







