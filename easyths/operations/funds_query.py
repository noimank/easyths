import time
from typing import Dict, Any

from easyths.core import BaseOperation
from easyths.models.operations import PluginMetadata, OperationResult


class FundsQueryOperation(BaseOperation):
    """资金查询操作"""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="FundsQueryOperation",
            version="1.0.0",
            description="查询账户资金信息",
            author="noimank",
            operation_name="funds_query",
            parameters={
            }
        )

    def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        return True


    def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行资金查询操作"""
        start_time = time.time()

        try:
            self.logger.info(f"执行资金查询操作。")
            # 切换到资金股票菜单
            self.switch_left_menus("查询[F4]", "资金股票")
            # 刷新数据
            self.get_main_window(wrapper_obj=True).type_keys("{F5}")
            # 防抖
            self.sleep(0.3)
            # print(f"切换页面耗时：{time.time() - tt}")
            # 拿到显示面板, 大约会有 34个children
            # main_window = self.get_main_window()
            # main_panel = main_window.child_window(auto_id="59649", control_type="Pane", depth=2).wrapper_object()
                 # 改进版：不使用child_window从 1.5s降低到1s
            main_window_wrapper = self.get_main_window(wrapper_obj=True)
            main_panel = main_window_wrapper.children(control_type="Pane")[0].children(class_name='AfxMDIFrame140s')[0]
            # 再进一步筛选
            text_controls = main_panel.children(control_type="Text",class_name="Static")

            # 准备返回数据
            result_data = {
                "timestamp": time.time(),
                "success": True
            }

            # 一次遍历完成信息提取
            for control in text_controls:
                auto_id = control.element_info.automation_id
                if auto_id == "1012":
                    result_data["资金余额"] = control.window_text()
                elif auto_id == "1013":
                    result_data["冻结金额"] = control.window_text()
                elif auto_id == "1016":
                    result_data["可用金额"] = control.window_text()
                elif auto_id == "1017":
                    result_data["可取金额"] = control.window_text()
                elif auto_id == "1014":
                    result_data["股票市值"] = control.window_text()
                elif auto_id == "1015":
                    result_data["总资产"] = control.window_text()
                elif auto_id == "1027":
                    result_data["持仓盈亏"] = control.window_text()

            self.logger.info(f"资金查询完成，耗时{time.time() - start_time}", **result_data)

            return OperationResult(
                success=True,
                data=result_data
            )

        except Exception as e:
            error_msg = f"资金查询操作异常: {str(e)}"
            self.logger.exception(error_msg)
            return OperationResult(
                success=False,
                error=error_msg,
                data={ "timestamp": time.time()}
            )