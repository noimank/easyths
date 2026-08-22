import time

from easyths.core import BaseOperation
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import ConditionOrderParams, format_price
from easyths.operations.results import ConditionOrderResult

# 策略有效期在下拉列表中的索引（客户端固定档位 1/3/5/10/20/30）
_EXPIRE_INDEX = {"1": 0, "3": 1, "5": 2, "10": 3, "20": 4, "30": 5}


class ConditionSellOperation(BaseOperation[ConditionOrderParams]):
    """条件卖出股票操作（股价达到触发价自动卖出）"""

    operation_name = "condition_sell"
    description = "条件卖出股票（股价达到触发价自动卖出）"
    Params = ConditionOrderParams
    Result = ConditionOrderResult

    def execute(self, params: ConditionOrderParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        target_price = format_price(stock_code, params.target_price)

        self.logger.info(
            "执行条件卖出操作",
            stock_code=stock_code,
            target_price=target_price,
            quantity=params.quantity,
        )

        main_window = self.get_main_window(wrapper_obj=True)
        # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        self.switch_left_menus("条件单", "股价条件")
        self.wait_for_pop_dialog(2.5)

        pop_dialog_title, _ = self.get_pop_dialog()
        if pop_dialog_title != "ConditionToolBar":
            return self._fail(
                f"条件单窗口未打开: {pop_dialog_title}", ErrorCode.UI_ERROR
            )

        main_panel = main_window.children(control_type="Pane", class_name="#32770")[
            0
        ].children(control_type="Pane", class_name="AfxWnd140s")[0]
        inner_panel2 = main_panel.children(
            control_type="Pane", class_name="CefBrowserWindow"
        )[0].children(control_type="Pane", class_name="Chrome_WidgetWin_0")[0]
        document_panel = self.get_control_with_children(
            inner_panel2,
            control_type="Document",
            class_name="Chrome_RenderWidgetHostHWND",
        )

        # 切换到卖出页签
        tab_control = self.get_control_with_children(document_panel, control_type="Tab")
        tab_control.children()[1].click_input()
        self.sleep(0.3)

        combox = self.get_control_with_children(document_panel, control_type="ComboBox")
        stock_edit = self.get_control_with_children(
            combox, control_type="Edit", title_contains="代码"
        )
        stock_edit.set_text(stock_code)
        # 设置触发价格
        self.get_control_with_children(document_panel, control_type="Edit").set_text(
            target_price
        )
        self.sleep(0.3)

        # 下一步（按钮不可用说明没有持仓），模拟账户在非交易日也是灰色
        next_btn = self.get_control_with_children(
            document_panel, control_type="Button", title="下一步"
        )
        if not next_btn.is_enabled():
            return self._fail(
                "条件卖出设置失败，请检查是否持有该标的或者交易日再尝试",
                ErrorCode.CLIENT_REJECTED,
            )
        next_btn.click()
        # 等页面重绘渲染
        self.sleep(0.5)

        # 只能根据序号定位数量输入框
        document_panel.children(control_type="Edit")[2].set_text(str(params.quantity))
        self.sleep(0.15)

        # 选择全自动委托（模拟交易中该项为灰色）
        weituo_btn = self.get_control_with_children(
            document_panel, control_type="RadioButton", title="全自动委托"
        )
        if not weituo_btn.is_selected() and weituo_btn.is_enabled():
            weituo_btn.select()
            self.sleep(0.6)
            # 可能出现“成功添加到条件单”的温馨提示，勾选不再提醒并关闭
            inner_pane = self.get_control_with_children(
                document_panel, control_type="Custom", title="温馨提示"
            )
            if inner_pane:
                self.get_control_with_children(
                    inner_pane, control_type="CheckBox"
                ).click()
                self.sleep(0.2)
                self.get_control_with_children(
                    inner_pane, control_type="Button", title="我知道了"
                ).click()

        # 选择策略有效期
        expire_choose = document_panel.children(control_type="Edit", title="请选择")[1]
        expire_choose.click_input()
        self.sleep(0.3)
        expire_list_control = self.get_control_with_children(
            document_panel, control_type="List"
        )
        expire_list_control.children(control_type="ListItem")[
            _EXPIRE_INDEX[str(params.expire_days)]
        ].invoke()
        self.sleep(0.2)
        expire_list_control.type_keys("{ENTER}")
        self.sleep(0.2)

        self.get_control_with_children(
            document_panel, control_type="Button", title="提交确认"
        ).click()
        # 可能出现的成功提示弹窗无需处理，下一次操作的 close_pop_dialog 会统一清理

        return self._ok(
            data=ConditionOrderResult(
                stock_code=stock_code,
                target_price=params.target_price,
                quantity=params.quantity,
                expire_days=params.expire_days,
            ).model_dump(),
            message=f"执行{stock_code}的条件卖出成功，耗时{time.time() - start_time:.2f}秒",
        )
