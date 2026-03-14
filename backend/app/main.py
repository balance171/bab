import os
from contextlib import asynccontextmanager

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from app.db import close_pool, init_pool
from app.logging_config import setup_logging
from app.meals_router import router as meals_router
from app.schools_router import router as schools_router, _load_cache as _warm_schools_cache

setup_logging(module="api")
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    logger.info("startup", step="lifespan", message="NEIS Meal API starting")
    # 학교 목록 캐시 미리 로드 (첫 요청 지연 방지)
    import asyncio
    asyncio.create_task(_warm_schools_cache())
    yield
    await close_pool()
    logger.info("shutdown", step="lifespan", message="NEIS Meal API stopped")


app = FastAPI(
    title="NEIS Meal Search API",
    version="0.1.0",
    lifespan=lifespan,
)

_CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5174").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+",  # 개발: 모든 localhost 포트 허용
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(meals_router)
app.include_router(schools_router)


@app.get("/health")
async def health():
    logger.info("health_check", step="health", status="ok")
    return {"status": "ok", "version": "0.1.0"}
