import time
from typing import Dict, Any

from easyths.automation.base_operation import BaseOperation, register_operation
from easyths.models.operations import PluginMetadata, OperationResult


@register_operation
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
                "query_type": {
                    "type": "string",
                    "required": False,
                    "description": "查询类型：total（总资金）、available（可用资金）、frozen（冻结资金）、stock_value（股票市值）",
                    "enum": ["total", "available", "frozen", "stock_value", "all"],
                    "default": "all"
                }
            }
        )

    async def validate(self, params: Dict[str, Any]) -> bool:
        """验证查询参数"""
        return True


    async def execute(self, params: Dict[str, Any]) -> OperationResult:
        """执行资金查询操作"""
        # query_type = params.get("query_type", "all")
        start_time = time.time()

        try:
            self.logger.info(f"执行资金查询操作。")

            # 切换到资金股票菜单
            self.switch_left_menus(["查询[F4]", "资金股票"])

            fund_balance = self.get_control(control_id=0x3F4).window_text()
            frozen_amount = self.get_control(control_id=0x3F5).window_text()
            available_amount = self.get_control(control_id=0x3F8).window_text()
            #可取金额
            amount_available = self.get_control(control_id=0x3F9).window_text()
            stock_market_capitalization = self.get_control(control_id=0x3F6).window_text()
            total_assets = self.get_control(control_id=0x3F7).window_text()
            profit_and_loss_on_holdings = self.get_control(control_id=0x403).window_text()

            # 准备返回数据
            result_data = {
                "资金余额": fund_balance,
                "冻结金额": frozen_amount,
                "可用金额": available_amount,
                "可取金额": amount_available,
                "股票市值": stock_market_capitalization,
                "总资产": total_assets,
                "持仓盈亏": profit_and_loss_on_holdings,
                "timestamp": time.time(),
                "success": True
            }

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