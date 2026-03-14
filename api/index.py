"""
Vercel Serverless Function — FastAPI 앱
/api/* 요청을 처리
"""
import os
import re
from typing import Literal, Optional

import asyncpg
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

PAGE_SIZE = 50

SORTABLE = {
    "meal_date", "school_name", "region",
    "meal_type", "soup", "main_dish", "side1", "dessert",
}

_SELECT_COLS = (
    "id, region, school_name, meal_date, meal_type, "
    "soup, main_dish, side1, dessert, menu_full, search_key"
)


# ── 정규화 ──────────────────────────────────────────────────
def _build_search_key(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[\s\u00a0\t]", "", text)
    text = re.sub(r"[a-z*☆△★]+(?=,|$)", "", text)
    text = re.sub(r"(?<=,)[*☆△★]+", "", text)
    text = re.sub(r"^[*☆△★]+", "", text)
    return text


# ── DB 연결 (serverless: 요청마다 연결) ─────────────────────
async def _get_conn() -> asyncpg.Connection:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise HTTPException(500, "DATABASE_URL not configured")
    return await asyncpg.connect(dsn, timeout=10)


# ── 스키마 ──────────────────────────────────────────────────
class MealRow(BaseModel):
    id: int
    region: str
    school_name: str
    meal_date: str
    meal_type: str
    soup: Optional[str] = None
    main_dish: Optional[str] = None
    side1: Optional[str] = None
    dessert: Optional[str] = None
    menu_full: str
    search_key: str


class MealsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[MealRow]


class SchoolItem(BaseModel):
    school_name: str
    school_code: str
    region: str


# ── 쿼리 빌더 ──────────────────────────────────────────────
def _build_query(
    school: Optional[str],
    school_code: Optional[str],
    dish: Optional[str],
    month: Optional[int],
    years: list[int],
    sort_col: str,
    sort_dir: str,
    page: int,
) -> tuple[str, str, list]:
    fast_clauses: list[str] = []
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
        normalized = _build_search_key(dish)
        slow_clauses.append(f"search_key LIKE ${idx}")
        params.append(f"%{normalized}%")
        idx += 1

    if month:
        fast_clauses.append(f"meal_month = ${idx}")
        params.append(month)
        idx += 1

    if years:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(years)))
        fast_clauses.append(f"meal_year IN ({placeholders})")
        params.extend(years)
        idx += len(years)

    order_sql = f"ORDER BY {sort_col} {sort_dir}, id ASC"
    offset = (page - 1) * PAGE_SIZE

    if fast_clauses and slow_clauses:
        fast_where = "WHERE " + " AND ".join(fast_clauses)
        slow_where = "WHERE " + " AND ".join(slow_clauses)
        cte = f"WITH base AS MATERIALIZED (SELECT * FROM meals {fast_where})"
        count_sql = f"{cte} SELECT COUNT(*) FROM base {slow_where}"
        data_sql = (
            f"{cte} SELECT {_SELECT_COLS} "
            f"FROM base {slow_where} {order_sql} "
            f"LIMIT {PAGE_SIZE} OFFSET {offset}"
        )
    else:
        all_clauses = fast_clauses + slow_clauses
        where_sql = ("WHERE " + " AND ".join(all_clauses)) if all_clauses else ""
        count_sql = f"SELECT COUNT(*) FROM meals {where_sql}"
        data_sql = (
            f"SELECT {_SELECT_COLS} "
            f"FROM meals {where_sql} {order_sql} "
            f"LIMIT {PAGE_SIZE} OFFSET {offset}"
        )

    return count_sql, data_sql, params


# ── 엔드포인트 ──────────────────────────────────────────────
@app.get("/api/meals", response_model=MealsResponse)
async def search_meals(
    school: Optional[str] = Query(None),
    school_code: Optional[str] = Query(None),
    dish: Optional[str] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    years: list[int] = Query(default=[]),
    sort: str = Query("meal_date"),
    order: Literal["asc", "desc", "default"] = Query("default"),
    page: int = Query(1, ge=1),
):
    if not school and not school_code and not dish and month is None:
        raise HTTPException(400, "학교명, 요리명, 월 중 하나 이상 입력해야 합니다.")
    if sort not in SORTABLE:
        raise HTTPException(400, f"정렬 불가 컬럼: {sort}")

    sort_dir = "ASC" if order == "asc" else ("DESC" if order == "desc" else "ASC")
    count_sql, data_sql, params = _build_query(
        school, school_code, dish, month, years, sort, sort_dir, page
    )

    conn = await _get_conn()
    try:
        total = await conn.fetchval(count_sql, *params)
        rows = await conn.fetch(data_sql, *params)
    finally:
        await conn.close()

    data = [
        MealRow(
            id=r["id"], region=r["region"], school_name=r["school_name"],
            meal_date=r["meal_date"].isoformat(), meal_type=r["meal_type"],
            soup=r["soup"], main_dish=r["main_dish"], side1=r["side1"],
            dessert=r["dessert"], menu_full=r["menu_full"], search_key=r["search_key"],
        )
        for r in rows
    ]
    return MealsResponse(total=total, page=page, page_size=PAGE_SIZE, data=data)


@app.get("/api/schools", response_model=list[SchoolItem])
async def list_schools(
    q: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
):
    conn = await _get_conn()
    try:
        rows = await conn.fetch(
            "SELECT DISTINCT school_name, school_code, region FROM meals ORDER BY school_name"
        )
    finally:
        await conn.close()

    schools = [{"school_name": r["school_name"], "school_code": r["school_code"], "region": r["region"]} for r in rows]
    if not q:
        return schools[:limit]
    q_lower = q.lower()
    return [s for s in schools if q_lower in s["school_name"].lower()][:limit]


@app.get("/api/health")
async def health():
    return {"status": "ok"}
