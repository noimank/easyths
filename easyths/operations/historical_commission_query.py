import time
from typing import Any

from easyths.core import BaseOperation
from easyths.models.operations import OperationResult
from easyths.operations.params import HistoricalQueryParams
from easyths.operations.results import HistoricalOrderRow
from easyths.utils import df_to_records, text2df


class HistoricalCommissionQueryOperation(BaseOperation[HistoricalQueryParams]):
    """历史委托查询操作"""

    operation_name = "historical_commission_query"
    description = "查询股票历史委托订单信息"
    Params = HistoricalQueryParams
    Result = HistoricalOrderRow

    def parse_historical_row(self, record: dict[str, Any]) -> HistoricalOrderRow:
        """剪贴板历史委托记录 → 行模型（显式字段装配，列名差异在此适配）"""
        return HistoricalOrderRow(
            order_date=record["委托日期"],
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

    def execute(self, params: HistoricalQueryParams) -> OperationResult:
        start_time = time.time()
        stock_code = params.stock_code
        self.logger.info("执行历史委托查询操作", stock_code=stock_code or "全部")

        self.switch_left_menus("查询[F4]", "历史委托")
        main_window = self.get_main_window(wrapper_obj=True)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 时间范围单选按钮 auto_id 映射
        control_map = {
            "当日": "5315",
            "近一周": "5308",
            "近一月": "5309",
            "近三月": "5310",
            "近一年": "5311",
        }
        self.get_control_with_children(
            main_panel,
            auto_id=control_map[params.time_range],
            control_type="Button",
            class_name="Button",
        ).click()

        # 指定股票代码则输入过滤，否则点击查询按钮刷新
        if stock_code:
            combox = self.get_control_with_children(
                main_panel,
                control_type="ComboBox",
                class_name="ComboBox",
                auto_id="1337",
            )
            edit_stock_code = self.get_control_with_children(
                combox, auto_id="1001", control_type="Edit", class_name="Edit"
            )
            edit_stock_code.type_keys("{BACKSPACE 7}")
            time.sleep(0.05)
            edit_stock_code.type_keys(stock_code)
            time.sleep(0.1)
        else:
            self.get_control_with_children(
                main_panel, class_name="Button", auto_id="2449"
            ).click()

        time.sleep(0.2)
        # 复制表格数据
        table_panel = (
            main_panel.children(control_type="Pane", title="HexinScrollWnd")[0]
            .children(control_type="Pane", title="HexinScrollWnd2")[0]
            .children(class_name="CVirtualGridCtrl")[0]
        )
        table_panel.click_input()
        time.sleep(0.01)
        table_panel.type_keys("^a")
        time.sleep(0.02)
        table_panel.type_keys("^c")
        time.sleep(0.15)
        # 处理触发复制的限制提示框
        self.process_captcha_dialog()

        table_df = text2df(self.get_clipboard_data())

        # 没有弹窗了，说明没有其他意外情况发生
        is_op_success = not self.is_exist_pop_dialog()
        # 逐行显式装配，缺列会在此明确报错，多余列自然忽略
        historical_orders = [
            self.parse_historical_row(record).model_dump()
            for record in df_to_records(table_df)
        ]

        if not is_op_success:
            return self._fail(
                f"历史委托查询存在未处理弹窗: {self.get_pop_dialog_content()}"
            )

        return self._ok(
            data=historical_orders,
            message=f"历史委托查询完成，耗时{time.time() - start_time:.2f}秒",
        )
