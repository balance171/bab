"""전국 중학교 급식 데이터 일괄 수집"""
import asyncio
import os
import sys
import time
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from app.ingest import (
    _neis_get, fetch_meals, _build_record, upsert_meals,
    REGIONS, PAGE_SIZE,
)
from app.logging_config import setup_logging
import structlog

load_dotenv(Path(__file__).parent / ".env")
setup_logging(module="ingest_middle")
logger = structlog.get_logger(__name__)

API_KEY = os.environ["NEIS_API_KEY"]


async def fetch_middle_schools(client, region_code, job_id):
    """중학교 목록만 수집"""
    schools = []
    page = 1
    while True:
        rows = await _neis_get(client, "schoolInfo", {
            "ATPT_OFCDC_SC_CODE": region_code,
            "SCHUL_KND_SC_NM": "중학교",
            "pIndex": page,
        }, job_id)
        if not rows:
            break
        schools.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        page += 1
    return schools


async def main():
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)
    job_id = "mid_all"
    t0 = time.monotonic()

    async with httpx.AsyncClient() as client:
        for region_code, region_name in REGIONS.items():
            schools = await fetch_middle_schools(client, region_code, job_id)
            logger.info("middle_schools", region=region_name, count=len(schools))

            for i, school in enumerate(schools):
                school_name = school["SCHUL_NM"]
                school_code = school["SD_SCHUL_CODE"]

                # 이미 데이터 있으면 건너뛰기
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM meals WHERE school_code = $1", school_code
                )
                if existing > 0:
                    continue

                try:
                    meals = await fetch_meals(client, region_code, school_code, job_id)
                    if not meals:
                        continue
                    records = [
                        r for row in meals
                        if (r := _build_record(region_name, region_code, school_name, school_code, row))
                    ]
                    await upsert_meals(conn, records, job_id)
                    if (i + 1) % 50 == 0:
                        logger.info("progress", region=region_name, done=i+1, total=len(schools))
                except Exception as e:
                    logger.error("school_error", school=school_name, error=str(e))

            logger.info("region_done", region=region_name)

    elapsed = int(time.monotonic() - t0)
    logger.info("all_done", elapsed_sec=elapsed)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
