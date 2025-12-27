import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class ReverseRepoBuyOperation(BaseOperation):
    """国债逆回购操作"""


    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ReverseRepoOperation",
            version="1.0.0",
            description="国债逆回购操作,购买后可用在订单查询中查看购买情况",
            author="noimank",
            operation_name="reverse_repo_buy",
            parameters={
                "market": {
                    "type": "string",
                    "required": True,
                    "description": "交易市场",
                    "enum": ["上海", "深圳"],
                },
                "time_range": {
                    "type": "string",
                    "required": True,
                    "description": "回购期限",
                    "enum": ["1天期", "2天期", "3天期", "4天期", "7天期"],
                },
                "amount": {
                    "type": "integer",
                    "required": True,
                    "description": "出借金额（必须是1000的倍数）",
                    "minimum": 1000,
                    "multiple_of": 1000
                },
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证国债逆回购参数"""
        try:
            # 检查必需参数
            required_params = ["market", "time_range", "amount"]
            for param in required_params:
                if param not in params:
                    self.logger.error(f"缺少必需参数: {param}")
                    return False

            market = params["market"]
            time_range = params["time_range"]
            amount = params["amount"]

            # 验证市场
            if market not in ["上海", "深圳"]:
                self.logger.error("市场参数无效，有效值为：上海、深圳")
                return False

            # 验证期限
            if time_range not in ["1天期", "2天期", "3天期", "4天期", "7天期"]:
                self.logger.error("期限参数无效，有效值为：1天期、2天期、3天期、4天期、7天期")
                return False

            # 验证出借金额
            if not isinstance(amount, int) or amount < 1000 or amount % 1000 != 0:
                self.logger.error("出借金额必须是1000的倍数且不小于1000")
                return False

            self.logger.info("国债逆回购参数验证通过")
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def select_target_area(self, table_contrls, key_word):
        """
        根据关键字比如 GC001，这种特定的标识
        返回目标控件
        """
        for table_item in table_contrls:
            cc = table_item.children(control_type="Custom")[0].children(control_type="DataItem")[0].children(control_type="Text")
            content = "".join([c.window_text() for c in cc])
            if key_word in content:
                table_item.click_input()
                self.sleep(0.05)
                return table_item
        return None



    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行国债逆回购操作 - 占位实现"""
        market = params["market"]
        time_range = params["time_range"]
        amount = params["amount"]
        start_time = time.time()

        try:
            self.logger.info(
                f"执行国债逆回购操作",
                market=market,
                time_range=time_range,
                amount=amount
            )
            main_window = self.get_main_window(wrapper_obj=True)
            #先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("国债逆回购")

            # 1. 根据 market 和 time_range 获取对应的国债逆回购代码
            code_map = {
                "1天期": "001",
                "2天期": "002",
                "3天期": "003",
                "4天期": "004",
                "7天期": "007"
            }

            target_keyword =  "GC"+code_map.get(time_range)  if market == "上海" else  "R-"+code_map.get(time_range)
            # 5. 确认下单
            is_pop_up = self.wait_for_pop_dialog(5)
            is_op_success = False
            op_message = "国债逆回购操作成功"
            if is_pop_up:
                pop_dialog_title, pop_control = self.get_pop_dialog()
                if pop_dialog_title == "国债逆回购窗口":
                    inner_panel = pop_control.children(control_type="Pane", class_name="AfxWnd140s")[0]
                    inner_panel2 = inner_panel.children(control_type="Pane", class_name="CefBrowserWindow")[0].children(control_type="Pane", class_name="Chrome_WidgetWin_0")[0]
                    document_panel =self.get_control_with_children(inner_panel2, control_type="Document", auto_id="174504928")
                    # 会有10个元素
                    table_panel = document_panel.children(control_type="Table")
                    #选择对应的选择
                    select_target_control = self.select_target_area(table_panel, target_keyword)
                    #输入金额
                    self.get_control_with_children(document_panel, control_type="Edit", auto_id="shuru").set_text(str(amount))
                    self.sleep(0.1)
                    # 点击出借，这个是文本渲染的，如果出借金额不足，马上会变成灰色，此时无法触发出借并关闭窗口的实践
                    chujie_btn = self.get_control_with_children(document_panel, control_type="Text", title="出借")
                    # 模拟物理点击
                    chujie_btn.click_input()
                    self.sleep(0.1)
                    ask_pop_dialog = self.get_control_with_children(document_panel, control_type="Text", title_re="您是否确认以上")
                    self.sleep(0.1)
                    # 是否出现询问窗口
                    if ask_pop_dialog is None:
                        is_op_success = False
                        # 定位元素属性缺乏，只能顺序取，可能不保证是对应的元素,实测其实也还行，可能后面遇到同花顺界面重构会要修改
                        available_amount = document_panel.children(control_type="Text")[10]
                        available_amount_text = available_amount.window_text()
                        op_message = f"国债逆回购操作失败，计划出借金额：{amount} 元， 可用金额：{available_amount_text} 元"

                    else:
                        # 点击确认
                        op_message = f"国债逆回购操作成功， 成功出借:{amount} 元， 年化利率为：{self.get_control_with_children(document_panel,control_type='Text', title_re='%').window_text().replace('\xa0','')}"
                        self.get_control_with_children(document_panel, control_type="Text", title="确定").click_input()
                        is_op_success = True

                    # 成功与否都需要把窗口关闭
                    self.get_control_with_children(pop_control, control_type="Button", auto_id="1008",
                                                   class_name="Button").click()
            # 占位实现
            result_data = {
                "market": market,
                "time_range": time_range,
                "amount": amount,
                "success": is_op_success,
                "message": op_message
            }

            self.logger.info(f"国债逆回购操作完成，耗时{time.time() - start_time}s, 操作结果：", **result_data)
            return OperationResult(
                success=is_op_success,
                data=result_data,
            )

        except Exception as e:
            error_msg = f"国债逆回购操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(success=False, error=error_msg)
