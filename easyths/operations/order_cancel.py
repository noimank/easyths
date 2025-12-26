import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class OrderCancelOperation(BaseOperation):
    """撤单操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="CancelOperation",
            version="1.0.0",
            description="撤单操作",
            author="noimank",
            operation_name="order_cancel",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": False,
                    "description": "股票代码（6位数字），不指定则撤销所有待成交委托",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "cancel_type": {
                    "type": "string",
                    "required": False,
                    "description": "撤单类型，不指定则默认为全部撤单",
                    "enum": ["all", "sell", "buy"]
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证撤单参数"""
        try:
            stock_code = params.get("stock_code")
            cancel_type = params.get("cancel_type")
            # 如果提供了股票代码，验证其格式
            if stock_code is not None:
                if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                    self.logger.error("股票代码格式错误，必须是6位数字")
                    return False
            if cancel_type is not None and cancel_type not in ["all", "sell", "buy"]:
                self.logger.error("撤单类型错误，必须是'all'、'sell'或'buy'")
                return False
            self.logger.info(f"撤单参数验证通过，stock_code: {stock_code or '全部'}")
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
        if pop_dialog_title.strip() == "撤单确认":
            code_text = top_window.child_window(control_id=0x412).window_text()
            price_text = top_window.child_window(control_id=0x413).window_text()
            vol_text = top_window.child_window(control_id=0x414).window_text()
            tip_text = top_window.child_window(control_id=0x6E8).window_text()
            return f"{code_text}\n {price_text}\n {vol_text}\n {tip_text}"

        return "解析弹窗内容失败，请检查"

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行撤单操作"""
        stock_code = params.get("stock_code")  # 默认为None，表示撤销所有委托
        cancel_type = params.get("cancel_type", "all")  # 默认为全部撤单
        start_time = time.time()

        try:
            self.logger.info(
                f"执行撤单操作",
                stock_code=stock_code or "全部"
            )

            # 1. 打开撤单界面或切换到撤单标签页
            # 2. 如果指定了股票代码，查找对应的委托记录
            # 3. 执行撤单操作
            # 4. 处理各种确认弹窗
            # 5. 返回撤单结果

            main_window = self.get_main_window(wrapper_obj=True)
            #
            # # 切换到撤单界面（假设使用某个快捷键或菜单）
            main_window.type_keys("{F3}")
            time.sleep(0.2)
            main_panel = main_window.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]
            #
            # # 如果指定了股票代码，定位到对应的委托，默认清空，点击查询代码按钮相当于刷新数据
            # 模拟清空
            edit_stock_code = self.get_control_with_children(main_panel, control_type="Edit",class_name="Edit", auto_id="3348")
            edit_stock_code.type_keys('{BACKSPACE 6}')
            time.sleep(0.1)
            if stock_code:
                # 查找并选择指定股票的委托
                edit_stock_code.type_keys(str(stock_code))
            #
            query_btn = self.get_control_with_children(main_panel, control_type="Button",class_name="Button", auto_id="3349")
            query_btn.click()
            time.sleep(0.1)

            cancel_btn = None
            if cancel_type == "all":
                cancel_btn = self.get_control_with_children(main_panel, class_name="Button", control_type="Button", auto_id="30001")
            elif cancel_type == "buy":
                cancel_btn = self.get_control_with_children(main_panel, class_name="Button", control_type="Button", auto_id="30002")
            elif cancel_type == "sell":
                cancel_btn = self.get_control_with_children(main_panel, class_name="Button", control_type="Button", auto_id="30003")
            else:
                self.logger.error(f"不支持的撤单类型: {cancel_type}")
                return OperationResult(success=False, error=f"不支持的撤单类型: {cancel_type}")

            #必须有单才可以撤，没单的话，按钮是灰色的，click会报错
            if cancel_btn.is_enabled():
                cancel_btn.click()
            # 等待弹窗出现， 软件必须确保已经勾选 撤单不需要确认
            is_op_success = not self.wait_for_pop_dialog(0.4)  # 没有弹窗就是成功了，这里其实多余判断，但是无所谓，不耗什么时间

            result_data = {
                "stock_code": stock_code,
                "operation": "cancel",
                "success": is_op_success,
                "message": f"撤销{stock_code}的委托{'成功' if is_op_success else '失败'}" if stock_code else "已成功撤销所有委托",
            }

            self.logger.info(f"撤单操作{'成功' if is_op_success else '失败'}，耗时{time.time() - start_time}, 操作结果：",
                             **result_data)
            return OperationResult(
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"撤单操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
