import datetime
import time
from typing import Dict, Any

from src.automation.base_operation import BaseOperation, register_operation
from src.models.operations import PluginMetadata, OperationResult

@register_operation
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
                "query_type": {
                    "type": "string",
                    "required": False,
                    "description": "查询类型：all（所有持仓）、available（可卖持仓）、frozen（冻结持仓）",
                    "enum": ["all", "available", "frozen"],
                    "default": "all"
                }
            }
        )

    async def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        try:
            query_type = params.get("return_type")
            if query_type not in ["str", "json", "dict","df", "markdown"]:
                self.logger.error("参数query_type无效，有效值为：str、json、dict、df、markdown")
                return False
            return True

        except Exception as e:
            self.logger.exception("参数验证异常", error=str(e))
            return False

    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行持仓查询操作"""
        start_time = time.time()
        return_type = params.get("return_type")
        try:
            self.logger.info(f"执行持仓查询操作。")
            # 切换到持仓菜单
            self.switch_left_menus(["查询[F4]", "资金股票"])

            table_data = self.get_table_data("持仓列表",return_type=return_type, control_id=0x417)
            # 准备返回数据
            result_data = {
                "holdings": table_data,
                "timestamp": datetime.datetime.now().isoformat(),
                "success": True
            }

            self.logger.info(f"持仓查询完成，耗时{time.time() - start_time}秒",
                           holding=table_data)

            return OperationResult(
                success=True,
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