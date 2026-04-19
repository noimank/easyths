import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult

# 成交策略映射
EXECUTION_STRATEGIES = {
    1: "对手方最优",
    2: "本方最优",
    3: "五档即成剩撤",
    4: "即成剩撤",
    5: "全额成交或撤",
    6: "五档即成剩转限"
}


class MarketBuyOperation(BaseOperation):
    """市价买入股票操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="MarketBuyOperation",
            version="1.0.0",
            description="市价买入股票操作",
            author="noimank",
            operation_name="market_buy",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": True,
                    "description": "股票代码（6位数字）",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "quantity": {
                    "type": "integer",
                    "required": True,
                    "description": "买入数量（股票必须是100的倍数，可转债必须是10的倍数）",
                    "minimum": 10,
                    "multiple_of": 10
                },
                "execution_strategy": {
                    "type": "integer",
                    "required": False,
                    "description": "成交策略：1-对手方最优 2-本方最优 3-五档即成剩撤 4-即成剩撤 5-全额成交或撤 6-五档即成剩转限",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 6
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        try:
            required_params = ["stock_code", "quantity"]
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            stock_code = params["stock_code"]
            quantity = params["quantity"]

            if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                self.logger.error("股票代码格式错误，必须是6位数字")
                return False

            is_convertible_bond = stock_code.startswith(("11", "12"))
            min_qty = 10 if is_convertible_bond else 100
            multiple = 10 if is_convertible_bond else 100
            if not isinstance(quantity, int) or quantity < min_qty or quantity % multiple != 0:
                self.logger.error(f"数量必须是{multiple}的倍数且不小于{min_qty}" + ("（可转债）" if is_convertible_bond else ""))
                return False

            self.logger.info("市价买入参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行市价买入操作 """
        stock_code = params["stock_code"]
        quantity = params["quantity"]
        execution_strategy = params.get("execution_strategy", 3)

        try:
            self.logger.info(
                "执行市价买入操作",
                stock_code=stock_code,
                quantity=quantity,
                execution_strategy=execution_strategy,
            )
            # 按下 F1键
            main_window = self.get_main_window(wrapper_obj=True)
            self.switch_left_menus("市价委托", "买入")
            # 防抖
            self.sleep(0.25)
            # 拿到控制面板
            main_panel = self.get_control_with_children(main_window, class_name="AfxMDIFrame140s", control_type="Pane", auto_id="59648").children(class_name='AfxMDIFrame140s')[0]

            # 清除可能存在的股票代码等待输出
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1032").type_keys("{BACKSPACE 6}", pause=0.02)
            self.sleep(0.2)
            # 输入股票代码
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1032").type_keys(stock_code)

            # 输入数量
            self.get_control_with_children(main_panel, control_type="Edit", auto_id="1034").type_keys(str(quantity))
            self.sleep(0.2)

            # 判断是否支持市价委托
            combo_box = self.get_control_with_children(main_panel, control_type="ComboBox", auto_id="1541")
            combo_box.expand()
            self.sleep(0.2)
            list_box = self.get_control_with_children(combo_box, control_type="List", class_name="ComboLBox")
            # 选择成交策略
            texts = [i[0] for i in  list_box.texts()]
            texts2str = "".join(texts)
            if "不支持市价委托" in texts2str:
                return OperationResult(success=False, message=f"标的：{stock_code}，不支持市价委托")
            # 判断是否支持成交策略
            is_valid_execution_strategy = EXECUTION_STRATEGIES.get(execution_strategy, "未知策略") in texts2str
            waiting_for_select_str = EXECUTION_STRATEGIES.get(execution_strategy) if  is_valid_execution_strategy else EXECUTION_STRATEGIES.get(3)

            for i, text in enumerate(texts):
                if waiting_for_select_str in text:
                    item = list_box.get_item(i)  # 获取第3项
                    item.click_input()
                    break
            # 点击买入按钮
            self.get_control_with_children(main_panel, control_type="Button", auto_id="1006").click()
            self.sleep(0.35)
            pop_dialog_content = self.get_pop_dialog_content()
            # 出现弹窗说明没提交成功
            if pop_dialog_content:
                return OperationResult(success=False, message=f"市价买入操作失败，错误：{pop_dialog_content}")

            msg = f"市价买入操作成功，买入策略{waiting_for_select_str}"
            if not is_valid_execution_strategy:
                msg = f"市价买入操作成功，买入策略在标的{stock_code}情况下不支持，已经使用默认策略：{waiting_for_select_str}提交）"

            return OperationResult(success=True, message=msg, data={"stock_code": stock_code, "quantity": quantity, "msg": msg})

        except Exception as e:
            self.logger.exception("市价买入操作异常", error=str(e))
            return OperationResult(
            success=False,
            message="市价买入操作异常，错误：{}".format(e),
        )



