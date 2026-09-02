import time
from typing import Any

from easyths.core import BaseOperation
from easyths.models.operations import EmptyParams, OperationResult
from easyths.operations.results import HoldingRow
from easyths.utils import df_to_records, text2df


class HoldingQueryOperation(BaseOperation[EmptyParams]):
    """持仓查询操作"""

    operation_name = "holding_query"
    description = "查询股票持仓信息"
    Params = EmptyParams
    Result = HoldingRow

    def parse_holding_row(self, record: dict[str, Any]) -> HoldingRow:
        """剪贴板持仓记录 → 行模型（显式字段装配，列名差异在此适配）"""
        return HoldingRow(
            stock_code=record["证券代码"],
            stock_name=record["证券名称"],
            # 列名差异：实盘为「持仓数量/可用数量」，模拟账户为「股票余额/可用余额」（语义相同）
            quantity=record.get("持仓数量") or record.get("股票余额"),
            available_quantity=record.get("可用数量") or record.get("可用余额"),
            frozen_quantity=record["冻结数量"],
            # 列名差异：实盘为「参考成本价」，模拟账户为「成本价」
            cost_price=record.get("参考成本价") or record.get("成本价"),
            # 列名差异：实盘为「当前价」，模拟账户为「市价」
            current_price=record.get("当前价") or record.get("市价"),
            # 列名差异：实盘为「浮动盈亏」，模拟账户为「盈亏」
            floating_profit=record.get("浮动盈亏") or record.get("盈亏"),
            profit_ratio=record.get("盈亏比例(%)") or record.get("盈亏比(%)"),
            # 有时直接打开下单软件的情况下没有「当日盈亏」和「当日盈亏比(%)」列，默认填充为 null
            daily_profit=record.get("当日盈亏"),
            daily_profit_ratio=record.get("当日盈亏比(%)"),
            # 列名差异：实盘为「最新市值」，模拟账户为「市值」
            market_value=record.get("最新市值") or record.get("市值"),
            position_ratio=record["仓位占比(%)"],
            daily_bought=record["当日买入"],
            daily_sold=record["当日卖出"],
            market=record["交易市场"],
        )

    def execute(self, params: EmptyParams) -> OperationResult:
        start_time = time.time()
        self.logger.info("执行持仓查询操作")
        # 切换到持仓菜单并刷新数据
        self.switch_left_menus("查询[F4]", "资金股票")
        self.get_main_window(wrapper_obj=True).type_keys("{F5}")
        # 等待页面加载完成，这个页面还是需要实时的
        self.clear_clipboard()
        self.sleep(0.3)
        main_window_wrapper = self.get_main_window(wrapper_obj=True)
        main_panel = self.get_control_with_children(
            main_window_wrapper,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        HexinScrollWnd = self.get_control_with_children(
            main_panel, title="HexinScrollWnd", auto_id="1047"
        )
        HexinScrollWnd2 = self.get_control_with_children(
            HexinScrollWnd, auto_id="200", class_name="AfxWnd140s"
        )

        # 获取表格控件并复制
        table_panel = self.get_control_with_children(
            HexinScrollWnd2, title="Custom1", class_name="CVirtualGridCtrl"
        )
        table_panel.click_input()
        table_panel.type_keys("^a")
        time.sleep(0.05)
        table_panel.type_keys("^c")
        time.sleep(0.2)
        # 处理可能触发复制的限制提示框
        self.process_captcha_dialog()

        table_df = text2df(self.get_clipboard_data())

        # 没有弹窗了，说明没有其他意外情况发生
        is_op_success = not self.is_exist_pop_dialog()
        # 逐行显式装配，缺列会在此明确报错，多余列（操作/Unnamed）自然忽略
        holdings = [
            self.parse_holding_row(record).model_dump()
            for record in df_to_records(table_df)
        ]

        if not is_op_success:
            return self._fail(
                f"持仓查询存在未处理弹窗: {self.get_pop_dialog_content()}"
            )

        return self._ok(
            data=holdings,
            message=f"持仓查询完成，耗时{time.time() - start_time:.2f}秒",
        )
