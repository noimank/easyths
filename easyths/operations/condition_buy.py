
import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class ConditionBuyOperation(BaseOperation):
    """条件买入股票操作 - 同步执行模式"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ConditionBuyOperation",
            version="1.0.0",
            description="条件买入股票操作",
            author="noimank",
            operation_name="condition_buy",
            parameters={
                "stock_code": {
                    "type": "string",
                    "required": True,
                    "description": "股票代码（6位数字）",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "target_price": {
                    "type": "number",
                    "required": True,
                    "description": "目标价格（触发价格）",
                    "minimum": 0.01,
                    "maximum": 10000
                },
                "quantity": {
                    "type": "integer",
                    "required": True,
                    "description": "买入数量（必须是100的倍数）",
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
        """验证条件买入参数"""
        try:
            # 检查必需参数
            required_params = ["stock_code", "target_price", "quantity"]
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            stock_code = params["stock_code"]
            target_price = params["target_price"]
            quantity = params["quantity"]
            expire_days = params.get("expire_days", 30)

            # 验证股票代码
            if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                self.logger.error("股票代码格式错误，必须是6位数字")
                return False

            # 验证目标价格
            if not isinstance(target_price, (int, float)) or target_price <= 0:
                self.logger.error("目标价格必须大于0")
                return False

            # 验证数量
            if not isinstance(quantity, int) or quantity < 100 or quantity % 100 != 0:
                self.logger.error("数量必须是100的倍数且不小于100")
                return False
            # 验证有效期
            if expire_days not in [1, 3, 5, 10, 20, 30]:
                self.logger.error("有效期必须是1,3,5,10,20,30中的任意一个")
                return False
            # 验证价格和数量的合理性
            if target_price * quantity > 10000000:  # 单笔不超过1000万
                self.logger.error("单笔金额过大")
                return False

            self.logger.info("条件买入参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行条件买入操作 - TODO: 待实现"""
        stock_code = params["stock_code"]
        target_price = params["target_price"]
        quantity = params["quantity"]
        expire_days = params.get("expire_days", 30)
        start_time = time.time()

        try:
            self.logger.info(
                f"执行条件买入操作",
                stock_code=stock_code,
                target_price=target_price,
                quantity=quantity
            )

            main_window = self.get_main_window(wrapper_obj=True)
            # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("条件单", "股价条件")
            self.wait_for_pop_dialog(2.5)
            # 用于控制选择策略有效期索引
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
            op_message = f"执行{stock_code}的条件单失败"

            if pop_dialog_title == "ConditionToolBar":
                # 获取主界面
                main_panel = main_window.children(control_type="Pane", class_name="#32770")[0].children(control_type="Pane", class_name="AfxWnd140s")[0]
                inner_panel2 = main_panel.children(control_type="Pane", class_name="CefBrowserWindow")[0].children(
                    control_type="Pane", class_name="Chrome_WidgetWin_0")[0]
                document_panel = self.get_control_with_children(inner_panel2, control_type="Document",
                                                                class_name="Chrome_RenderWidgetHostHWND")

                combox = self.get_control_with_children(document_panel, control_type="ComboBox")
                stock_edit = self.get_control_with_children(combox, control_type="Edit", title_re="代码")
                #设置股票代码
                stock_edit.set_text(stock_code)
                # 设置目标价格
                self.get_control_with_children(document_panel, control_type="Edit").set_text(str(target_price))
                self.sleep(0.2)
                # 下一步
                self.get_control_with_children(document_panel, control_type="Button", title="下一步").click()
                # 等页面重绘渲染
                self.sleep(0.4)
                # 只能根据序号定位
                document_panel.children(control_type="Edit")[2].set_text(str(quantity))
                self.sleep(0.05)
                # 选择全自动委托
                weituo_btn = self.get_control_with_children(document_panel, control_type="RadioButton", title="全自动委托")
                # 模拟交易中全自动委托是灰色的
                if not weituo_btn.is_selected() and weituo_btn.is_enabled():
                    weituo_btn.select()
                    self.sleep(0.6)
                    # 等待弹窗出现，看是否会出现提示成功添加到条件单的窗口，也可以勾选不再提醒
                    inner_pane = self.get_control_with_children(document_panel, control_type="Custom", title="温馨提示")
                    if inner_pane:
                        # 勾选不再提醒
                        self.get_control_with_children(inner_pane, control_type="CheckBox").click()
                        #点击我知道了按钮
                        self.sleep(0.2)
                        self.get_control_with_children(inner_pane, control_type="Button", title="我知道了").click()

                # 策略有效期
                expire_choose = document_panel.children(control_type="Edit", title="请选择")[1]
                expire_choose.click_input()
                # 等待渲染
                self.sleep(0.3)
                expire_list_control = self.get_control_with_children(document_panel, control_type="List")
                expire_list_control.children(control_type="ListItem")[count_map.get(str(expire_days))].invoke()

                self.sleep(0.1)
                expire_list_control.type_keys("{ENTER}")
                self.sleep(0.1)
                self.get_control_with_children(document_panel, control_type="Button", title="提交确认").click()
                # 等待弹窗出现，看是否会出现提示成功添加到条件单的窗口，直接关闭，关不关都无所谓了，反正会被close_pop_dailog函数关闭，这里还省掉sleep呢
                # 关闭可能出现的成功提示弹窗
                # self.sleep(0.2)
                # self.get_pop_dialog()[1].type_keys("{ESC}", pause=0.15)
                is_op_success = True
                op_message = f"执行{stock_code}的条件单成功"

            result_data = {
                "stock_code": stock_code,
                "target_price": target_price,
                "quantity": quantity,
                "operation": "condition_buy",
                "success": is_op_success,
                "message": op_message
            }

            self.logger.info(f"条件买入操作耗时{time.time() - start_time}, 操作结果：", **result_data)
            return OperationResult(
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"条件买入操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
