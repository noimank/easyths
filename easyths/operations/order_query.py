import datetime
import time
from typing import Dict, Any
from easyths.utils import df_format_convert,text2df

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult

class OrderQueryOperation(BaseOperation):
    """委托订单查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="OrderQueryOperation",
            version="1.0.0",
            description="查询股票委托订单信息",
            author="noimank",
            operation_name="order_query",
            parameters={
                "return_type": {
                    "type": "string",
                    "required": True,
                    "description": "",
                    "enum": ["str", "markdown", "df", "json", "dict"],
                },
                "stock_code": {
                    "type": "string",
                    "required": False,
                    "description": "股票代码（6位数字），不指定则查询所有股票的委托",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                }
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        try:
            stock_code = params.get("stock_code")
            # 验证股票代码格式（如果提供了的话）
            if stock_code is not None:
                if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                    self.logger.error("股票代码格式错误，必须是6位数字")
                    return False

            # 验证返回类型
            return_type = params.get("return_type")
            if return_type not in ["str", "json", "dict", "df", "markdown"]:
                self.logger.error("参数return_type无效，有效值为：str、json、dict、df、markdown")
                return False

            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行委托订单查询操作"""
        start_time = time.time()
        stock_code = params.get("stock_code")
        return_type = params.get("return_type", "str")

        try:
            self.logger.info(f"执行委托查询操作，股票代码: {stock_code or '全部'}")

            # 1. 打开撤单界面（F3键），这个界面也显示了委托信息
            main_window = self.get_main_window(wrapper_obj=True)
            main_window.type_keys("{F3}")
            self.sleep(0.1)
            main_window.type_keys("{F5}")
            self.sleep(0.25)
            main_panel = main_window.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]


            edit_stock_code = self.get_control_with_children(main_panel, control_type="Edit", class_name="Edit",
                                                             auto_id="3348")
            # 如果没有指定股票代码，清空查询框以显示所有委托
            edit_stock_code.type_keys('{BACKSPACE 6} ')
            # 2. 如果指定了股票代码，输入股票代码进行查询
            if stock_code:
                edit_stock_code.type_keys(str(stock_code))

            time.sleep(0.1)
            query_btn = self.get_control_with_children(main_panel, control_type="Button", class_name="Button",
                                                       auto_id="3349")
            query_btn.click()
            time.sleep(0.1)

            # 3. 根据查询类型获取委托数据
            self.clear_clipboard()
            # 获取表格控件
            table_control = self.get_control_with_children(main_panel,auto_id="1047", control_type="Pane").children()[0].children(class_name="CVirtualGridCtrl")[0]
            # 鼠标左键点击
            table_control.click_input()

            # 按下 Ctrl+A Ctrl+ C  触发复制
            table_control.type_keys("^a")
            time.sleep(0.05)
            table_control.type_keys("^c")
            time.sleep(0.1)

            # 处理触发复制的限制提示框
            self.process_captcha_dialog()

            # 获取剪贴板数据
            table_data = self.get_clipboard_data()
            table_data = text2df(table_data)
            # 丢弃多余列
            table_data = table_data.drop(columns=["Unnamed: 12"], errors="ignore")

            is_op_success = not self.wait_for_pop_dialog(0.2) # 没有弹窗了，说明没有其他意外情况发生
            if is_op_success:
                # 获取表格数据
                table_data = df_format_convert(table_data, return_type)

            # 4. 准备返回数据
            result_data = {
                "orders": f"没有对应的委托订单" if len(table_data) ==0 else table_data,
                "stock_code": stock_code if stock_code else "全部查询",
                "timestamp": datetime.datetime.now().isoformat(),
                "success": is_op_success
            }

            self.logger.info(f"委托查询完成，耗时{time.time() - start_time}秒",
                           stock_code=stock_code or "全部")

            return OperationResult(
                success=is_op_success,
                data=result_data
            )

        except Exception as e:
            error_msg = f"委托查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )