"""
NEIS 급식 데이터 수집 및 Supabase upsert
실행: uv run python -m app.ingest [--region B10] [--limit 1]
"""
import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import asyncpg
import httpx
import structlog
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.logging_config import setup_logging
from app.normalize import (
    build_search_key,
    normalize_menu_full,
    parse_dishes,
    parse_meal_date,
    parse_meal_type,
)

load_dotenv(Path(__file__).parent.parent / ".env")
setup_logging(module="ingest")
logger = structlog.get_logger(__name__)

# ── 설정 ────────────────────────────────────────────────────
API_KEY   = os.environ["NEIS_API_KEY"]
BASE_URL  = os.getenv("NEIS_BASE_URL", "https://open.neis.go.kr/hub")
from datetime import date as _date, timedelta as _timedelta
_yesterday = (_date.today() - _timedelta(days=1)).strftime("%Y%m%d")
YEAR_FROM = os.getenv("NEIS_YEAR_FROM", "20230101")
YEAR_TO   = os.getenv("NEIS_YEAR_TO",   _yesterday)
PAGE_SIZE = 1000
RETRY_MAX = 3
RETRY_DELAY = 2.0  # seconds

REGIONS = {
    "B10": "서울",
    "C10": "부산",
    "D10": "대구",
    "E10": "인천",
    "J10": "경기",
}


# ── NEIS API 호출 ─────────────────────────────────────────────

async def _neis_get(
    client: httpx.AsyncClient,
    endpoint: str,
    params: dict,
    job_id: str,
) -> list[dict]:
    """단일 페이지 요청, 재시도 포함"""
    params = {"KEY": API_KEY, "Type": "json", "pSize": PAGE_SIZE, **params}
    url = f"{BASE_URL}/{endpoint}"

    for attempt in range(1, RETRY_MAX + 1):
        t0 = time.monotonic()
        try:
            resp = await client.get(url, params=params, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            duration_ms = int((time.monotonic() - t0) * 1000)

            # NEIS 오류 응답 처리
            if endpoint in body:
                head = body[endpoint][0]["head"]
                code = head[1]["RESULT"]["CODE"]
                if code not in ("INFO-000", "INFO-200"):
                    logger.warning(
                        "neis_api_warn",
                        job_id=job_id,
                        endpoint=endpoint,
                        code=code,
                        message=head[1]["RESULT"]["MESSAGE"],
                        duration_ms=duration_ms,
                    )
                    return []
                total = head[0]["list_total_count"]
                rows  = body[endpoint][1]["row"]
                logger.debug(
                    "neis_api_ok",
                    job_id=job_id,
                    endpoint=endpoint,
                    row_count=len(rows),
                    total=total,
                    duration_ms=duration_ms,
                )
                return rows
            # 데이터 없음 (NEIS: {"RESULT": {"CODE":"INFO-200"...}})
            return []

        except Exception as exc:
            logger.warning(
                "neis_api_retry",
                job_id=job_id,
                endpoint=endpoint,
                attempt=attempt,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            if attempt == RETRY_MAX:
                logger.error(
                    "neis_api_failed",
                    job_id=job_id,
                    endpoint=endpoint,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return []
            await asyncio.sleep(RETRY_DELAY * attempt)
    return []


async def fetch_schools(
    client: httpx.AsyncClient,
    region_code: str,
    job_id: str,
) -> list[dict]:
    """schoolInfo API로 초·중·고등학교 목록 수집"""
    schools: list[dict] = []
    for school_type in ("초등학교", "중학교", "고등학교"):
        page = 1
        while True:
            rows = await _neis_get(
                client,
                "schoolInfo",
                {
                    "ATPT_OFCDC_SC_CODE": region_code,
                    "SCHUL_KND_SC_NM": school_type,
                    "pIndex": page,
                },
                job_id,
            )
            if not rows:
                break
            schools.extend(rows)
            if len(rows) < PAGE_SIZE:
                break
            page += 1

    logger.info(
        "schools_fetched",
        job_id=job_id,
        region_code=region_code,
        school_count=len(schools),
    )
    return schools


async def fetch_meals(
    client: httpx.AsyncClient,
    region_code: str,
    school_code: str,
    job_id: str,
) -> list[dict]:
    """mealServiceDietInfo API로 급식 데이터 수집"""
    meals: list[dict] = []
    page = 1
    while True:
        rows = await _neis_get(
            client,
            "mealServiceDietInfo",
            {
                "ATPT_OFCDC_SC_CODE": region_code,
                "SD_SCHUL_CODE": school_code,
                "MLSV_FROM_YMD": YEAR_FROM,
                "MLSV_TO_YMD": YEAR_TO,
                "pIndex": page,
            },
            job_id,
        )
        if not rows:
            break
        meals.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        page += 1
    return meals


# ── DB upsert ────────────────────────────────────────────────

UPSERT_SQL = """
INSERT INTO meals (
    region, region_code, school_name, school_code,
    meal_date, meal_type, menu_full, search_key,
    soup, main_dish, side1, dessert,
    meal_month, meal_year
)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
ON CONFLICT (school_code, meal_date, meal_type, menu_full)
DO NOTHING
"""


def _build_record(
    region: str,
    region_code: str,
    school_name: str,
    school_code: str,
    row: dict,
) -> Optional[tuple]:
    try:
        menu_full  = normalize_menu_full(row.get("DDISH_NM", ""))
        if not menu_full:
            return None
        search_key = build_search_key(menu_full)
        meal_date  = parse_meal_date(row["MLSV_YMD"])
        meal_type  = parse_meal_type(row.get("MMEAL_SC_NM"), row.get("MMEAL_SC_CODE"))
        dishes     = parse_dishes(menu_full)
        return (
            region, region_code, school_name, school_code,
            meal_date, meal_type, menu_full, search_key,
            dishes["soup"], dishes["main_dish"], dishes["side1"], dishes["dessert"],
            meal_date.month, meal_date.year,
        )
    except Exception as exc:
        logger.warning(
            "record_build_error",
            error_type=type(exc).__name__,
            error_message=str(exc),
            row=row,
        )
        return None


async def upsert_meals(
    conn: asyncpg.Connection,
    records: list[tuple],
    job_id: str,
) -> int:
    if not records:
        return 0
    t0 = time.monotonic()
    await conn.executemany(UPSERT_SQL, records)
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "upsert_ok",
        job_id=job_id,
        row_count=len(records),
        duration_ms=duration_ms,
    )
    return len(records)


# ── 메인 ────────────────────────────────────────────────────

async def ingest_region(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    region_code: str,
    job_id: str,
    school_limit: Optional[int] = None,
) -> dict:
    region_name = REGIONS[region_code]
    failed_schools: list[str] = []
    total_upserted = 0

    schools = await fetch_schools(client, region_code, job_id)
    if school_limit:
        schools = schools[:school_limit]

    for school in schools:
        school_name = school["SCHUL_NM"]
        school_code = school["SD_SCHUL_CODE"]
        log = logger.bind(
            job_id=job_id,
            region=region_name,
            region_code=region_code,
            school=school_name,
            school_code=school_code,
        )
        try:
            meals = await fetch_meals(client, region_code, school_code, job_id)
            log.info("meals_fetched", row_count=len(meals))

            if not meals:
                continue

            records = [
                r for row in meals
                if (r := _build_record(region_name, region_code, school_name, school_code, row))
            ]
            upserted = await upsert_meals(conn, records, job_id)
            total_upserted += upserted

        except Exception as exc:
            log.error(
                "school_ingest_failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            failed_schools.append(school_code)

    return {
        "region": region_name,
        "school_count": len(schools),
        "upserted": total_upserted,
        "failed": failed_schools,
    }


async def main(
    regions: Optional[list[str]] = None,
    school_limit: Optional[int] = None,
) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("missing_env", error_message="DATABASE_URL not set")
        sys.exit(1)

    job_id = uuid.uuid4().hex[:8]
    target_regions = regions or list(REGIONS.keys())

    logger.info(
        "ingest_start",
        job_id=job_id,
        regions=target_regions,
        year_from=YEAR_FROM,
        year_to=YEAR_TO,
        school_limit=school_limit,
    )

    conn = await asyncpg.connect(dsn)
    async with httpx.AsyncClient() as client:
        try:
            for region_code in target_regions:
                if region_code not in REGIONS:
                    logger.warning("unknown_region", region_code=region_code)
                    continue
                result = await ingest_region(conn, client, region_code, job_id, school_limit)
                logger.info("region_done", job_id=job_id, **result)
                if result["failed"]:
                    logger.error(
                        "region_has_failures",
                        job_id=job_id,
                        region=result["region"],
                        failed_schools=result["failed"],
                    )
        finally:
            await conn.close()

    logger.info("ingest_complete", job_id=job_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NEIS 급식 데이터 수집")
    parser.add_argument(
        "--region",
        nargs="+",
        choices=list(REGIONS.keys()),
        help="수집할 지역 코드 (예: B10 C10). 미지정 시 전체",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="지역당 수집할 최대 학교 수 (테스트용)",
    )
    args = parser.parse_args()
    asyncio.run(main(regions=args.region, school_limit=args.limit))
