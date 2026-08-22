import time

from easyths.core import BaseOperation
from easyths.models.operations import EmptyParams, OperationResult
from easyths.operations.results import FundsResult


class FundsQueryOperation(BaseOperation[EmptyParams]):
    """资金查询操作"""

    operation_name = "funds_query"
    description = "查询账户资金信息"
    Params = EmptyParams
    Result = FundsResult

    def execute(self, params: EmptyParams) -> OperationResult:
        start_time = time.time()
        self.logger.info("执行资金查询操作")
        # F4 切到资金股票页，不采用特定子菜单定位
        # https://github.com/noimank/easyths/issues/4
        main_window_wrapper = self.get_main_window(wrapper_obj=True)
        main_window_wrapper.type_keys("{F4}")
        self.sleep(0.2)
        main_window_wrapper.type_keys("{F5}")
        # 防抖
        self.sleep(0.3)
        main_panel = self.get_control_with_children(
            main_window_wrapper,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]
        text_controls = main_panel.children(control_type="Text", class_name="Static")

        # 资金字段控件 auto_id → Result 字段名映射
        field_map = {
            "1012": "balance",
            "1013": "frozen_amount",
            "1014": "market_value",
            "1015": "total_assets",
            "1016": "available_amount",
            "1017": "withdrawable_amount",
            "1027": "holding_profit",
        }
        raw_funds = {}
        for control in text_controls:
            auto_id = control.element_info.automation_id
            if auto_id in field_map:
                raw_funds[field_map[auto_id]] = control.window_text()

        return self._ok(
            data=FundsResult.model_validate(raw_funds).model_dump(),
            message=f"资金查询完成，耗时{time.time() - start_time:.2f}秒",
        )
