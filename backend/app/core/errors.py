import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("uvicorn.error")


def install_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "success": False,
                "message": detail,
                "data": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in issue["loc"]),
                "message": issue["msg"],
            }
            for issue in exc.errors()
        ]

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "Request validation failed",
                "data": {"errors": errors},
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError):
        logger.exception(
            "Database error while handling %s %s",
            request.method,
            request.url.path,
        )

        print("\n" + "=" * 80)
        print("DATABASE EXCEPTION")
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80 + "\n")

        # Re-raise so uvicorn prints the complete traceback
        raise exc

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception while handling %s %s",
            request.method,
            request.url.path,
        )

        print("\n" + "=" * 80)
        print("UNHANDLED EXCEPTION")
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80 + "\n")

        # Re-raise so uvicorn prints the complete traceback
        raise exc