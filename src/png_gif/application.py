"""Приложение FastAPI с XML и HTTP Basic по RFC 7617."""

import base64
import binascii
from contextlib import asynccontextmanager
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from png_gif.file_store import FileStore
from png_gif.jobs import Jobs
from png_gif.model import Model
from png_gif.routes import actor_router, instruction_router, report_router
from png_gif.schema import ModelError
from png_gif.xml_codec import encode


AUTH_CHALLENGE = {'WWW-Authenticate': 'Basic realm="png-gif", charset="UTF-8"'}


class XmlResponse(Response):
    """Использовать XML и для успешных ответов, и для ошибок."""

    media_type = "application/xml"

    def render(self, content):
        return encode(content)


def authorized(header, settings):
    """Разобрать Basic и сравнить обе части без раннего выхода."""
    try:
        scheme, token = header.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, binascii.Error, UnicodeError):
        return False
    username_ok = secrets.compare_digest(
        username.encode("utf-8"), settings.username.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        password.encode("utf-8"), settings.password.encode("utf-8"),
    )
    return username_ok & password_ok


def create_store(settings):
    """Создать файловый слой данных второго этапа."""
    return FileStore(settings.data_dir / "records.json")


def lifespan_for(settings):
    """Открыть хранилище при старте, затем закрыть очередь и данные."""
    @asynccontextmanager
    async def lifespan(app):
        store = create_store(settings)
        model = Model(store)
        jobs = Jobs(model, settings.data_dir, settings.test_mode)
        app.state.model, app.state.jobs = model, jobs
        try:
            yield
        finally:
            try:
                jobs.close()
            finally:
                store.close()
    return lifespan


def add_error_handlers(app):
    """Заменить стандартные JSON-ошибки FastAPI XML-ответами."""
    @app.exception_handler(ModelError)
    async def model_error(request, error):
        return XmlResponse({"error": str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return XmlResponse({"error": "Invalid path parameter"}, status_code=400)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return XmlResponse({"error": str(error.detail)},
                           status_code=error.status_code)


def create_app(settings):
    """Собрать десять маршрутов, жизненный цикл и проверку авторизации."""
    app = FastAPI(default_response_class=XmlResponse,
                  lifespan=lifespan_for(settings), docs_url=None,
                  redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        header = request.headers.get("Authorization", "")
        if not authorized(header, settings):
            return XmlResponse({"error": "Authentication required"},
                               status_code=401, headers=AUTH_CHALLENGE)
        return await call_next(request)

    add_error_handlers(app)
    app.include_router(actor_router())
    app.include_router(instruction_router())
    app.include_router(report_router())
    return app
