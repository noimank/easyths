from src.automation.operation_manager import OperationManager
from src.utils.env_config import get_settings
from dotenv import load_dotenv

load_dotenv()


PROJECT_DIR = "D:/ProgramCodes/QuantTrader"


settings = get_settings()
config = settings.to_dict()

operation_manager = OperationManager(config.get('plugins', {}))

def test_load_plugins():
    operation_manager.load_plugins()
    assert  1 == 1



