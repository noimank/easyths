import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class ConditionOrderCancelOperation(BaseOperation):
    """条件单删除操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ConditionOrderCancelOperation",
            version="1.0.0",
            description="删除条件单",
            author="noimank",
            operation_name="condition_order_cancel",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": False,
                    "description": "股票代码（6位数字），不指定则删除所有条件单",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "order_type": {
                    "type": "string",
                    "required": False,
                    "description": "订单类型",
                    "enum": ["买入", "卖出"]
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证删除参数"""
        try:
            stock_code = params.get("stock_code")
            order_type = params.get("order_type")

            # 验证股票代码格式（如果提供了的话）
            if stock_code is not None:
                if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                    self.logger.error("股票代码格式错误，必须是6位数字")
                    return False

            # 验证订单类型（如果提供了的话）
            if order_type is not None and order_type not in ["买入", "卖出"]:
                self.logger.error("订单类型无效，有效值为：买入、卖出")
                return False

            self.logger.info("条件单删除参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def ensure_check(self, check_btn):
        """
        确保是选择状态
        """
        if check_btn.get_toggle_state():
            return
        check_btn.click()

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        start_time = time.time()
        stock_code = params.get("stock_code")
        order_type = params.get("order_type")

        try:
            self.logger.info(
                f"执行条件单删除操作",
                stock_code=stock_code or "全部",
                order_type=order_type or "全部"
            )

            main_window = self.get_main_window(wrapper_obj=True)
            # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("条件单", "条件单监控")
            self.sleep(0.1)
            main_window.type_keys("{F5}")
            self.sleep(0.3)
            # 有两个
            panel_AfxWnd140s_2 = \
            self.get_control_with_children(main_window, control_type="Pane", auto_id="59648").children(
                class_name="AfxMDIFrame140s")[0]
            panel_AfxWnd140s = self.get_control_with_children(panel_AfxWnd140s_2, auto_id="2393", control_type="Pane",
                                                              class_name="AfxWnd140s")
            cefbrowserwindow = self.get_control_with_children(panel_AfxWnd140s, control_type="Pane",
                                                              class_name="CefBrowserWindow")
            chrome_widget = self.get_control_with_children(cefbrowserwindow, control_type="Pane",
                                                           class_name="Chrome_WidgetWin_0")

            chrome_render_win = self.get_control_with_children(chrome_widget, control_type="Document",
                                                               class_name="Chrome_RenderWidgetHostHWND")

            # 检查是否有残留的内置弹窗, 还有另一个是系统维护的弹窗，暂时没有实验对象未实现
            confirm_pop_old = self.get_control_with_children(chrome_render_win, control_type="Custom", title="提示")
            if confirm_pop_old:
                self.get_control_with_children(confirm_pop_old, control_type="Button", title="取消").click()
                self.sleep(0.1)

            # 要选择  未触发
            type_tab_control = self.get_control_with_children(chrome_render_win, control_type="Tab")
            wcf_control = self.get_control_with_children(type_tab_control, control_type="TabItem", title="未触发")
            wcf_control.click_input()
            self.sleep(0.3)

            # 获取未触发的显示面板
            custom_pane = self.get_control_with_children(chrome_render_win, title="未触发", control_type="Custom",
                                                         auto_id="pane-not_triggered")
            # 准备解析表格数据
            table_raw_controls = custom_pane.children(control_type="Table")

            # 第一个是表头
            table_header = table_raw_controls[0].children(control_type="Custom")[0]
            header = [item.window_text() for item in table_header.children(control_type="Header")]
            # 第二个是数据表格
            data_tables = table_raw_controls[1].children()
            delete_count = 0
            op_message = "条件单删除失败"
            is_op_success = False

            # 解析表格
            for table_row in data_tables:
                data_items = table_row.children(control_type="DataItem")

                #操作复选框
                check_btn = data_items[0].children(control_type="CheckBox")[0]

                # 方向
                order_direction = data_items[4].window_text()
                #监控标的
                jkbd = data_items[5].window_text()
                # 全部删除
                if stock_code is None and order_type is None:
                    self.ensure_check(check_btn)
                    delete_count += 1
                # 指定股票代码
                elif stock_code and stock_code in jkbd:
                    if order_type is None:
                        self.ensure_check(check_btn)
                        delete_count += 1
                    elif order_type == order_direction:
                        self.ensure_check(check_btn)
                        delete_count += 1
                # 指定订单类型
                elif order_type and order_type == order_direction:
                    if stock_code is None:
                        self.ensure_check(check_btn)
                        delete_count += 1
            # 等待按钮变颜色
            self.sleep(0.2)
            # 删除按钮
            delete_btn = self.get_control_with_children(chrome_render_win, control_type="Button", title="删除")
            if delete_btn.is_enabled():
                delete_btn.click()
                #等待确认弹窗
                self.sleep(0.35)
                confirm_pop = self.get_control_with_children(chrome_render_win, control_type="Custom", title="提示")
                yes_btn = self.get_control_with_children(confirm_pop, control_type="Button", title="确认")
                yes_btn.click()
                is_op_success = True
            else:
                op_message = "没有符合筛选条件的条件单，无法进行删除操作"
                is_op_success = False

            # 占位实现
            result_data = {
                "stock_code": stock_code,
                "order_type": order_type,
                "deleted_count": delete_count,
                "message": op_message,
                "timestamp": time.time(),
                "success": is_op_success
            }

            self.logger.info(f"条件单删除操作耗时{time.time() - start_time}秒")
            return OperationResult(
                success=is_op_success,
                data=result_data
            )

        except Exception as e:
            error_msg = f"条件单删除操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )
