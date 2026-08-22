"""API 层公共响应工具"""

from fastapi.responses import JSONResponse

from easyths.models.operations import APIResponse, ErrorCode


def json_response(envelope: APIResponse, status_code: int) -> JSONResponse:
    """以统一信封构造 JSON 响应"""
    return JSONResponse(
        status_code=status_code, content=envelope.model_dump(mode="json")
    )


def error_response(
    status_code: int, message: str, error_code: ErrorCode
) -> JSONResponse:
    """以统一信封构造错误响应（替代 HTTPException 的 {detail} 格式）"""
    return json_response(
        APIResponse(success=False, message=message, error_code=error_code), status_code
    )
