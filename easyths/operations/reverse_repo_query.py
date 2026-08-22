import time

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import EmptyParams
from easyths.operations.results import ReverseRepoQuote


class ReverseRepoQueryOperation(BaseOperation[EmptyParams]):
    """国债逆回购查询操作"""

    operation_name = "reverse_repo_query"
    description = "查询国债逆回购年化利率信息"
    Params = EmptyParams
    Result = ReverseRepoQuote

    def parse_table_panels(self, table_controls: list) -> list:
        data_list = []
        for table_item_wrapper in table_controls:
            table_item = (
                table_item_wrapper.children(control_type="Custom")[0]
                .children(control_type="DataItem")[0]
                .children(control_type="Text")
            )
            time_type = table_item[0].window_text()
            type_flag = table_item[1].window_text()
            year_profit = table_item[2].window_text()
            data_list.append(
                ReverseRepoQuote(
                    market="上海" if "GC" in type_flag else "深圳",
                    term=time_type,
                    annual_rate=year_profit,
                ).model_dump()
            )
        return data_list

    def execute(self, params: EmptyParams) -> OperationResult:
        start_time = time.time()
        self.logger.info("执行国债逆回购查询操作")
        main_window = self.get_main_window(wrapper_obj=True)
        # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        self.switch_left_menus("通用回购")

        if not self.wait_for_pop_dialog(5):
            return self._fail("国债逆回购窗口未打开")
        pop_dialog_title, pop_control = self.get_pop_dialog()
        if pop_dialog_title != "通用回购":
            return self._fail(f"国债逆回购窗口异常: {pop_dialog_title}")

        AfxWnd140s_pane = self.get_control_with_children(
            pop_control,
            control_type="Pane",
            auto_id="3001",
            class_name="AfxWnd140s",
        )
        CefBrowserWindow_pane = self.get_control_with_children(
            AfxWnd140s_pane, control_type="Pane", class_name="CefBrowserWindow"
        )
        Chrome_WidgetWin_0_pane = self.get_control_with_children(
            CefBrowserWindow_pane, control_type="Pane", class_name="Chrome_WidgetWin_0"
        )
        document_panel = self.get_control_with_children(
            Chrome_WidgetWin_0_pane,
            control_type="Document",
            class_name="Chrome_RenderWidgetHostHWND",
        )

        # 会有10个元素
        table_panel = document_panel.children(control_type="Table")
        reverse_repo_interest = self.parse_table_panels(table_panel)

        # 查询完成后关闭窗口
        self.get_control_with_children(
            pop_control,
            control_type="Button",
            auto_id="1008",
            class_name="Button",
        ).click()

        return self._ok(
            data=reverse_repo_interest,
            message=f"查询国债逆回购年化利率成功，耗时{time.time() - start_time:.2f}秒",
        )
