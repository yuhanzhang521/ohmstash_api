import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Dict

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.migrations import run_database_migrations
from app.core.service_config import write_caddy_config
from app.database import SessionLocal, engine
from app.services import auth

STATIC_DIR = Path(__file__).resolve().parent / "static"
_registered_models = models
logger = logging.getLogger(__name__)

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    run_database_migrations(settings.DATABASE_URL, engine=engine)
    with SessionLocal() as db:
        auth.ensure_default_admin(db)
        auth.reset_default_admin_password(db, db.query(auth.AuthUser).order_by(auth.AuthUser.id).first())
    if settings.CADDY_BACKEND_HOST == "api":
        try:
            write_caddy_config(settings)
        except OSError:
            logger.warning("Unable to write Caddy config on startup", exc_info=True)
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/", tags=["Root"])
def read_root() -> Dict[str, str]:
    return {"message": "Welcome to the OhmStash API!"}


app.include_router(api_router, prefix=settings.API_V1_STR)
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
