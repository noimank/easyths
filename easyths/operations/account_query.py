"""账户列表查询操作 - 获取客户端所有已登录账户"""

import time

from easyths.core import BaseOperation
from easyths.core.account_state import account_state
from easyths.models.operations import EmptyParams, OperationResult
from easyths.operations.results import AccountRow, AccountsResult


class AccountQueryOperation(BaseOperation[EmptyParams]):
    """获取客户端所有已登录账户（幂等）。

    首次执行点开账户下拉，读取全部 ``(account_name, account_index)`` 条目
    并借选中项识别当前账户；此后直接复用缓存，不再触 GUI。
    """

    operation_name = "account_query"
    description = "获取客户端所有已登录账户"
    Params = EmptyParams
    Result = AccountsResult

    def execute(self, params: EmptyParams) -> OperationResult:
        start_time = time.time()
        # 幂等获取：已缓存则直接复用，不再经 GUI 实时获取
        if not account_state.available_accounts:
            entries = self._read_accounts()
            account_state.update_available_accounts(entries)
        accounts = account_state.available_accounts

        return self._ok(
            data=AccountsResult(
                available_accounts=[
                    AccountRow(account_name=name, account_index=index)
                    for name, index in accounts
                ],
            ).model_dump(),
            message=f"共{len(accounts)}个账户，耗时{time.time() - start_time:.2f}秒",
        )

    def _read_accounts(self) -> list[tuple[str, int]]:
        """从客户端读取全部账户条目，并借选中项刷新当前使用账户。

        账户名取条目完整展示名（仅去除首尾空白，如 "平安证券-王*明"），
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
        # 解析账户列表
        account_items: list[tuple[str, int]] = []
        # 等待界面渲染
        self.sleep(0.35)

        list_box = self.automator.app.windows(
            class_name="ComboLBox", control_type="List"
        )[0]
        items = list_box.children()
        for index, item in enumerate(items):
            account_name = item.window_text()
            if account_name == "编辑账户":
                continue
            # 账户名如 "平安证券-王*明"
            clean_account_name = account_name.strip()
            account_items.append((clean_account_name, index + 1))
            if item.is_selected():
                account_state.set_current_used_account(clean_account_name)
                self.logger.info(f"当前使用的账户为：{account_name}")
        # 退出下拉框
        main_window.type_keys("{ESC}")
        return account_items
