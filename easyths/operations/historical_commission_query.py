import datetime
import time
from typing import Dict, Any
from easyths.utils import df_format_convert, text2df

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult

class HistoricalCommissionQueryOperation(BaseOperation):
    """历史委托查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="HistoricalCommissionQueryOperation",
            version="1.0.0",
            description="查询股票历史委托订单信息",
            author="noimank",
            operation_name="historical_commission_query",
            parameters={
                "return_type": {
                    "type": "string",
                    "required": True,
                    "description": "返回数据格式",
                    "enum": ["str", "markdown", "df", "json", "dict"],
                },
                "stock_code": {
                    "type": "string",
                    "required": False,
                    "description": "股票代码（6位数字），不指定则查询所有股票的历史委托",
                    "min_length": 6,
                    "max_length": 6,
                    "pattern": "^[0-9]{6}$"
                },
                "time_range": {
                    "type": "string",
                    "required": False,
                    "description": "查询时间范围，不指定则默认为当日",
                    "default": "当日",
                    "enum": ["当日", "近一周", "近一月", "近三月", "近一年"],
                }

            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        try:
            stock_code = params.get("stock_code")
            time_range = params.get("time_range", "当日")

            # 验证股票代码格式（如果提供了的话）
            if stock_code is not None:
                if not isinstance(stock_code, str) or len(stock_code) != 6 or not stock_code.isdigit():
                    self.logger.error("股票代码格式错误，必须是6位数字")
                    return False

            # 验证日期格式（如果提供了的话）
            if time_range not in ["当日", "近一周", "近一月", "近三月", "近一年"]:
                self.logger.error("时间范围参数无效，有效值为：当日、近一周、近一月、近三月、近一年")
                return False

            # 验证返回类型
            return_type = params.get("return_type", "str")
            if return_type not in ["str", "json", "dict", "df", "markdown"]:
                self.logger.error("参数return_type无效，有效值为：str、json、dict、df、markdown")
                return False

            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行历史委托查询操作"""
        start_time = time.time()
        stock_code = params.get("stock_code")
        return_type = params.get("return_type")
        time_range = params.get("time_range", "当日")

        try:
            self.logger.info(f"执行历史委托查询操作，股票代码: {stock_code or '全部'}")
            self.switch_left_menus("查询[F4]", "历史委托")
            # self.sleep(0.2)

            # 1. 打开历史委托查询界面（通常是F7或Ctrl+F7）
            main_window = self.get_main_window(wrapper_obj=True)
            # 尝试使用Ctrl+F7打开历史委托，如果不行再尝试其他快捷键
            main_panel = main_window.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]

            # auto_id
            control_map ={
                "当日": "5315",
                "近一周": "5308",
                "近一月": "5309",
                "近三月": "5310",
                "近一年": "5311"
            }
            # 2. 选择时间范围
            self.get_control_with_children(main_panel,auto_id=control_map[time_range], control_type="Button", class_name="Button").click()

            # 3. 如果指定了股票代码，输入股票代码进行查询
            if stock_code:
                combox = self.get_control_with_children(main_panel, control_type="ComboBox", class_name="ComboBox", auto_id="1337")
                edit_stock_code = self.get_control_with_children(combox,auto_id="1001", control_type="Edit", class_name="Edit")
                # 清空并输入股票代码
                edit_stock_code.type_keys('{BACKSPACE 7}')
                time.sleep(0.05)
                edit_stock_code.type_keys(str(stock_code))
                time.sleep(0.1)
            else:
                query_btn = self.get_control_with_children(main_panel, class_name="Button", auto_id="2449")
                query_btn.click()

            # 4. 点击查询按钮
            #等待加载数据
            time.sleep(0.2)
            # 获取表格控件
            # table_control = self.get_control(control_id=0x417, class_name="CVirtualGridCtrl")
            table_panel = main_panel.children(control_type="Pane", title='HexinScrollWnd')[0].children(control_type="Pane", title="HexinScrollWnd2")[0].children(class_name="CVirtualGridCtrl")[0]

            # 鼠标左键点击
            table_panel.click_input()
            time.sleep(0.01)

            # 按下 Ctrl+A Ctrl+C 触发复制
            table_panel.type_keys("^a")
            time.sleep(0.02)
            table_panel.type_keys("^c")
            time.sleep(0.15)
            # 处理触发复制的限制提示框
            self.process_captcha_dialog()
            # 获取剪贴板数据
            table_data = self.get_clipboard_data()
            table_data = text2df(table_data)
            # 丢弃多余列
            table_data = table_data.drop(columns=["Unnamed: 13"], errors="ignore")

            is_op_success = not self.is_exist_pop_dialog()  # 没有弹窗了，说明没有其他意外情况发生
            if is_op_success:
                # 获取表格数据
                table_data = df_format_convert(table_data, return_type)

            # 6. 准备返回数据
            result_data = {
                "historical_orders": f"没有对应的历史委托订单" if len(table_data) == 0 else table_data,
                "stock_code": stock_code,
                "time_range": time_range,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": is_op_success
            }

            self.logger.info(f"历史委托查询完成，耗时{time.time() - start_time}秒",
                           stock_code=stock_code or "全部")

            return OperationResult(
                success=is_op_success,
                data=result_data
            )

        except Exception as e:
            error_msg = f"历史委托查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={"timestamp": time.time()}
            )