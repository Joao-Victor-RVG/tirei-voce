import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 400
    code = "bad_request"
    message = "Requisição inválida."

    def __init__(
        self, message: str | None = None, *, code: str | None = None, details: Any = None
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Você precisa estar logado."


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Você não tem permissão para esta ação."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Não encontrado."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Esta ação não é permitida no estado atual."


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"
    message = "Não foi possível processar a requisição."


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
    message = "Muitas tentativas. Aguarde um pouco e tente novamente."


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


_HTTP_CODES = {
    400: ("bad_request", "Requisição inválida."),
    401: ("unauthorized", "Você precisa estar logado."),
    403: ("forbidden", "Você não tem permissão para esta ação."),
    404: ("not_found", "Não encontrado."),
    405: ("method_not_allowed", "Método não permitido."),
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.details), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "Alguns campos estão inválidos.", details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("http_error", str(exc.detail)))
        return JSONResponse(
            error_body(code, message), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error")
        return JSONResponse(
            error_body("internal_error", "Ops! Algo deu errado. Tente novamente."),
            status_code=500,
        )
