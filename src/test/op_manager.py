from src.automation.operation_manager import OperationManager
from src.utils.config_loader import load_config



PROJECT_DIR = "D:/ProgramCodes/QuantTrader"


config = load_config(f"{PROJECT_DIR}/config/trading_config.yaml")

operation_manager = OperationManager(config.get('plugins', {}))

def test_load_plugins():
    operation_manager.load_plugins()
    assert  1 == 1



