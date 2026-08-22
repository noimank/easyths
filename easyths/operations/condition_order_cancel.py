import time

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import ConditionOrderCancelParams
from easyths.operations.results import ConditionOrderCancelResult


class ConditionOrderCancelOperation(BaseOperation[ConditionOrderCancelParams]):
    """条件单删除操作"""

    operation_name = "condition_order_cancel"
    description = "删除条件单"
    Params = ConditionOrderCancelParams
    Result = ConditionOrderCancelResult

    def ensure_check(self, check_btn) -> None:
        """确保复选框是勾选状态"""
        if check_btn.get_toggle_state():
            return
        check_btn.click()

    def execute(self, params: ConditionOrderCancelParams) -> OperationResult:
        start_time = time.time()
        self.logger.info(
            "执行条件单删除操作",
            stock_code=params.stock_code or "全部",
            order_type=params.order_type or "全部",
        )

        main_window = self.get_main_window(wrapper_obj=True)
        # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        self.switch_left_menus("条件单", "条件单监控")
        self.sleep(0.1)
        main_window.type_keys("{F5}")
        self.sleep(0.3)
        panel_AfxWnd140s_2 = self.get_control_with_children(
            main_window, control_type="Pane", auto_id="59648"
        ).children(class_name="AfxMDIFrame140s")[0]
        panel_AfxWnd140s = self.get_control_with_children(
            panel_AfxWnd140s_2,
            auto_id="2393",
            control_type="Pane",
            class_name="AfxWnd140s",
        )
        cefbrowserwindow = self.get_control_with_children(
            panel_AfxWnd140s, control_type="Pane", class_name="CefBrowserWindow"
        )
        chrome_widget = self.get_control_with_children(
            cefbrowserwindow, control_type="Pane", class_name="Chrome_WidgetWin_0"
        )
        chrome_render_win = self.get_control_with_children(
            chrome_widget,
            control_type="Document",
            class_name="Chrome_RenderWidgetHostHWND",
        )

        # 检查是否有残留的内置弹窗, 还有另一个是系统维护的弹窗，暂时没有实验对象未实现
        confirm_pop_old = self.get_control_with_children(
            chrome_render_win, control_type="Custom", title="提示"
        )
        if confirm_pop_old:
            self.get_control_with_children(
                confirm_pop_old, control_type="Button", title="取消"
            ).click()
            self.sleep(0.3)

        # 切换到「未触发」页签
        type_tab_control = self.get_control_with_children(
            chrome_render_win, control_type="Tab"
        )
        wcf_control = self.get_control_with_children(
            type_tab_control, control_type="TabItem", title="未触发"
        )
        wcf_control.click_input()
        self.sleep(0.3)

        # 获取未触发的显示面板
        custom_pane = self.get_control_with_children(
            chrome_render_win,
            title="未触发",
            control_type="Custom",
            auto_id="pane-not_triggered",
        )
        table_raw_controls = custom_pane.children(control_type="Table")
        # 第一个是表头，第二个是数据表格
        data_tables = table_raw_controls[1].children()

        # 勾选符合筛选条件的行
        delete_count = 0
        for table_row in data_tables:
            data_items = table_row.children(control_type="DataItem")
            check_btn = data_items[0].children(control_type="CheckBox")[0]
            order_direction = data_items[4].window_text()
            jkbd = data_items[5].window_text()

            code_matched = params.stock_code is None or params.stock_code in jkbd
            type_matched = (
                params.order_type is None or params.order_type == order_direction
            )
            if code_matched and type_matched:
                self.ensure_check(check_btn)
                delete_count += 1

        # 等待按钮变颜色后点击删除
        self.sleep(0.3)
        delete_btn = self.get_control_with_children(
            chrome_render_win, control_type="Button", title="删除"
        )
        if delete_btn.is_enabled():
            delete_btn.click()
            # 等待确认弹窗
            self.sleep(0.5)
            confirm_pop = self.get_control_with_children(
                chrome_render_win, control_type="Custom", title="提示"
            )
            self.get_control_with_children(
                confirm_pop, control_type="Button", title="确认"
            ).click()
            message = f"条件单删除成功，删除{delete_count}条记录"
        else:
            message = "没有符合筛选条件的条件单，无法进行删除操作"

        return self._ok(
            data=ConditionOrderCancelResult(
                stock_code=params.stock_code,
                order_type=params.order_type,
                deleted_count=delete_count,
            ).model_dump(),
            message=f"{message}，耗时{time.time() - start_time:.2f}秒",
        )
