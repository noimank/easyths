import time
from typing import Any

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import StockQueryParams
from easyths.operations.results import OrderRow
from easyths.utils import df_to_records, text2df


class OrderQueryOperation(BaseOperation[StockQueryParams]):
    """委托订单查询操作"""

    operation_name = "order_query"
    description = "查询股票委托订单信息"
    Params = StockQueryParams
    Result = OrderRow

    def parse_order_row(self, record: dict[str, Any]) -> OrderRow:
        """剪贴板委托记录 → 行模型（显式字段装配，列名差异在此适配）"""
        return OrderRow(
            order_time=record["委托时间"],
            stock_code=record["证券代码"],
            stock_name=record["证券名称"],
            operation=record["操作"],
            remark=record["备注"],
            quantity=record["委托数量"],
            filled_quantity=record["成交数量"],
            price=record["委托价格"],
            avg_fill_price=record["成交均价"],
            cancelled_quantity=record["撤销数量"],
            contract_no=record["合同编号"],
            market=record["交易市场"],
        )

    def execute(self, params: StockQueryParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        self.logger.info("执行委托查询操作", stock_code=stock_code or "全部")

        # 打开撤单界面（F3键），这个界面也显示了委托信息
        main_window = self.get_main_window(wrapper_obj=True)
        main_window.type_keys("{F3}")
        self.sleep(0.1)
        main_window.type_keys("{F5}")
        self.sleep(0.25)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 清空查询框（显示全部委托），指定股票代码则输入过滤
        edit_stock_code = self.get_control_with_children(
            main_panel, control_type="Edit", class_name="Edit", auto_id="3348"
        )
        edit_stock_code.type_keys("{BACKSPACE 6} ")
        if stock_code:
            edit_stock_code.type_keys(stock_code)

        time.sleep(0.1)
        query_btn = self.get_control_with_children(
            main_panel, control_type="Button", class_name="Button", auto_id="3349"
        )
        query_btn.click()
        time.sleep(0.1)

        # 复制表格数据
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
        # 处理触发复制的限制提示框
        self.process_captcha_dialog()

        table_df = text2df(self.get_clipboard_data())

        # 没有弹窗了，说明没有其他意外情况发生
        is_op_success = not self.wait_for_pop_dialog(0.2)
        # 逐行显式装配，缺列会在此明确报错，多余列自然忽略
        orders = [
            self.parse_order_row(record).model_dump()
            for record in df_to_records(table_df)
        ]

        if not is_op_success:
            return self._fail(
                f"委托查询存在未处理弹窗: {self.get_pop_dialog_content()}"
            )

        return self._ok(
            data=orders,
            message=f"委托查询完成，耗时{time.time() - start_time:.2f}秒",
        )
