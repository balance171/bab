"""
GET /api/meals — 급식 검색 엔드포인트
"""
import re
import time
import uuid
from typing import Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db import get_pool
from app.normalize import build_search_key

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api", tags=["meals"])

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 200

# ── 정렬 허용 컬럼 화이트리스트 ──────────────────────────────
SORTABLE = {
    "meal_date", "meal_year", "school_name", "region",
    "meal_type", "soup", "main_dish", "side1", "dessert",
}


# ── 응답 스키마 ──────────────────────────────────────────────
class MealRow(BaseModel):
    id: int
    region: str
    school_name: str
    meal_date: str        # ISO 문자열로 직렬화
    meal_type: str
    soup: Optional[str]
    main_dish: Optional[str]
    side1: Optional[str]
    dessert: Optional[str]
    menu_full: str
    search_key: str


class MealsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[MealRow]


# ── 쿼리 빌더 ────────────────────────────────────────────────
_SELECT_COLS = (
    "id, region, school_name, meal_date, meal_type, "
    "soup, main_dish, side1, dessert, menu_full, search_key"
)


def _build_query(
    school: Optional[str],
    school_code: Optional[str],
    dish: Optional[str],
    month: Optional[int],
    months: list[int],
    years: list[int],
    sort_col: str,
    sort_dir: str,
    page: int,
    page_size: int,
) -> tuple[str, str, list]:
    """
    (count_sql, data_sql, params) 반환.

    최적화 전략: btree 인덱스 조건(school_code, meal_month, meal_year)을
    CTE MATERIALIZED로 먼저 적용하고, 느린 텍스트 검색(ILIKE/LIKE)은
    작은 결과셋에서 수행 → Supabase 프리 티어에서도 빠른 응답.
    """
    # 빠른 조건 (btree 인덱스)
    fast_clauses: list[str] = []
    # 느린 조건 (텍스트 검색 — GIN이 한국어에서 느림)
    slow_clauses: list[str] = []
    params: list = []
    idx = 1

    if school_code:
        fast_clauses.append(f"school_code = ${idx}")
        params.append(school_code)
        idx += 1
    elif school:
        slow_clauses.append(f"school_name ILIKE ${idx}")
        params.append(f"%{school}%")
        idx += 1

    if dish:
        normalized = build_search_key(dish)
        slow_clauses.append(f"search_key LIKE ${idx}")
        params.append(f"%{normalized}%")
        idx += 1

    if months:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(months)))
        fast_clauses.append(f"meal_month IN ({placeholders})")
        params.extend(months)
        idx += len(months)
    elif month:
        fast_clauses.append(f"meal_month = ${idx}")
        params.append(month)
        idx += 1

    if years:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(years)))
        fast_clauses.append(f"meal_year IN ({placeholders})")
        params.extend(years)
        idx += len(years)

    order_sql = f"ORDER BY meal_year DESC, {sort_col} {sort_dir}, id ASC"
    offset = (page - 1) * page_size

    # CTE 최적화: month/year + text에만 사용 (school_code는 소량이라 불필요)
    has_school_code = any("school_code" in c for c in fast_clauses)
    use_cte = fast_clauses and slow_clauses and not has_school_code
    if use_cte:
        fast_where = "WHERE " + " AND ".join(fast_clauses)
        slow_where = "WHERE " + " AND ".join(slow_clauses)
        cte = f"WITH base AS MATERIALIZED (SELECT * FROM meals {fast_where})"
        count_sql = f"{cte} SELECT COUNT(*) FROM base {slow_where}"
        data_sql = (
            f"{cte} SELECT {_SELECT_COLS} "
            f"FROM base {slow_where} {order_sql} "
            f"LIMIT {page_size} OFFSET {offset}"
        )
    else:
        all_clauses = fast_clauses + slow_clauses
        where_sql = ("WHERE " + " AND ".join(all_clauses)) if all_clauses else ""
        count_sql = f"SELECT COUNT(*) FROM meals {where_sql}"
        data_sql = (
            f"SELECT {_SELECT_COLS} "
            f"FROM meals {where_sql} {order_sql} "
            f"LIMIT {page_size} OFFSET {offset}"
        )

    return count_sql, data_sql, params


# ── 엔드포인트 ───────────────────────────────────────────────
@router.get("/meals", response_model=MealsResponse)
async def search_meals(
    school: Optional[str] = Query(None, description="학교명 부분일치 (school_code 없을 때)"),
    school_code: Optional[str] = Query(None, description="학교코드 정확매칭 (자동완성 선택 시)"),
    dish: Optional[str] = Query(None, description="요리명 부분일치 (search_key 대상)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="월 단일 (1~12)"),
    months: list[int] = Query(default=[], description="월 복수선택 (예: ?months=3&months=4)"),
    years: list[int] = Query(default=[], description="연도 복수선택 (예: ?years=2023&years=2024)"),
    sort: str = Query("meal_date", description="정렬 컬럼"),
    order: Literal["asc", "desc", "default"] = Query("default", description="정렬 방향"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="페이지 크기"),
):
    request_id = uuid.uuid4().hex[:8]
    t0 = time.monotonic()
    log = logger.bind(request_id=request_id)

    # 조건 검증: school/school_code/dish/month 중 하나 이상 필요
    if not school and not school_code and not dish and month is None and not months:
        log.warning("search_empty_conditions", step="validate")
        raise HTTPException(
            status_code=400,
            detail="학교명, 요리명, 월 중 하나 이상 입력해야 합니다.",
        )

    # 정렬 컬럼 검증
    if sort not in SORTABLE:
        log.warning("invalid_sort_column", step="validate", sort=sort)
        raise HTTPException(
            status_code=400,
            detail=f"정렬 불가 컬럼: {sort}. 허용: {sorted(SORTABLE)}",
        )

    sort_dir = "ASC" if order == "asc" else ("DESC" if order == "desc" else "ASC")

    log.info(
        "search_request",
        step="search",
        school=school,
        dish=dish,
        month=month,
        years=years,
        sort=sort,
        order=order,
        page=page,
    )

    try:
        count_sql, data_sql, params = _build_query(
            school, school_code, dish, month, months, years, sort, sort_dir, page, page_size
        )
        pool = get_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(count_sql, *params)
            rows  = await conn.fetch(data_sql, *params)

    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        log.error(
            "search_db_error",
            step="search",
            error_type=type(exc).__name__,
            error_message=str(exc),
            duration_ms=duration_ms,
        )
        raise HTTPException(status_code=500, detail="데이터베이스 오류가 발생했습니다.")

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info(
        "search_ok",
        step="search",
        total=total,
        returned=len(rows),
        page=page,
        duration_ms=duration_ms,
    )

    def _strip(v: str | None) -> str | None:
        if not v:
            return v
        return re.sub(r"[a-zA-Z0-9.*#☆△★]+$", "", v).strip() or v

    data = [
        MealRow(
            id=r["id"],
            region=r["region"],
            school_name=r["school_name"],
            meal_date=r["meal_date"].isoformat(),
            meal_type=r["meal_type"],
            soup=_strip(r["soup"]),
            main_dish=_strip(r["main_dish"]),
            side1=_strip(r["side1"]),
            dessert=_strip(r["dessert"]),
            menu_full=r["menu_full"],
            search_key=re.sub(r"[0-9.*#☆△★]+(?=,|$)", "", r["search_key"] or ""),
        )
        for r in rows
    ]
    return MealsResponse(total=total, page=page, page_size=page_size, data=data)
