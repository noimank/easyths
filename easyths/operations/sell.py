import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


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
                    "description": "卖出数量（股票必须是100的倍数，可转债必须是10的倍数）",
                    "minimum": 10,
                    "multiple_of": 10
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
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

            # 验证数量（可转债11/12开头为10的倍数，其余为100的倍数）
            is_convertible_bond = stock_code.startswith(("11", "12"))
            min_qty = 10 if is_convertible_bond else 100
            multiple = 10 if is_convertible_bond else 100
            if not isinstance(quantity, int) or quantity < min_qty or quantity % multiple != 0:
                self.logger.error(f"数量必须是{multiple}的倍数且不小于{min_qty}" + ("（可转债）" if is_convertible_bond else ""))
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

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行卖出操作"""
        stock_code = params["stock_code"]
        # 判断代码是否是etf,股票类别和etf类别精度不一致 https://github.com/noimank/easyths/issues/6
        if stock_code.startswith("5") or stock_code.startswith("1"):
            price = "{:.3f}".format(float(params["price"]))
        else:
            price = "{:.2f}".format(float(params["price"]))

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
            main_window = self.get_main_window(wrapper_obj=True)
            # 切换到别的页面再切会买入页面会清空可能残留的操作信息，增强操作可用性
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            main_window.type_keys("{F2}")
            # 防抖
            self.sleep(0.25)
            # 拿到显示面板, 大约会有 34个children
            main_panel = self.get_control_with_children(main_window, class_name="AfxMDIFrame140s", control_type="Pane", auto_id="59648").children(class_name='AfxMDIFrame140s')[0]
            # # 1. 输入股票代码
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1032").type_keys(stock_code)
            self.sleep(0.08)
            # # 2.输入价格
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1033").type_keys(price)
            self.sleep(0.08)
            # # 3. 输入数量
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1034").type_keys(str(quantity))
            # # 等待输入数量后稳定在确认
            self.sleep(0.3)
            # 4. 点击买入按钮
            main_window.type_keys("{ENTER}")
            # self.sleep(0.25)
            self.wait_for_pop_dialog(0.3)
            # 没弹窗就是成功，这里已经假设用户已经按照项目设置好软件，为了加快操作速度，去掉了多余的弹窗处理（因为设置好软件后不会有弹窗）
            is_op_success = not self.is_exist_pop_dialog()
            # 证券名称，如果购买成功，stock_name会清空
            stock_name = self.get_control_with_children(main_panel, control_type="Text", auto_id="1036").window_text()

            message = f"成功提交{stock_code}的卖出委托"
            if not is_op_success:
                # 不成功就尝试获取弹窗内容
                pop_dialog_title, pop_control = self.get_pop_dialog()
                if pop_dialog_title == "失败提示":
                    message = self.get_control_with_children(pop_control, control_type="Image", auto_id="1004",
                                                             class_name="Static").window_text()
                    self.get_control_with_children(pop_control, control_type="Button", auto_id="2",
                                                   class_name="Button").type_keys("{ENTER}")
            # 二次确认
            elif len(stock_name) > 0:
                message = f"卖出操作未能成功，请检查软件设置是否有项目要求不符的地方"
                is_op_success = False

            # 返回买入结果
            result_data = {
                "stock_code": stock_code,
                "price": price,
                "quantity": quantity,
            }

            self.logger.info(f"卖出操作{"成功" if is_op_success else "失败"}，耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                message=message,
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"卖出操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, message=error_msg)