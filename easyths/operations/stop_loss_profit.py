
import time
from typing import Dict, Any
import re
from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class StopLossProfitOperation(BaseOperation):
    """止盈止损操作 - 同步执行模式"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="StopLossProfitOperation",
            version="1.0.0",
            description="止盈止损操作",
            author="noimank",
            operation_name="stop_loss_profit",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": True,
                    "description": "股票代码（6位数字）",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "stop_loss_percent": {
                    "type": "number",
                    "required": True,
                    "description": "止损百分比（如3表示3%）",
                    "minimum": 0.01,
                    "maximum": 100
                },
                "stop_profit_percent": {
                    "type": "number",
                    "required": True,
                    "description": "止盈百分比（如5表示5%）",
                    "minimum": 0.01,
                    "maximum": 100
                },
                "quantity": {
                    "type": "integer",
                    "required": False,
                    "description": "买入数量（必须是100的倍数）,可以不指定，默认买完所有持仓数量，建议还是传入，受T+1影响，如果不指定，当天就无法设置止盈止损",
                    "minimum": 100,
                    "multiple_of": 100
                },
                "expire_days": {
                    "type": "integer",
                    "required": False,
                    "description": "止盈止损策略有效期，单位为自然日",
                    "default": 30,
                    "enum": [1,3,5,10,20,30]
                }

            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证止盈止损参数"""
        try:
            # 检查必需参数
            required_params = ["stock_code", "stop_loss_percent", "stop_profit_percent"]
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            stock_code = params["stock_code"]
            stop_loss_percent = params["stop_loss_percent"]
            stop_profit_percent = params["stop_profit_percent"]
            # 支持不指定，默认卖完所有
            quantity = params.get("quantity")
            expire_days = params.get("expire_days", 30)

            # 验证股票代码
            if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                self.logger.error("股票代码格式错误，必须是6位数字")
                return False

            # 验证止损百分比
            if not isinstance(stop_loss_percent, (int, float)) or stop_loss_percent <= 0 or stop_loss_percent > 100:
                self.logger.error("止损百分比必须在0-100之间")
                return False

            # 验证止盈百分比
            if not isinstance(stop_profit_percent, (int, float)) or stop_profit_percent <= 0 or stop_profit_percent > 100:
                self.logger.error("止盈百分比必须在0-100之间")
                return False


            # 验证有效期
            if expire_days not in [1,3,5,10,20,30]:
                self.logger.error("有效期必须是1,3,5,10,20,30中的任意一个")
                return False

            # 验证数量
            if quantity is not None:
                if not isinstance(quantity, int) or quantity < 100 or quantity % 100 != 0:
                    self.logger.error("数量必须是100的倍数且不小于100")
                    return False

            self.logger.info("止盈止损参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False


    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行止盈止损操作"""
        stock_code = params["stock_code"]
        stop_loss_percent = params["stop_loss_percent"]
        stop_profit_percent = params["stop_profit_percent"]
        quantity = params.get("quantity")
        expire_days = params.get("expire_days", 30)

        start_time = time.time()

        try:
            self.logger.info(
                f"执行止盈止损操作",
                stock_code=stock_code,
                stop_loss_percent=stop_loss_percent,
                stop_profit_percent=stop_profit_percent
            )

            main_window = self.get_main_window(wrapper_obj=True)
            # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("条件单", "止盈止损")
            self.wait_for_pop_dialog(2.51)

            #用于控制选择策略有效期索引
            count_map = {
                "1": 0,
                "3": 1,
                "5": 2,
                "10": 3,
                "20": 4,
                "30": 5
            }

            pop_dialog_title, pop_toolbar_control = self.get_pop_dialog()
            is_op_success = False
            op_message = f"执行{stock_code}的止盈止损单失败"

            if pop_dialog_title == "ConditionToolBar":
                # 获取主界面
                main_panel = main_window.children(control_type="Pane", class_name="#32770")[0].children(control_type="Pane", class_name="AfxWnd140s")[0]
                inner_panel2 = main_panel.children(control_type="Pane", class_name="CefBrowserWindow")[0].children(
                    control_type="Pane", class_name="Chrome_WidgetWin_0")[0]
                document_panel = self.get_control_with_children(inner_panel2, control_type="Document",
                                                                class_name="Chrome_RenderWidgetHostHWND")
                # 设置股票代码
                # stock_edit.set_text(stock_code),不支持输入完整的代码，需要特殊处理
                document_panel.children(control_type="Edit")[0].set_text(stock_code[:5])
                self.sleep(0.3)
                has_order = False
                try:
                    # 获取筛选出来的股票持仓
                    stock_list_controls = document_panel.children(control_type="List")[0].children()
                    for stock_cc in stock_list_controls:
                        iitem = stock_cc.children(control_type="Text")[0]
                        item_text = iitem.window_text()
                        if stock_code in item_text:
                            iitem.click_input()
                            has_order = True
                            break
                except IndexError as e:
                    self.logger.warn("没有相应的股票持仓记录，无法设置止盈止损", error=str(e))

                # 处理没有对应持仓股票的情况，因为没有就对应持仓就不能设置止盈止损
                if not has_order:
                    is_op_success = False
                    op_message = f"执行{stock_code}的止盈止损单失败，不支持该品种的标的,请检查是否持仓该股票"
                    # 有些奇怪必须指定pause才能生效
                    main_panel.type_keys("{ESC}", pause=0.15)

                else:
                    # 盈利填写
                    document_panel.children(control_type="Edit")[4].set_text(str(stop_profit_percent))
                    # 亏损填写
                    self.sleep(0.05)
                    document_panel.children(control_type="Edit")[6].set_text(str(stop_loss_percent))
                    self.sleep(0.1)

                    # 下一步
                    self.get_control_with_children(document_panel, control_type="Button", title="下一步").click()
                    # 画面渲染需要时间
                    self.sleep(0.3)

                    #填写委托数量
                    if quantity is None:
                        # 尝试自动获取可用的数量
                        quantity = self.get_control_with_children(document_panel, control_type="Text", title_re="可卖").window_text()
                        quantity = re.search(r'\d+', quantity).group()

                    document_panel.children(control_type="Edit")[4].set_text(str(quantity))

                    # 处理触发类型
                    # 选择全自动委托
                    weituo_btn = self.get_control_with_children(document_panel, control_type="RadioButton",
                                                                title="全自动委托")
                    # 模拟交易中全自动委托是灰色的
                    if not weituo_btn.is_selected() and weituo_btn.is_enabled():
                        weituo_btn.select()
                        self.sleep(0.6)
                        # 等待弹窗出现，看是否会出现提示成功添加到条件单的窗口，也可以勾选不再提醒
                        inner_pane = self.get_control_with_children(document_panel, control_type="Custom",
                                                                    title="温馨提示")
                        if inner_pane:
                            # 勾选不再提醒
                            self.get_control_with_children(inner_pane, control_type="CheckBox").click()
                            # 点击我知道了按钮
                            self.sleep(0.2)
                            self.get_control_with_children(inner_pane, control_type="Button", title="我知道了").click()

                    # 策略有效期选择
                    expire_choose = document_panel.children(control_type="Edit", title="请选择")[1]
                    expire_choose.click_input()
                    # 等待渲染
                    self.sleep(0.3)
                    expire_list_control = self.get_control_with_children(document_panel, control_type="List")
                    expire_list_control.children(control_type="ListItem")[count_map.get(str(expire_days))].invoke()

                    self.sleep(0.1)
                    expire_list_control.type_keys("{ENTER}")
                    self.sleep(0.2)
                    # 提交确认
                    self.get_control_with_children(document_panel, control_type="Button", title="提交确认").click()
                    # 关闭可能出现的成功提示弹窗
                    # self.sleep(0.2)
                    # self.get_pop_dialog()[1].type_keys("{ESC}", pause=0.15)

                    is_op_success = True
                    op_message = f"执行{stock_code}的止盈止损单成功"

            result_data = {
                "stock_code": stock_code,
                "stop_loss_percent": stop_loss_percent,
                "stop_profit_percent": stop_profit_percent,
                "operation": "stop_loss_profit",
                "success": is_op_success,
                "message": op_message
            }

            self.logger.info(f"止盈止损操作耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"止盈止损操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
