"""账户切换操作 - 切换当前交易账户"""

import time

from easyths.core import BaseOperation
from easyths.core.account_state import account_state
from easyths.models.operations import ErrorCode, OperationResult
from easyths.operations.params import AccountSwitchParams
from easyths.operations.results import AccountSwitchResult


class AccountSwitchOperation(BaseOperation[AccountSwitchParams]):
    """切换当前交易账户（幂等）。

    - 目标账户不在缓存账户列表中（含列表未初始化）→ ``client_rejected`` 失败
    - 目标即当前账户 → 直接成功，不触 GUI
    - 其余情况：主窗口发送 ``Alt + 账户序号`` 完成切换，成功后刷新缓存
    """

    operation_name = "account_switch"
    description = "切换当前交易账户"
    Params = AccountSwitchParams
    Result = AccountSwitchResult

    def execute(self, params: AccountSwitchParams) -> OperationResult:
        start_time = time.time()
        previous = account_state.current_used_account

        index = next(
            (
                idx
                for name, idx in account_state.available_accounts
                if name == params.account_name
            ),
            None,
        )
        if index is None:
            return self._fail(
                f"账户（{params.account_name}）不存在,当前可用账户为：{[name for name, index in account_state.available_accounts]} ",
                ErrorCode.CLIENT_REJECTED,
            )

        # 同账户幂等：已是当前使用账户则直接成功，不触 GUI
        if previous == params.account_name:
            return self._ok(
                data=AccountSwitchResult(
                    previous_used_account=previous,
                    current_used_account=params.account_name,
                ).model_dump(),
                message=f"当前已使用账户{params.account_name}，无需切换",
            )

        # Alt + 账户序号 切换（% 即 Alt）
        main_window = self.get_main_window(wrapper_obj=True)
        main_window.type_keys(f"%{index}")
        account_state.set_current_used_account(params.account_name)
        # 给点缓冲，增加稳定性
        self.sleep(0.3)

        return self._ok(
            data=AccountSwitchResult(
                previous_used_account=previous,
                current_used_account=params.account_name,
            ).model_dump(),
            message=(
                f"已切换至账户{params.account_name}"
                + (f"（原账户{previous}）" if previous else "")
                + f"，耗时{time.time() - start_time:.2f}秒"
            ),
        )
