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
                    "description": "卖出数量（必须是100的倍数）",
                    "minimum": 100,
                    "multiple_of": 100
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

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行卖出操作"""
        stock_code = params["stock_code"]
        # 转为 2位小数的字符
        price =  "{:.2f}".format(float(params["price"]))
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
            main_window.type_keys("{F2}")
            # 防抖
            self.sleep(0.25)
            # 拿到显示面板, 大约会有 34个children
            main_panel = main_window.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]
            # # 1. 输入股票代码
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1032").type_keys(stock_code)
            # # 2.输入价格
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1033").type_keys(price)
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
            message = f"成功提交{stock_code}的卖出委托"
            if not is_op_success:
                # 不成功就尝试获取弹窗内容
                pop_dialog_title, pop_control = self.get_pop_dialog()
                if pop_dialog_title == "失败提示":
                    message = self.get_control_with_children(pop_control, control_type="Image", auto_id="1004",
                                                             class_name="Static").window_text()
                    self.get_control_with_children(pop_control, control_type="Button", auto_id="2",
                                                   class_name="Button").type_keys("{ENTER}")
            # 返回买入结果
            result_data = {
                "stock_code": stock_code,
                "price": price,
                "quantity": quantity,
                "operation": "buy",
                "success": is_op_success,
                "message": message
            }

            self.logger.info(f"卖出操作{"成功" if is_op_success else "失败"}，耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"卖出操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)