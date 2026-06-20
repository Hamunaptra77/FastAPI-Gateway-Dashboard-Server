from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import asyncio
import contextlib
import logging
import time

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.routers import admin, dashboard, gateway, license_user, payments
from app.services.auth_service import seed_admin_users
from app.services.cleanup_service import cleanup_inactive_trial_licenses
from app.services.license_service import seed_license_plans


cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    global cleanup_task

    settings.ensure_security_for_runtime()

    if settings.app_env.lower() != "testing":
        Base.metadata.create_all(bind=engine)

        with SessionLocal() as db:
            seed_license_plans(db)
            seed_admin_users(db)

    for warning in settings.security_warnings():
        logger.warning("security_warning %s", warning)

    if settings.app_env.lower() != "testing":
        with SessionLocal() as db:
            deleted = cleanup_inactive_trial_licenses(db)
            if deleted:
                logger.info("Removed %s inactive trial licenses at startup", deleted)

        cleanup_task = asyncio.create_task(_trial_cleanup_loop())

    try:
        yield
    finally:
        if cleanup_task is not None:
            cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cleanup_task
            cleanup_task = None

app = FastAPI(title=settings.app_name, debug=settings.app_debug, lifespan=app_lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    max_age=settings.session_timeout_minutes * 60,
    same_site="lax",
    https_only=settings.session_cookie_secure_enabled(),
)
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = Limiter(key_func=get_remote_address)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG if settings.app_debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("request_failed method=%s path=%s duration_ms=%.2f", request.method, request.url.path, duration_ms)
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request_completed method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("http_error method=%s path=%s status=%s detail=%s", request.method, request.url.path, exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "http_error",
                "message": str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": jsonable_encoder(exc.errors()) if settings.app_debug else [],
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "Internal server error",
            }
        },
    )


async def _trial_cleanup_loop() -> None:
    while True:
        with SessionLocal() as db:
            deleted = cleanup_inactive_trial_licenses(db)
            if deleted:
                logger.info("Removed %s inactive trial licenses", deleted)

        await asyncio.sleep(max(settings.trial_cleanup_interval_seconds, 60))

app.include_router(dashboard.router)
app.include_router(admin.router)
app.include_router(license_user.router)
app.include_router(gateway.router)
app.include_router(payments.router)


@app.get("/health")
def healthcheck():
    return {"status": "ok", "service": settings.app_name}
