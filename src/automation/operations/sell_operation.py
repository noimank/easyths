import time
from typing import Dict, Any

from src.automation.base_operation import BaseOperation, register_operation
from src.models.operations import PluginMetadata, OperationResult


@register_operation
class SellOperation(BaseOperation):
    """卖出股票操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SellOperation",
            version="1.0.0",
            description="卖出股票操作",
            author="noimank",
            operation_name="sell",
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
                    "description": "卖出价格",
                    "minimum": 0.01,
                    "maximum": 10000
                },
                "quantity": {
                    "type": "integer",
                    "required": True,
                    "description": "卖出数量（必须是100的倍数）",
                    "minimum": 100,
                    "multiple_of": 100
                }
            }
        )

    async def validate(self, params: Dict[str, Any]) -> bool:
        """验证卖出参数"""
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

            self.logger.info("卖出参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False


    def _extract_pop_dialog_content(self,pop_dialog_title):
        top_window = self.get_top_window()
        if pop_dialog_title.strip() in ["委托确认", "提示信息"]:
            return top_window.child_window(control_id=0x410).window_text()
        if "提示" == pop_dialog_title.strip():
            return top_window.child_window(control_id=0x3EC).window_text()

        return "解析弹窗内容失败，请检查"

    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行卖出操作"""
        stock_code = params["stock_code"]
        # 转为 2位小数的字符
        price =  "{:.2f}".format(float(params["price"]))
        print("price=", price)
        quantity = params["quantity"]
        start_time = time.time()
        try:
            self.logger.info(
                f"执行卖出操作",
                stock_code=stock_code,
                price=price,
                quantity=quantity
            )

            # 按下 F2键 （卖出快捷键）
            main_window =  self.automator.get_main_window()
            # self.set_main_window_focus()
            main_window.type_keys("{F2}")
            #防抖
            time.sleep(0.1)

            # 1. 输入股票代码
            # 设置股票代码
            edit_ts_code = self.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x408)
            # edit_ts_code.set_edit_text('')
            # time.sleep(0.1)
            edit_ts_code.type_keys(stock_code)
            # 防抖，因为输入代码后软件会自动获取相关信息，这一步需要时间
            # time.sleep(1.1)

            # 输入价格,不能直接设置，只能模拟输入
            price_edit =  self.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x409)
            price_edit.set_edit_text('')
            # time.sleep(0.1)
            price_edit.type_keys(str(price))
            #  输入数量
            quantity_edit =  self.get_control(parent=main_window,class_name="Edit", found_index=None,control_id=0x40A)
            quantity_edit.set_edit_text('')
            # time.sleep(0.1)
            quantity_edit.type_keys(str(quantity))

            #点击卖出按钮
            sell_button =  self.get_control(parent=main_window,class_name="Button", found_index=None,control_id=0x3EE)
            sell_button.click()
            # 等待弹窗出现
            time.sleep(0.2)

            is_sell_success = False
            sell_message = ""
            # 开始处理各种弹窗
            count = 0  #防止死循环
            while self.is_exist_pop_dialog() and count < 4:
                time.sleep(0.1)
                pop_dialog_title = self.get_pop_dialog_title()
                top_window = self.get_top_window()
                pop_dialog_content = self._extract_pop_dialog_content(pop_dialog_title)

                # 提示窗口只有确认按钮，不具备下一步的操作直接esc退出
                if "提示" == pop_dialog_title.strip():
                    top_window.type_keys("{ESC}", set_foreground=False)
                else:
                    top_window.type_keys("%Y", set_foreground=False)
                #等待窗口关闭
                time.sleep(0.25)
                sell_message = pop_dialog_content
                if "成功" in pop_dialog_content:
                    is_sell_success = True
                count +=1

            # 返回卖出结果
            result_data = {
                "stock_code": stock_code,
                "price": price,
                "quantity": quantity,
                "operation": "sell",
                "success": is_sell_success,
                "message": sell_message
            }

            self.logger.info(f"卖出操作完成，耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                success=True,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"卖出操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)