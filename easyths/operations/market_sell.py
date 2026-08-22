from easyths.core import BaseOperation
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import MarketOrderParams
from easyths.operations.results import MarketOrderResult
from easyths.utils.execution_strategy import (
    DEFAULT_STRATEGY,
    EXECUTION_STRATEGIES,
    resolve_strategy,
)


class MarketSellOperation(BaseOperation[MarketOrderParams]):
    """市价卖出股票操作"""

    operation_name = "market_sell"
    description = "市价卖出股票"
    Params = MarketOrderParams
    Result = MarketOrderResult

    def execute(self, params: MarketOrderParams) -> OperationResult:
        stock_code = params.stock_code

        self.logger.info(
            "执行市价卖出操作",
            stock_code=stock_code,
            quantity=params.quantity,
            execution_strategy=params.execution_strategy,
        )

        main_window = self.get_main_window(wrapper_obj=True)
        self.switch_left_menus("市价委托", "卖出")
        # 防抖
        self.sleep(0.25)
        main_panel = self.get_control_with_children(
            main_window,
            class_name="AfxMDIFrame140s",
            control_type="Pane",
            auto_id="59648",
        ).children(class_name="AfxMDIFrame140s")[0]

        # 清除可能残留的股票代码再输入
        self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1032"
        ).type_keys("{BACKSPACE 6}", pause=0.02)
        self.sleep(0.2)
        self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1032"
        ).type_keys(stock_code)

        # 输入数量
        self.get_control_with_children(
            main_panel, control_type="Edit", auto_id="1034"
        ).type_keys(str(params.quantity))
        self.sleep(0.2)

        # 判断是否支持市价委托并选择成交策略
        # （客户端策略数量/顺序不定，必须按名称内容匹配，不能按编号定位）
        combo_box = self.get_control_with_children(
            main_panel, control_type="ComboBox", auto_id="1541"
        )
        combo_box.expand()
        self.sleep(0.2)
        list_box = self.get_control_with_children(
            combo_box, control_type="List", class_name="ComboLBox"
        )
        texts = [i[0] for i in list_box.texts()]
        if "不支持市价委托" in "".join(texts):
            return self._fail(
                f"标的：{stock_code}，不支持市价委托", ErrorCode.CLIENT_REJECTED
            )

        resolved = resolve_strategy(texts, params.execution_strategy)
        if resolved is None:
            return self._fail(
                f"标的：{stock_code}，不含可用市价成交策略"
                f"（请求策略 {EXECUTION_STRATEGIES.get(params.execution_strategy, '未知')} "
                f"与兜底策略 {EXECUTION_STRATEGIES[DEFAULT_STRATEGY]} 均不支持）",
                ErrorCode.CLIENT_REJECTED,
            )
        selected_strategy, selected_str, selected_index = resolved
        list_box.get_item(selected_index).click_input()
        # 点击委托按钮
        self.get_control_with_children(
            main_panel, control_type="Button", auto_id="1006"
        ).click()
        self.sleep(0.35)
        # 出现弹窗说明没提交成功
        pop_dialog_content = self.get_pop_dialog_content()
        if pop_dialog_content:
            return self._fail(
                f"市价卖出操作失败，错误：{pop_dialog_content}",
                ErrorCode.CLIENT_REJECTED,
            )

        if selected_strategy != params.execution_strategy:
            message = (
                f"市价卖出操作成功，请求策略"
                f"（{EXECUTION_STRATEGIES[params.execution_strategy]}）在标的"
                f"{stock_code}下不支持，已使用兜底策略：{selected_str}"
            )
        else:
            message = f"市价卖出操作成功，成交策略：{selected_str}"

        return self._ok(
            data=MarketOrderResult(
                stock_code=stock_code, quantity=params.quantity, strategy=selected_str
            ).model_dump(),
            message=message,
        )
