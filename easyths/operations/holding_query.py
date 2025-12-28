import datetime
import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.utils import df_format_convert,text2df
from easyths.models.operations import PluginMetadata, OperationResult

class HoldingQueryOperation(BaseOperation):
    """持仓查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="HoldingQueryOperation",
            version="1.0.0",
            description="查询股票持仓信息",
            author="noimank",
            operation_name="holding_query",
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
            return_type = params.get("return_type")
            if return_type not in ["str", "json", "dict","df", "markdown"]:
                self.logger.error("参数return_type无效，有效值为：str、json、dict、df、markdown")
                return False
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行持仓查询操作"""
        start_time = time.time()
        return_type = params.get("return_type")
        try:
            self.logger.info(f"执行持仓查询操作。")
            # 切换到持仓菜单
            self.switch_left_menus("查询[F4]", "资金股票")
            # 刷新数据
            self.get_main_window(wrapper_obj=True).type_keys("{F5}")
            # 等待页面加载完成，这个页面还是需要实时的
            self.clear_clipboard()
            self.sleep(0.3)
            main_window_wrapper = self.get_main_window(wrapper_obj=True)
            main_panel = main_window_wrapper.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]

            HexinScrollWnd = self.get_control_with_children(main_panel, title='HexinScrollWnd', auto_id="1047")

            HexinScrollWnd2 = self.get_control_with_children(HexinScrollWnd, auto_id="200", class_name="AfxWnd140s")

            # 获取表格控件
            table_panel = self.get_control_with_children(HexinScrollWnd2, title="Custom1", class_name="CVirtualGridCtrl")
            # 鼠标左键点击
            table_panel.click_input()

            # 按下 Ctrl+A Ctrl+ C  触发复制
            table_panel.type_keys("^a")
            time.sleep(0.05)
            table_panel.type_keys("^c")
            time.sleep(0.2)
            # 处理可能触发复制的限制提示框
            self.process_captcha_dialog()

            # 获取剪贴板数据
            table_data = self.get_clipboard_data()
            table_data = text2df(table_data)
            if not table_data.empty:
                # 丢弃多余列
                table_data = table_data.drop(columns=["操作", "Unnamed: 19"], errors="ignore")

            is_op_success = not self.is_exist_pop_dialog()  #没有弹窗了，说明没有其他意外情况发生
            if is_op_success:
                # 获取表格数据
                table_data = df_format_convert(table_data, return_type)

            # 准备返回数据
            result_data = {
                "holdings": table_data,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": is_op_success
            }

            self.logger.info(f"持仓查询完成，耗时{time.time() - start_time}秒",
                           holding=table_data)

            return OperationResult(
                success=is_op_success,
                data=result_data
            )

        except Exception as e:
            error_msg = f"持仓查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )