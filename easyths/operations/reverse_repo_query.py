import datetime
import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.utils import df_format_convert, text2df
from easyths.models.operations import PluginMetadata, OperationResult
import pandas as pd

class ReverseRepoQueryOperation(BaseOperation):
    """国债逆回购查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ReverseRepoQueryOperation",
            version="1.0.0",
            description="查询国债逆回购年化利率信息",
            author="noimank",
            operation_name="reverse_repo_query",
            parameters={

            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        try:

            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def parse_table_panels(self, table_controls:list)->list:

        data_list =[]
        for table_item_wrapper in table_controls:
            table_item = table_item_wrapper.children(control_type="Custom")[0].children(control_type="DataItem")[0].children(control_type="Text")
            time_type = table_item[0].window_text()
            type_flag = table_item[1].window_text()
            year_profit = table_item[2].window_text()
            if "GC" in type_flag:
                data_list.append({
                    "市场类型": "上海市场",
                    "时间类型": time_type,
                    "年化利率": year_profit
                })
            else:
                data_list.append({
                    "市场类型": "深圳市场",
                    "时间类型": time_type,
                    "年化利率": year_profit
                })
        return data_list


    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行国债逆回购查询操作"""
        start_time = time.time()

        try:
            self.logger.info(f"执行国债逆回购查询操作")
            main_window = self.get_main_window(wrapper_obj=True)
            # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("国债逆回购")

            is_pop_up = self.wait_for_pop_dialog(5)
            reverse_repo_interest_data = None
            is_op_success = False
            op_message = "查询国债逆回购年化利率失败"

            if is_pop_up:
                pop_dialog_title, pop_control = self.get_pop_dialog()
                if pop_dialog_title == "国债逆回购窗口":
                    inner_panel = pop_control.children(control_type="Pane", class_name="AfxWnd140s")[0]
                    inner_panel2 = inner_panel.children(control_type="Pane", class_name="CefBrowserWindow")[0].children(control_type="Pane", class_name="Chrome_WidgetWin_0")[0]
                    document_panel =self.get_control_with_children(inner_panel2, control_type="Document", auto_id="174504928")
                    # 会有10个元素
                    table_panel = document_panel.children(control_type="Table")
                    #选择对应的选择
                    reverse_repo_interest_data = self.parse_table_panels(table_panel)
                    #输入金额
                    is_op_success = True
                    op_message = "查询国债逆回购年化利率成功"
                    # 成功与否都需要把窗口关闭
                    self.get_control_with_children(pop_control, control_type="Button", auto_id="1008",
                                                   class_name="Button").click()

            # 3. 准备返回数据
            result_data = {
                "reverse_repo_interest": reverse_repo_interest_data,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": is_op_success,
                "message": op_message
            }

            self.logger.info(f"国债逆回购查询完成，耗时{time.time() - start_time}秒")

            return OperationResult(
                success=is_op_success,
                data=result_data
            )

        except Exception as e:
            error_msg = f"国债逆回购查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )
