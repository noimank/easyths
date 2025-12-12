import asyncio
import time
from typing import Dict, Any

import pywinauto

from src.automation.base_operation import BaseOperation, register_operation
from src.automation.utils.pop_dialog_handle import PopDialogHandler
from src.models.operations import PluginMetadata, OperationResult

@register_operation
class BuyOperation(BaseOperation):
    """买入股票操作"""

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

    async def validate(self, params: Dict[str, Any]) -> bool:
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

    def handle_pop_dialogs(self):
        handler = PopDialogHandler(self.automator.app)

        while self.automator.is_exist_pop_dialog():
            try:
                title = self.automator.get_pop_dialog_title()
            except pywinauto.findwindows.ElementNotFoundError:
                return {"message": "success"}

            result = handler.handle(title)
            if result:
                return result
        return {"message": "success"}

    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行买入操作"""
        stock_code = params["stock_code"]
        # 转为 2位小数的字符
        price =  "{:.2f}".format(float(params["price"]))
        print("price=", price)
        quantity = params["quantity"]
        market = params.get("market", "SH")
        start_time = time.time()
        try:
            self.logger.info(
                f"执行买入操作",
                stock_code=stock_code,
                market=market,
                price=price,
                quantity=quantity
            )

            top = self.get_top_window()
            main_window = self.automator.get_main_window()
            # web_view = self.automator.get_control(parent=main_window,title_re="Internet Explorer.*", found_index=None)


            # self.close_pop_dialog()

            print("top=",top)
            f = self.is_exist_pop_dialog()
            print("f=",f)
            title = self.get_pop_dialog_title()
            print("title=",title)

            self.set_main_window_focus()

            # 打印树



            # 按下 F1键
            # main_window = await self.automator.get_main_window()
            # main_window.type_keys("{F1}")
            #
            # reset_btn = await self.automator.get_control(parent=main_window,class_name="Button", found_index=None,control_id=0x3EF)
            # reset_btn.click()
            #
            # # 1. 输入股票代码
            # # 设置股票代码
            # edit_ts_code = await self.automator.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x408)
            #
            # edit_ts_code.type_keys(stock_code)
            #
            # await asyncio.sleep(0.5)
            #
            # # 输入价格,不能直接设置，只能模拟输入
            # price_edit = await self.automator.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x409)
            # price_edit.set_edit_text('')
            # price_edit.type_keys(str(price))
            # #  输入数量
            # quantity_edit = await self.automator.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x40A)
            # # quantity_edit.set_edit_text('')
            # quantity_edit.type_keys(str(quantity))
            #
            #
            # #点击买入按钮
            # buy_button = await self.automator.get_control(parent=main_window,class_name="Button", found_index=None,control_id=0x3EE)
            # buy_button.click()
            #
            # resule = self.handle_pop_dialogs()
            # print("rrrrrr=",resule)



            # 返回买入结果
            result_data = {
                "stock_code": stock_code,
                "market": market,
                "price": price,
                "quantity": quantity,
                "amount": price * quantity,
                "operation": "buy",
                "status": "submitted"
            }


            print("耗时：{}s".format(time.time()-start_time))
            return OperationResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"买入操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
