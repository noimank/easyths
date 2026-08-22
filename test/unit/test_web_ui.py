"""内嵌 Web 控制台行为测试：静态资源挂载、页面公开访问、数据面认证边界。

控制台约定：页面与静态资源（/、/static/*）不含敏感数据，公开访问；
数据请求（/api/*）仍受 API Key 认证约束。
"""

import pytest
from fastapi.testclient import TestClient

from easyths.api.app import TradingAPIApp
from easyths.core.base_operation import operation_registry
from easyths.utils import project_config_instance


@pytest.fixture()
def web_client(monkeypatch):
    """带认证的完整应用：验证控制台资源公开而数据面受保护"""
    operation_registry.load_plugins()

    class StubQueue:
        def submit(self, operation):
            return operation.id

        def get_state(self, operation_id):
            return None

        def get_result(self, operation_id, timeout=None):
            raise KeyError(operation_id)

        def get_queue_stats(self):
            return {"queued_count": 0, "running_count": 0, "total_processed": 0}

        def cancel_operation(self, operation_id):
            return False

    # 关闭限流避免批量请求干扰；保留认证中间件验证边界
    monkeypatch.setattr(project_config_instance, "api_key", "test-key")
    monkeypatch.setattr(project_config_instance, "api_rate_limit", 0)
    app = TradingAPIApp(StubQueue(), None).create_app()
    return TestClient(app)


def test_root_serves_web_console(web_client):
    """/ 返回控制台 HTML 页面"""
    r = web_client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "EasyTHS 控制台" in r.text


def test_static_assets_served(web_client):
    """/static/* 返回控制台静态资源（正确的 MIME 类型）"""
    for path, content_type in [
        ("/static/app.js", "javascript"),
        ("/static/style.css", "text/css"),
    ]:
        r = web_client.get(path)
        assert r.status_code == 200, path
        assert content_type in r.headers["content-type"]


def test_console_resources_public_while_api_requires_key(web_client):
    """页面资源公开访问，数据面（/api/*）必须携带 Bearer Key"""
    # 页面与静态资源：无凭据可访问
    assert web_client.get("/").status_code == 200
    assert web_client.get("/static/app.js").status_code == 200

    # 数据面：无凭据 401，凭据有效放行
    r = web_client.get("/api/v1/operations/")
    assert r.status_code == 401
    assert r.json()["error_code"] == "unauthorized"

    r = web_client.get(
        "/api/v1/operations/", headers={"Authorization": "Bearer test-key"}
    )
    assert r.status_code == 200
    assert r.json()["data"]["count"] > 0


def test_static_mount_does_not_shadow_api(web_client):
    """静态挂载不影响 REST 路由：/api/v1 带凭据可正常到达"""
    r = web_client.get(
        "/api/v1/queue/stats", headers={"Authorization": "Bearer test-key"}
    )
    assert r.status_code == 200
    assert r.json()["success"] is True
