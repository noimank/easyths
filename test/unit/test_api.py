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
from easyths.core.base_operation import operation_registry
from easyths.models.operations import (
    ErrorCode,
    Operation,
    OperationResult,
    OperationStatus,
)


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
    app = TradingAPIApp(stub, None).create_app()
    # 去掉限流中间件对批量测试请求的干扰（该中间件行为单独测试）
    app.user_middleware = [
        m for m in app.user_middleware if "RateLimit" not in str(m.cls)
    ]
    app.middleware_stack = app.build_middleware_stack()
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


def test_envelope_timestamp_format(client):
    """时间戳为北京时间秒级文本（2026-08-22 06:46:56）。"""
    c, _ = client
    body = c.get("/api/v1/operations/").json()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body["timestamp"])


def test_rate_limit_returns_429():
    """限流触发返回 429（而非 500），且过期 IP 记录被清理。"""
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
    # 客户端记录被清理后不会无限累积
    mw = app.middleware_stack.app  # 最外层即限流中间件
    assert isinstance(mw, RateLimitMiddleware)
    assert all(len(v) <= 2 for v in mw.clients.values())


def test_ip_whitelist_ignores_forwarded_headers():
    """伪造 X-Forwarded-For / X-Real-IP 不能绕过白名单。"""
    from easyths.api.middleware import IPWhitelistMiddleware

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(IPWhitelistMiddleware, allowed_hosts=["10.0.0.1"])
    c = TestClient(app, client=("192.168.1.50", 22222))
    r = c.get("/ping", headers={"X-Forwarded-For": "10.0.0.1", "X-Real-IP": "10.0.0.1"})
    assert r.status_code == 403


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
