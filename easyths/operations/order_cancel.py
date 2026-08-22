import time

import pandas as pd

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import OrderCancelParams
from easyths.operations.results import OrderCancelResult
from easyths.utils import text2df


def _count_cancel_rows(table_df: pd.DataFrame, cancel_type: str) -> int:
    """统计将被撤销的委托笔数（按操作列的委托方向过滤）"""
    if table_df.empty:
        return 0
    if cancel_type == "all":
        return len(table_df)
    keyword = "买" if cancel_type == "buy" else "卖"
    return int(table_df["操作"].str.contains(keyword).sum())


class OrderCancelOperation(BaseOperation[OrderCancelParams]):
    """撤单操作"""

    operation_name = "order_cancel"
    description = "撤销委托订单"
    Params = OrderCancelParams
    Result = OrderCancelResult

    # 撤单按钮 auto_id 映射
    _BTN_IDS = {
        "all": "30001",
        "buy": "30002",
        "sell": "30003",
    }

    def execute(self, params: OrderCancelParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        self.logger.info(
            "执行撤单操作",
            stock_code=stock_code or "全部",
            cancel_type=params.cancel_type,
        )

        main_window = self.get_main_window(wrapper_obj=True)
        # 切换到撤单界面（F3）
        main_window.type_keys("{F3}")
        time.sleep(0.2)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 清空查询框（显示全部委托），指定股票代码则输入过滤；
        # 点击查询按钮相当于刷新数据
        edit_stock_code = self.get_control_with_children(
            main_panel, control_type="Edit", class_name="Edit", auto_id="3348"
        )
        edit_stock_code.type_keys("{BACKSPACE 6}")
        time.sleep(0.1)
        if stock_code:
            edit_stock_code.type_keys(stock_code)

        self.get_control_with_children(
            main_panel, control_type="Button", class_name="Button", auto_id="3349"
        ).click()
        time.sleep(0.1)

        # 复制刷新后的委托表格，统计待撤委托笔数
        self.clear_clipboard()
        table_control = (
            self.get_control_with_children(
                main_panel, auto_id="1047", control_type="Pane"
            )
            .children()[0]
            .children(class_name="CVirtualGridCtrl")[0]
        )
        table_control.click_input()
        table_control.type_keys("^a")
        time.sleep(0.05)
        table_control.type_keys("^c")
        time.sleep(0.1)
        self.process_captcha_dialog()
        cancelled_count = _count_cancel_rows(
            text2df(self.get_clipboard_data()), params.cancel_type
        )

        cancel_btn = self.get_control_with_children(
            main_panel,
            class_name="Button",
            control_type="Button",
            auto_id=self._BTN_IDS[params.cancel_type],
        )
        # 必须有单才可以撤，没单的话按钮是灰色的，click会报错
        if cancel_btn.is_enabled():
            cancel_btn.click()
        # 等待弹窗出现，软件必须确保已经勾选 撤单不需要确认
        # 没有弹窗就是成功了
        is_op_success = not self.wait_for_pop_dialog(0.4)

        if not is_op_success:
            return self._fail(f"撤单存在确认弹窗: {self.get_pop_dialog_content()}")

        target = stock_code or "全部"
        return self._ok(
            data=OrderCancelResult(
                stock_code=stock_code,
                cancel_type=params.cancel_type,
                cancelled_count=cancelled_count,
            ).model_dump(),
            message=f"撤销{target}的委托成功，共{cancelled_count}笔，耗时{time.time() - start_time:.2f}秒",
        )
