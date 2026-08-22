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
    - 其余情况：主窗口发送 ``Alt + 账户序号`` 切换，经下拉列表校验实际生效后
      刷新缓存；校验未通过以 ``internal`` 收尾，缓存保持原账户
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
            names = [name for name, _ in account_state.available_accounts]
            hint = (
                f"当前可用账户为：{names}"
                if names
                else "账户列表未初始化（如刚重连），请先执行 account_query"
            )
            return self._fail(
                f"账户（{params.account_name}）不存在，{hint}",
                ErrorCode.CLIENT_REJECTED,
            )

        # 同账户幂等：已是当前使用账户则直接成功，不触 GUI
        if previous == params.account_name:
            return self._ok(
                data=AccountSwitchResult(
                    previous_used_account=previous,
                ).model_dump(),
                message=f"当前已使用账户{params.account_name}，无需切换",
            )

        # Alt + 账户序号 切换（% 即 Alt）
        main_window = self.get_main_window(wrapper_obj=True)
        main_window.type_keys(f"%{index}")
        # 给点缓冲，增加稳定性
        self.sleep(0.3)
        if not self._check_already_change(account_name_unverified=params.account_name):
            # 校验未通过：GUI 实际仍停留在原账户，缓存不动（不提前写目标账户）
            return self._fail(
                f"账户切换失败，当前账户保持为{previous or '未确认'}",
                ErrorCode.INTERNAL,
            )
        account_state.set_current_used_account(params.account_name)

        return self._ok(
            data=AccountSwitchResult(
                previous_used_account=previous,
            ).model_dump(),
            message=(
                f"已切换至账户{params.account_name}"
                + (f"（原账户{previous}）" if previous else "")
                + f"，耗时{time.time() - start_time:.2f}秒"
            ),
        )

    def _check_already_change(self, account_name_unverified: str) -> bool:
        """检查是否真的已经切换到位。

        账户名只取前面的标识（如 "平安证券-王*明" -> "平安证券"），
        条目与当前使用账户使用同一清洗规则，保证后者必在可用账户列表中。
        """
        main_window = self.get_main_window(wrapper_obj=True)
        toolbar_ctl = self.get_control_with_children(
            parent_control=main_window, control_type="ToolBar", auto_id="59392"
        )
        combobox_ctl = self.get_control_with_children(
            toolbar_ctl, control_type="ComboBox", auto_id="2322"
        )
        dropdown_btn = self.get_control_with_children(
            combobox_ctl, control_type="Button", auto_id="DropDown"
        )
        dropdown_btn.click()
        # 等待界面渲染
        self.sleep(0.4)

        list_box = self.automator.app.windows(
            class_name="ComboLBox", control_type="List"
        )[0]
        items = list_box.children()
        for item in items:
            account_name = item.window_text()
            if account_name == "编辑账户":
                continue
            # 只取前面的标识 如 "平安证券-王*明" -> "平安证券"
            clean_account_name = account_name.strip().split("-")[0]
            if item.is_selected() and clean_account_name == account_name_unverified:
                main_window.type_keys("{ESC}")
                return True
        # 退出下拉框
        main_window.type_keys("{ESC}")
        return False
