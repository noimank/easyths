import time
from typing import Dict, Any

import pandas as pd

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult
from easyths.utils import df_format_convert

class ConditionOrderQueryOperation(BaseOperation):
    """条件单查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="ConditionOrderQueryOperation",
            version="1.0.0",
            description="查询条件单信息",
            author="noimank",
            operation_name="condition_order_query",
            parameters={
                "return_type": {
                    "type": "string",
                    "required": False,
                    "description": "结果返回类型",
                    "enum": ["str", "json", "dict", "df", "markdown"],
                    "default": "json"
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        try:
            return_type = params.get("return_type", "json")
            if return_type not in ["str", "json", "dict", "df", "markdown"]:
                self.logger.error("参数return_type无效，有效值为：str、json、dict、df、markdown")
                return False
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        start_time = time.time()
        return_type = params.get("return_type", "json")

        try:
            self.logger.info("执行条件单查询操作")
            main_window = self.get_main_window(wrapper_obj=True)
            # 先跳到其他页面，要是停留在国债逆回购的话，再次点击可能没反应
            main_window.type_keys("{F3}")
            self.sleep(0.2)
            self.switch_left_menus("条件单", "条件单监控")
            self.sleep(0.1)
            main_window.type_keys("{F5}")
            self.sleep(0.3)
            # 有两个
            panel_AfxWnd140s_2 = self.get_control_with_children(main_window, control_type="Pane", auto_id="59648").children(class_name="AfxMDIFrame140s")[0]
            panel_AfxWnd140s = self.get_control_with_children(panel_AfxWnd140s_2, auto_id="2393", control_type="Pane", class_name="AfxWnd140s")
            cefbrowserwindow = self.get_control_with_children(panel_AfxWnd140s, control_type="Pane", class_name="CefBrowserWindow")
            chrome_widget = self.get_control_with_children(cefbrowserwindow, control_type="Pane", class_name="Chrome_WidgetWin_0")

            chrome_render_win  = self.get_control_with_children(chrome_widget, control_type="Document", class_name="Chrome_RenderWidgetHostHWND")

            # 要选择  未触发
            type_tab_control = self.get_control_with_children(chrome_render_win, control_type="Tab")
            wcf_control = self.get_control_with_children(type_tab_control, control_type="TabItem", title="未触发")
            wcf_control.click_input()
            self.sleep(0.3)

            # 获取未触发的显示面板
            custom_pane = self.get_control_with_children(chrome_render_win, title="未触发", control_type="Custom", auto_id="pane-not_triggered")
            # 准备解析表格数据
            table_raw_controls = custom_pane.children(control_type="Table")

            # 第一个是表头
            table_header = table_raw_controls[0].children(control_type="Custom")[0]
            header = [item.window_text() for item in table_header.children(control_type="Header")]
            # 第二个是数据表格
            data_tables = table_raw_controls[1].children()

            data = []
            # 解析表格
            for table_row in data_tables:
                data.append( [table_cell.window_text().replace('\xa0', ' ') for table_cell in table_row.children(control_type="DataItem")])

            df = pd.DataFrame(data, columns=header)
            # 丢弃第一列
            df = df.drop(df.columns[0], axis=1)
            # print(df)

            df_format = df_format_convert(df, return_type)


            result_data = {
                "condition_orders": df_format,
                "message": f"条件单查询成功，共获取到{len(df)}条数据",
                "timestamp": time.time(),
                "success": True
            }

            self.logger.info(f"条件单查询操作耗时{time.time() - start_time}秒")
            return OperationResult(
                success=True,
                data=result_data
            )

        except Exception as e:
            error_msg = f"条件单查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )
