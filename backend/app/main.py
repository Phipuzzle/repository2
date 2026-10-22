from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.service import shutdown_agent_runs
from app.agent.telemetry import configure_telemetry, instrument_fastapi, instrument_sqlalchemy
from app.api.v1.audit import router as audit_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import router as health_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.query_runs import router as query_runs_router
from app.core.config import get_settings
from app.core.errors import unhandled_exception_handler
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import dispose_engine, engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_telemetry()
    instrument_sqlalchemy(engine)
    try:
        yield
    finally:
        await shutdown_agent_runs()
        await dispose_engine()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Query run, SSE, result, metric, feedback and audit APIs for the Intelligent Data Agent."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(health_router)
app.include_router(query_runs_router)
app.include_router(metrics_router)
app.include_router(feedback_router)
app.include_router(audit_router)
instrument_fastapi(app)
