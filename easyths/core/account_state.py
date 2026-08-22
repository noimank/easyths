"""多账户状态缓存：进程内唯一的可用账户列表/当前使用账户可信副本。

写入方为账户操作：``account_query`` 刷新可用账户列表并借下拉选中项识别
当前使用账户（服务启动时自动执行一次完成初始化），``account_switch``
切换成功后刷新当前使用账户。读取方为所有操作结果的
``current_used_account`` 字段（``BaseOperation._ok/_fail`` 自动附带）与
账户切换的序号解析。操作队列串行执行保证无并发写，无需加锁。
"""

#: 账户条目：（账户名，客户端列表序号）
AccountEntry = tuple[str, int]


class AccountState:
    """账户状态缓存。

    可用账户以 ``(account_name, account_index)`` 条目存储：账户名是对外
    契约（接口参数/结果字段），序号是客户端列表位置（Alt+序号 切换的
    定位依据）。启动后由 account_query 完成初始化，此后恒非空。
    """

    def __init__(self) -> None:
        self._available_accounts: list[AccountEntry] = []
        self._current_used_account: str | None = None

    @property
    def available_accounts(self) -> list[AccountEntry]:
        """已缓存的全部可用账户条目（副本），未初始化为空列表"""
        return list(self._available_accounts)

    @property
    def current_used_account(self) -> str | None:
        """当前使用账户，未初始化（或已不在可用账户列表中）为 None"""
        return self._current_used_account

    def update_available_accounts(self, accounts: list[AccountEntry]) -> None:
        """刷新可用账户缓存（唯一调用方 account_query 保证当前使用账户来自同源读取）"""
        self._available_accounts = list(accounts)

    def set_current_used_account(self, name: str) -> None:
        """刷新当前使用账户（account_query 选中项识别 / account_switch 成功后调用）"""
        self._current_used_account = name

    def clear(self) -> None:
        """清空缓存（重连成功后调用：客户端可能已重启，账户集合/顺序与当前账户不可信）"""
        self._available_accounts = []
        self._current_used_account = None


#: 全局账户状态缓存（服务进程内单例，同花顺客户端只有一个）
account_state = AccountState()
