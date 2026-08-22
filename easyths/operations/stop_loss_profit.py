import re
import time

from easyths.core import BaseOperation
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import StopLossParams
from easyths.operations.results import StopLossResult

# 策略有效期在下拉列表中的索引（客户端固定档位 1/3/5/10/20/30）
_EXPIRE_INDEX = {"1": 0, "3": 1, "5": 2, "10": 3, "20": 4, "30": 5}


class StopLossProfitOperation(BaseOperation[StopLossParams]):
    """止盈止损操作"""

    operation_name = "stop_loss_profit"
    description = "设置止盈止损"
    Params = StopLossParams
    Result = StopLossResult

    def execute(self, params: StopLossParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        self.logger.info(
            "执行止盈止损操作",
            stock_code=stock_code,
            stop_loss_percent=params.stop_loss_percent,
            stop_profit_percent=params.stop_profit_percent,
        )

        main_window = self.get_main_window(wrapper_obj=True)
        # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
        main_window.type_keys("{F3}")
        self.sleep(0.2)
        self.switch_left_menus("条件单", "止盈止损")
        self.wait_for_pop_dialog(2.51)

        pop_dialog_title, _ = self.get_pop_dialog()
        if pop_dialog_title != "ConditionToolBar":
            return self._fail(f"止盈止损窗口未打开: {pop_dialog_title}")

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

        # 不支持输入完整的代码，需要截断触发筛选
        document_panel.children(control_type="Edit")[0].set_text(stock_code[:5])
        self.sleep(0.5)

        # 在筛选出的持仓列表中定位标的
        has_order = False
        try:
            stock_list_controls = document_panel.children(control_type="List")[0]
            for stock_cc in stock_list_controls.children():
                item_text = stock_cc.children(control_type="Text")[0].window_text()
                if stock_code in item_text:
                    stock_cc.children(control_type="Text")[0].click_input()
                    has_order = True
                    break
        except IndexError:
            # 没有持仓记录时列表为空
            pass

        if not has_order:
            return self._fail(
                f"执行{stock_code}的止盈止损单失败，请检查是否持仓该股票",
                ErrorCode.CLIENT_REJECTED,
            )

        # 盈利/亏损填写
        document_panel.children(control_type="Edit")[4].set_text(
            str(params.stop_profit_percent)
        )
        self.sleep(0.05)
        document_panel.children(control_type="Edit")[6].set_text(
            str(params.stop_loss_percent)
        )
        self.sleep(0.1)

        # 下一步
        self.get_control_with_children(
            document_panel, control_type="Button", title="下一步"
        ).click()
        self.sleep(0.5)

        # 填写委托数量，未指定则自动取可卖数量
        quantity = params.quantity
        if quantity is None:
            available_text = self.get_control_with_children(
                document_panel, control_type="Text", title_contains="可卖"
            ).window_text()
            quantity = int(re.search(r"\d+", available_text).group())
        document_panel.children(control_type="Edit")[4].set_text(str(quantity))

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

        # 提交确认
        self.get_control_with_children(
            document_panel, control_type="Button", title="提交确认"
        ).click()
        # 可能出现的成功提示弹窗无需处理，下一次操作的 close_pop_dialog 会统一清理

        return self._ok(
            data=StopLossResult(
                stock_code=stock_code,
                stop_loss_percent=params.stop_loss_percent,
                stop_profit_percent=params.stop_profit_percent,
                quantity=quantity,
                expire_days=params.expire_days,
            ).model_dump(),
            message=f"执行{stock_code}的止盈止损单成功，耗时{time.time() - start_time:.2f}秒",
        )
