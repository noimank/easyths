"""API 层行为单元测试：统一信封、提交时校验 422、404/408 语义、中间件。

通过 stub 队列与真实 FastAPI 应用（生成的类型化路由）测试，无需 GUI。
"""

import re
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from easyths.api.app import TradingAPIApp
from easyths.api.dependencies import common
from easyths.core.account_state import account_state
from easyths.core.base_operation import operation_registry
from easyths.models.operations import (
    ErrorCode,
    Operation,
    OperationResult,
    OperationStatus,
)
from easyths.utils import project_config_instance


class StubQueue:
    """实现路由所需接口的假队列，行为可控"""

    def __init__(self):
        self._lock = threading.Lock()
        self._ops: dict[str, Operation] = {}

    def submit(self, operation: Operation) -> str:
        with self._lock:
            self._ops[operation.id] = operation
        return operation.id

    def get_state(self, operation_id: str) -> Operation | None:
        return self._ops.get(operation_id)

    def get_result(self, operation_id: str, timeout=None) -> OperationResult | None:
        op = self._ops.get(operation_id)
        if op is None:
            raise KeyError(operation_id)
        return op.result  # 由测试预先设置；None 即视为未完成

    def get_queue_stats(self) -> dict:
        return {"queued_count": 0}

    def cancel_operation(self, operation_id: str) -> bool:
        return operation_id in self._ops

    def _make(self, status=OperationStatus.RUNNING, result=None) -> Operation:
        op = Operation(name="buy", params={})
        op.status = status
        op.result = result
        with self._lock:
            self._ops[op.id] = op
        return op


@pytest.fixture(scope="module")
def client():
    operation_registry.load_plugins()
    stub = StubQueue()
    common.set_global_instances(stub, None)
    # 本测试聚焦路由/信封行为（认证有专门用例），构建应用期间关闭认证，
    # 避免依赖本地 config.toml 是否配置了 api key；中间件在栈构建时快照配置，
    # 随后恢复原值不影响其他用例
    original_key = project_config_instance.api_key
    project_config_instance.api_key = None
    try:
        app = TradingAPIApp(stub, None).create_app()
        # 去掉限流中间件对批量测试请求的干扰（该中间件行为单独测试）
        app.user_middleware = [
            m for m in app.user_middleware if "RateLimit" not in str(m.cls)
        ]
        app.middleware_stack = app.build_middleware_stack()
    finally:
        project_config_instance.api_key = original_key
    return TestClient(app), stub


def test_execute_operation_validates_params_at_submit(client):
    """非法参数在提交时即 422（统一信封），不进入队列。"""
    c, _ = client
    r = c.post(
        "/api/v1/operations/buy",
        json={"stock_code": "6000", "price": 10, "quantity": 100},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "invalid_params"


def test_execute_operation_rejects_unknown_params(client):
    """未知字段（extra=forbid）提交时 422。"""
    c, _ = client
    r = c.post(
        "/api/v1/operations/buy",
        json={"stock_code": "600000", "price": 10, "quantity": 100, "typo": 1},
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "invalid_params"


def test_execute_operation_accepts_priority(client):
    """请求体可附带可选 priority；提交仅受理，success 保持 null。"""
    c, _ = client
    r = c.post(
        "/api/v1/operations/buy",
        json={"stock_code": "600000", "price": 10, "quantity": 100, "priority": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is None
    assert body["status"] == "queued"
    assert "operation_id" in body["data"]


def test_account_switch_validates_account_name_at_submit(client):
    """account_switch 缺少 account_name 提交时即 422。"""
    c, _ = client
    r = c.post("/api/v1/operations/account_switch", json={})
    assert r.status_code == 422
    assert r.json()["error_code"] == "invalid_params"

    r = c.post(
        "/api/v1/operations/account_switch",
        json={"account_name": "模拟账户", "typo": 1},
    )
    assert r.status_code == 422


def test_account_operations_submit(client):
    """账户操作按参数模型受理提交（仅受理，success 为 null）。"""
    c, _ = client
    for name, payload in [
        ("account_query", {}),
        ("account_switch", {"account_name": "模拟账户"}),
    ]:
        r = c.post(f"/api/v1/operations/{name}", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is None
        assert body["status"] == "queued"
        assert "operation_id" in body["data"]


def test_submit_with_account_directive(client):
    """请求体可附带 account_name 执行指令（与业务参数分离），默认 None。"""
    c, stub = client
    r = c.post(
        "/api/v1/operations/buy",
        json={
            "stock_code": "600000",
            "price": 10,
            "quantity": 100,
            "account_name": "B账户",
        },
    )
    assert r.status_code == 200
    op = stub._ops[r.json()["data"]["operation_id"]]
    assert op.account_name == "B账户"
    assert "account_name" not in op.params

    r = c.post("/api/v1/operations/funds_query", json={})
    assert stub._ops[r.json()["data"]["operation_id"]].account_name is None


def test_account_directive_blank_name_422(client):
    """account_name 指令为空串时提交即 422。"""
    c, _ = client
    r = c.post(
        "/api/v1/operations/buy",
        json={
            "stock_code": "600000",
            "price": 10,
            "quantity": 100,
            "account_name": "",
        },
    )
    assert r.status_code == 422
    assert r.json()["error_code"] == "invalid_params"


def test_account_switch_business_param_not_stripped(client):
    """account_switch 的 account_name 是业务参数：留在 params 且不注入指令。"""
    c, stub = client
    r = c.post("/api/v1/operations/account_switch", json={"account_name": "B账户"})
    assert r.status_code == 200
    op = stub._ops[r.json()["data"]["operation_id"]]
    assert op.params == {"account_name": "B账户"}
    assert op.account_name is None


def test_account_query_rejects_account_directive(client):
    """account_query 不接受 account_name 指令：提交时即 422（未知参数）。

    指令执行依赖 account_query 初始化的账户缓存，携带指令会构成死循环
    （重连后缓存为空时必失败），因此该操作显式关闭指令注入。
    """
    c, _ = client
    r = c.post("/api/v1/operations/account_query", json={"account_name": "B账户"})
    assert r.status_code == 422
    assert r.json()["error_code"] == "invalid_params"


def test_reconnect_clears_account_state(client, monkeypatch):
    """重连成功清空账户缓存（客户端可能已重启，序号/当前账户不可信）；失败保留。"""

    class FailAutomator:
        def reconnect(self) -> bool:
            return False

    class OkAutomator:
        def reconnect(self) -> bool:
            return True

    c, _ = client
    account_state.update_available_accounts([("A账户", 1)])
    account_state.set_current_used_account("A账户")

    monkeypatch.setattr(common, "_automator", FailAutomator())
    assert c.post("/api/v1/system/reconnect").status_code == 503
    assert account_state.available_accounts == [("A账户", 1)]

    monkeypatch.setattr(common, "_automator", OkAutomator())
    assert c.post("/api/v1/system/reconnect").status_code == 200
    assert account_state.available_accounts == []
    assert account_state.current_used_account is None


def test_result_endpoint_unknown_id_404(client):
    """不存在的操作 ID 返回 404（而非 408），信封含 not_found。"""
    c, _ = client
    r = c.get("/api/v1/operations/not-exist/result")
    assert r.status_code == 404
    assert r.json()["error_code"] == "not_found"


def test_result_endpoint_timeout_408_with_status(client):
    """等待超时返回 408，响应体带当前 status，明确操作仍在执行。"""
    c, stub = client
    op = stub._make(status=OperationStatus.RUNNING, result=None)
    r = c.get(f"/api/v1/operations/{op.id}/result?timeout=0.2")
    assert r.status_code == 408
    body = r.json()
    assert body["error_code"] == "timeout"
    assert body["status"] == "running"


def test_result_endpoint_returns_unified_envelope(client):
    """终态结果直接以统一信封返回，业务数据在 data，不再双层嵌套。"""
    c, stub = client
    result = OperationResult(
        status=OperationStatus.COMPLETED,
        success=True,
        data={"stock_code": "600000"},
        message="成功提交600000的买入委托",
    )
    op = stub._make(status=OperationStatus.COMPLETED, result=result)
    r = c.get(f"/api/v1/operations/{op.id}/result")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["status"] == "completed"
    assert body["data"] == {"stock_code": "600000"}
    assert body["message"] == "成功提交600000的买入委托"
    assert body["current_used_account"] is None


def test_result_endpoint_carries_current_used_account(client):
    """终态结果的 current_used_account 随信封透出（多账户场景）。"""
    c, stub = client
    result = OperationResult(
        status=OperationStatus.COMPLETED, success=True, current_used_account="模拟账户"
    )
    op = stub._make(status=OperationStatus.COMPLETED, result=result)
    body = c.get(f"/api/v1/operations/{op.id}/result").json()
    assert body["current_used_account"] == "模拟账户"


def test_status_endpoint_snapshot(client):
    """状态快照：非终态 success 为 None，终态回填业务结果。"""
    c, stub = client
    running = stub._make(status=OperationStatus.QUEUED, result=None)
    body = c.get(f"/api/v1/operations/{running.id}/status").json()
    assert body["status"] == "queued"
    assert body["success"] is None

    done = stub._make(
        status=OperationStatus.FAILED,
        result=OperationResult(
            status=OperationStatus.FAILED,
            success=False,
            message="数量必须是100的倍数",
            error_code=ErrorCode.CLIENT_REJECTED,
        ),
    )
    body = c.get(f"/api/v1/operations/{done.id}/status").json()
    assert body["success"] is False
    assert body["error_code"] == "client_rejected"


def test_list_operations_contains_schemas(client):
    c, _ = client
    body = c.get("/api/v1/operations/").json()
    assert body["data"]["count"] >= 16
    buy = body["data"]["operations"]["buy"]
    assert "parameters" in buy
    assert "result_schema" in buy
    assert "price" in buy["result_schema"]["properties"]
    assert buy["supports_account_directive"] is True
    # account_switch/account_query 不注入 account_name 指令（契约标志）
    assert (
        body["data"]["operations"]["account_switch"]["supports_account_directive"]
        is False
    )
    assert (
        body["data"]["operations"]["account_query"]["supports_account_directive"]
        is False
    )


def test_load_plugins_idempotent():
    """插件加载幂等：首次调用加载，重复调用返回 0 不重复扫描注册。"""
    operation_registry.load_plugins()
    assert operation_registry.load_plugins() == 0
    assert "account_query" in operation_registry.list_operations()


def test_envelope_timestamp_format(client):
    """时间戳为北京时间秒级文本（2026-08-22 06:46:56）。"""
    c, _ = client
    body = c.get("/api/v1/operations/").json()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body["timestamp"])


def test_rate_limit_returns_429():
    """限流触发返回 429 统一信封（rate_limited），且过期 IP 记录被清理。"""
    from easyths.api.middleware import RateLimitMiddleware

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware, calls=2, period=60)
    c = TestClient(app)
    assert c.get("/ping").status_code == 200
    assert c.get("/ping").status_code == 200
    r = c.get("/ping")
    assert r.status_code == 429
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "rate_limited"
    # 客户端记录被清理后不会无限累积
    mw = app.middleware_stack.app  # 最外层即限流中间件
    assert isinstance(mw, RateLimitMiddleware)
    assert all(len(v) <= 2 for v in mw.clients.values())


def test_ip_whitelist_ignores_forwarded_headers():
    """伪造 X-Forwarded-For / X-Real-IP 不能绕过白名单，403 统一信封（forbidden）。"""
    from easyths.api.middleware import IPWhitelistMiddleware

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(IPWhitelistMiddleware, allowed_hosts=["10.0.0.1"])
    c = TestClient(app, client=("192.168.1.50", 22222))
    r = c.get("/ping", headers={"X-Forwarded-For": "10.0.0.1", "X-Real-IP": "10.0.0.1"})
    assert r.status_code == 403
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "forbidden"
    assert "192.168.1.50" in body["message"]


def test_api_key_auth_returns_unified_envelope(monkeypatch):
    """认证失败（缺凭据/错密钥）返回 401 统一信封（unauthorized），保留 WWW-Authenticate 头。"""
    from easyths.api.middleware import APIKeyAuthMiddleware
    from easyths.utils import project_config_instance

    app = FastAPI()

    @app.get("/api/ping")
    async def ping():
        return {"ok": True}

    @app.get("/public")
    async def public():
        return {"ok": True}

    monkeypatch.setattr(project_config_instance, "api_key", "secret-key")
    app.add_middleware(APIKeyAuthMiddleware)
    c = TestClient(app)

    r = c.get("/api/ping")  # 缺少凭据
    assert r.status_code == 401
    body = r.json()
    assert body["success"] is False
    assert body["error_code"] == "unauthorized"
    assert r.headers["WWW-Authenticate"] == "Bearer"

    r = c.get("/api/ping", headers={"Authorization": "Bearer wrong"})  # 错误密钥
    assert r.status_code == 401
    assert r.json()["error_code"] == "unauthorized"

    r = c.get("/api/ping", headers={"Authorization": "Bearer secret-key"})
    assert r.status_code == 200

    # 认证只覆盖 /api 数据面：页面/静态资源/文档公开访问
    assert c.get("/public").status_code == 200


def test_system_status_exposes_account_state(client, monkeypatch):
    """系统状态直接透出内存账户缓存快照（控制台免执行 account_query 即可取账户）。"""

    class StubAutomator:
        app_path = "stub"

        def is_connected(self):
            return True

        def is_process_alive(self):
            return True

    monkeypatch.setattr(common, "_automator", StubAutomator())
    c, _ = client
    account_state.update_available_accounts([("A账户", 1), ("B账户", 2)])
    account_state.set_current_used_account("A账户")
    try:
        body = c.get("/api/v1/system/status").json()
        account = body["data"]["account"]
        assert account["current_used_account"] == "A账户"
        assert account["available_accounts"] == [
            {"account_name": "A账户", "account_index": 1},
            {"account_name": "B账户", "account_index": 2},
        ]
    finally:
        account_state.clear()


def test_mcp_execute_operation_queue_full_returns_envelope(monkeypatch):
    """MCP 工具在队列满（submit 抛 ValueError）时返回 internal 信封而非裸异常。"""
    import easyths.api.routes.mcp_server as mcp_module

    class FullQueue:
        def submit(self, operation):
            raise ValueError("队列已满，无法添加操作")

    monkeypatch.setattr(mcp_module, "_operation_queue", FullQueue())
    envelope = mcp_module._execute_operation("buy", {})
    assert envelope["success"] is False
    assert envelope["error_code"] == "internal"
    assert "队列已满" in envelope["message"]


def test_logging_middleware_redacts_sensitive_headers():
    """请求日志对 authorization/cookie 脱敏。"""
    import easyths.api.middleware.logging as mlog
    from easyths.api.middleware import LoggingMiddleware

    captured = {}

    class Cap:
        def info(self, event, **kw):
            captured[event] = kw

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(LoggingMiddleware)
    mlog.logger = Cap()
    TestClient(app).get(
        "/ping", headers={"Authorization": "Bearer secret", "Cookie": "sid=1"}
    )
    headers = captured["API请求开始"]["headers"]
    assert headers["authorization"] == "***"
    assert headers["cookie"] == "***"
