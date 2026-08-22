import time
from typing import Any

import pandas as pd

from easyths.core import BaseOperation
from easyths.models.operations import EmptyParams, OperationResult
from easyths.operations.results import ConditionOrderRow
from easyths.utils import df_to_records


class ConditionOrderQueryOperation(BaseOperation[EmptyParams]):
    """条件单查询操作"""

    operation_name = "condition_order_query"
    description = "查询条件单信息"
    Params = EmptyParams
    Result = ConditionOrderRow

    def parse_condition_row(self, record: dict[str, Any]) -> ConditionOrderRow:
        """条件单表格记录 → 行模型（显式字段装配，列名差异在此适配）"""
        return ConditionOrderRow(
            status=record["状态"],
            condition_type=record["条件类型"],
            direction=record["方向"],
            target=record["监控标的"],
            trigger_condition=record["触发条件"],
            latest_price=record["最新价"],
            change_ratio=record["涨幅"],
            order_detail=record["委托单"],
            created_at=record["创建时间"],
            monitor_cycle=record["监控周期"],
        )

    def execute(self, params: EmptyParams) -> OperationResult:
        start_time = time.time()
        self.logger.info("执行条件单查询操作")
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
        table_header = table_raw_controls[0].children(control_type="Custom")[0]
        header = [
            item.window_text() for item in table_header.children(control_type="Header")
        ]
        data_tables = table_raw_controls[1].children()

        data = [
            [
                table_cell.window_text().replace("\xa0", " ")
                for table_cell in table_row.children(control_type="DataItem")
            ]
            for table_row in data_tables
        ]

        df = pd.DataFrame(data, columns=header)
        # 丢弃第一列（复选框列），逐行显式装配，缺列会在此明确报错
        df = df.drop(df.columns[0], axis=1)
        records = [
            self.parse_condition_row(record).model_dump()
            for record in df_to_records(df)
        ]

        return self._ok(
            data=records,
            message=f"条件单查询成功，共获取到{len(df)}条数据，耗时{time.time() - start_time:.2f}秒",
        )
