import time

from easyths.core import BaseOperation
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import ReverseRepoBuyParams
from easyths.operations.results import ReverseRepoBuyResult


class ReverseRepoBuyOperation(BaseOperation[ReverseRepoBuyParams]):
    """国债逆回购操作"""

    operation_name = "reverse_repo_buy"
    description = "国债逆回购（出借资金），购买后可在委托查询中查看"
    Params = ReverseRepoBuyParams
    Result = ReverseRepoBuyResult

    # 期限 → 回购代码后缀
    _CODE_MAP = {
        "1天期": "001",
        "2天期": "002",
        "3天期": "003",
        "4天期": "004",
        "7天期": "007",
    }

    def select_target_area(self, table_controls, key_word):
        """根据关键字（如 GC001）点击并返回目标行控件，未找到返回 None"""
        for table_item in table_controls:
            texts = (
                table_item.children(control_type="Custom")[0]
                .children(control_type="DataItem")[0]
                .children(control_type="Text")
            )
            if key_word in "".join(t.window_text() for t in texts):
                table_item.click_input()
                self.sleep(0.05)
                return table_item
        return None

    def execute(self, params: ReverseRepoBuyParams) -> OperationResult:
        start_time = time.time()
        self.logger.info(
            "执行国债逆回购操作",
            market=params.market,
            time_range=params.time_range,
            amount=params.amount,
        )
        target_keyword = ("GC" if params.market == "上海" else "R-") + self._CODE_MAP[
            params.time_range
        ]

        main_window = self.get_main_window(wrapper_obj=True)
        # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        self.switch_left_menus("通用回购")

        if not self.wait_for_pop_dialog(5):
            return self._fail("国债逆回购下单窗口未打开")
        pop_dialog_title, pop_control = self.get_pop_dialog()
        if pop_dialog_title != "通用回购":
            return self._fail(f"国债逆回购下单窗口异常: {pop_dialog_title}")

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

        def close_window():
            self.get_control_with_children(
                pop_control,
                control_type="Button",
                auto_id="1008",
                class_name="Button",
            ).click()

        # 会有10个元素
        table_panel = document_panel.children(control_type="Table")
        if self.select_target_area(table_panel, target_keyword) is None:
            close_window()
            return self._fail(
                f"国债逆回购操作失败，未找到{target_keyword}对应的回购品种",
                ErrorCode.CLIENT_REJECTED,
            )

        # 输入金额
        self.get_control_with_children(
            document_panel, control_type="Edit", auto_id="shuru"
        ).set_text(str(params.amount))
        self.sleep(0.1)
        # 点击出借，这个是文本渲染的，如果出借金额不足，马上会变成灰色，
        # 此时无法触发出借并关闭窗口的事件
        chujie_btn = self.get_control_with_children(
            document_panel, control_type="Text", title="出借"
        )
        chujie_btn.click_input()
        self.sleep(0.1)
        # 是否出现确认询问
        ask_pop_dialog = self.get_control_with_children(
            document_panel, control_type="Text", title_contains="您是否确认以上"
        )
        self.sleep(0.1)

        if ask_pop_dialog is None:
            # 定位元素属性缺乏，只能顺序取，可能不保证是对应的元素，实测其实也还行，
            # 可能后面遇到同花顺界面重构会要修改
            available_amount = document_panel.children(control_type="Text")[10]
            op_message = (
                f"国债逆回购操作失败，计划出借金额：{params.amount} 元，"
                f"可用金额：{available_amount.window_text()} 元"
            )
            is_op_success = False
        else:
            annual_rate = (
                self.get_control_with_children(
                    document_panel, control_type="Text", title_contains="%"
                )
                .window_text()
                .replace("\xa0", "")
            )
            op_message = f"国债逆回购操作成功，成功出借:{params.amount} 元，年化利率为：{annual_rate}"
            self.get_control_with_children(
                document_panel, control_type="Text", title="确定"
            ).click_input()
            is_op_success = True

        # 成功与否都需要把窗口关闭
        close_window()

        if is_op_success:
            return self._ok(
                data=ReverseRepoBuyResult(
                    market=params.market,
                    time_range=params.time_range,
                    amount=params.amount,
                    annual_rate=annual_rate,
                ).model_dump(),
                message=f"{op_message}，耗时{time.time() - start_time:.2f}秒",
            )
        return self._fail(op_message, ErrorCode.CLIENT_REJECTED)
