
import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class BuyOperation(BaseOperation):
    """买入股票操作 - 同步执行模式"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="BuyOperation",
            version="1.0.0",
            description="买入股票操作",
            author="noimank",
            operation_name="buy",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": True,
                    "description": "股票代码（6位数字）",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "price": {
                    "type": "number",
                    "required": True,
                    "description": "买入价格",
                    "minimum": 0.01,
                    "maximum": 10000
                },
                "quantity": {
                    "type": "integer",
                    "required": True,
                    "description": "买入数量（必须是100的倍数）",
                    "minimum": 100,
                    "multiple_of": 100
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证买入参数"""
        try:
            # 检查必需参数
            required_params = ["stock_code", "price", "quantity"]
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            stock_code = params["stock_code"]
            price = params["price"]
            quantity = params["quantity"]

            # 验证股票代码
            if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                self.logger.error("股票代码格式错误，必须是6位数字")
                return False

            # 验证价格
            if not isinstance(price, (int, float)) or price <= 0:
                self.logger.error("价格必须大于0")
                return False

            # 验证数量
            if not isinstance(quantity, int) or quantity < 100 or quantity % 100 != 0:
                self.logger.error("数量必须是100的倍数且不小于100")
                return False

            # 验证价格和数量的合理性
            if price * quantity > 10000000:  # 单笔不超过1000万
                self.logger.error("单笔金额过大")
                return False

            self.logger.info("买入参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def _extract_pop_dialog_content(self, pop_dialog_title):
        """提取弹窗内容"""
        top_window = self.get_top_window()
        if pop_dialog_title.strip() in ["委托确认", "提示信息"]:
            return top_window.child_window(control_id=0x410).window_text()
        if "提示" == pop_dialog_title.strip():
            return top_window.child_window(control_id=0x3EC).window_text()

        return "解析弹窗内容失败，请检查"

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行买入操作 - 同步方法"""
        stock_code = params["stock_code"]
        # 转为 2位小数的字符
        price = "{:.2f}".format(float(params["price"]))
        print("price=", price)
        quantity = params["quantity"]
        start_time = time.time()

        try:
            self.logger.info(
                f"执行买入操作",
                stock_code=stock_code,
                price=price,
                quantity=quantity
            )

            # 按下 F1键
            main_window = self.get_main_window()
            top_window = self.get_top_window()

            main_window.type_keys("{F1}")
            # 防抖
            time.sleep(0.1)

            # 1. 输入股票代码
            self.get_control(parent=main_window, control_type="Edit", auto_id="1032").type_keys(stock_code)
            time.sleep(0.6)

            # 返回买入结果
            result_data = {
                "stock_code": stock_code,
                "price": price,
                "quantity": quantity,
                "operation": "buy",
            }

            self.logger.info(f"买入操作完成，耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"买入操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
