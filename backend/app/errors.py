"""에러 응답 봉투 — 계약 0장: {"error":{"code":"<대문자_스네이크>","message":"<한국어>"}}.

FastAPI 기본 {"detail": ...} 형식이 밖으로 새지 않게 전역에서 변환한다(#5 검수 반영).
라우터는 HTTPException(status, detail={"code": ..., "message": ..., ...확장필드})로 던지면
그대로 봉투에 실린다 — 코드별 확장 필드(예: current_quest_id)는 error 객체 안(계약 0장).
"""
import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bomnae")

_HTTP_MESSAGES = {
    404: ("NOT_FOUND", "요청한 주소를 찾을 수 없어요"),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 요청 방식이에요"),
}


def error_body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


class ErrorEnvelopeMiddleware:
    """unhandled 예외 → 500 INTERNAL 봉투.

    CORSMiddleware보다 먼저 add_middleware 해야(=스택 안쪽) 500 응답에도 CORS 헤더가 붙는다
    (전역 Exception 핸들러는 최외곽 ServerErrorMiddleware에서 돌아 CORS를 건너뛰는 함정).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception:
            logger.exception("unhandled error: %s %s", scope.get("method"), scope.get("path"))
            response = JSONResponse(
                status_code=500,
                content=error_body("INTERNAL", "일시적인 오류가 발생했어요. 잠시 후 다시 시도해 주세요"),
            )
            await response(scope, receive, send)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            body = error_body(**exc.detail)
        else:
            code, message = _HTTP_MESSAGES.get(
                exc.status_code, (HTTPStatus(exc.status_code).name, str(exc.detail))
            )
            body = error_body(code, message)
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        # 계약 §5 표기를 따라 400 VALIDATION — FastAPI 기본 422를 쓰지 않는다
        return JSONResponse(
            status_code=400, content=error_body("VALIDATION", "입력 값을 확인해 주세요")
        )
