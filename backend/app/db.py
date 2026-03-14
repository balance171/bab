"""
asyncpg 커넥션 풀 — FastAPI lifespan 에서 초기화/종료
"""
import os
from typing import Optional

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> None:
    global _pool
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
    _pool = await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=10,
        server_settings={"statement_timeout": "30000"},  # 30초 초과 시 오류 반환
    )
    logger.info("db_pool_created", step="startup", min_size=2, max_size=10)


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("db_pool_closed", step="shutdown")
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB 풀이 초기화되지 않았습니다.")
    return _pool
