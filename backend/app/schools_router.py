"""
GET /api/schools — 학교 목록 (메모리 캐싱, 자동완성용)
"""
import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import get_pool

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["schools"])

# ── 메모리 캐시 ────────────────────────────────────────────────
_cache: list[dict] | None = None
_loading: bool = False


class SchoolItem(BaseModel):
    school_name: str
    school_code: str
    region: str


async def _load_cache() -> list[dict]:
    global _cache, _loading
    if _cache is not None:
        return _cache
    if _loading:
        # 이미 로딩 중이면 완료될 때까지 대기
        import asyncio
        while _loading:
            await asyncio.sleep(0.1)
        return _cache or []
    _loading = True
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT school_name, school_code, region
                FROM meals
                ORDER BY school_name
                """
            )
        _cache = [{"school_name": r["school_name"], "school_code": r["school_code"], "region": r["region"]} for r in rows]
        logger.info("schools_cache_loaded", count=len(_cache))
        return _cache
    finally:
        _loading = False


@router.get("/schools", response_model=list[SchoolItem])
async def list_schools(
    q: str = Query("", description="학교명 검색어 (부분일치)"),
    limit: int = Query(20, ge=1, le=100),
):
    schools = await _load_cache()
    if not q:
        return schools[:limit]
    q_lower = q.lower()
    matched = [s for s in schools if q_lower in s["school_name"].lower()]
    return matched[:limit]
