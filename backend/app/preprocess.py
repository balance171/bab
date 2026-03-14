"""
전처리: meals 테이블의 soup/main_dish/side1/dessert NULL 행을 채움
실행: uv run python -m app.preprocess [--batch 500]
"""
import argparse
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

import asyncpg
import structlog
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from app.logging_config import setup_logging
from app.normalize import parse_dishes

load_dotenv(Path(__file__).parent.parent / ".env")
setup_logging(module="preprocess")
logger = structlog.get_logger(__name__)

UPDATE_SQL = """
UPDATE meals
SET soup      = $1,
    main_dish = $2,
    side1     = $3,
    dessert   = $4
WHERE id = $5
"""

COUNT_NULL_SQL = "SELECT COUNT(*) FROM meals WHERE soup IS NULL"
COUNT_TOTAL_SQL = "SELECT COUNT(*) FROM meals"

_SQL_NULL_ROWS = (
    "SELECT id, menu_full FROM meals WHERE soup IS NULL ORDER BY id LIMIT $1 OFFSET $2"
)
_SQL_ALL_ROWS = (
    "SELECT id, menu_full FROM meals ORDER BY id LIMIT $1 OFFSET $2"
)


async def _get_rows(
    conn: asyncpg.Connection,
    batch_size: int,
    offset: int,
    all_rows: bool,
) -> list[asyncpg.Record]:
    sql = _SQL_ALL_ROWS if all_rows else _SQL_NULL_ROWS
    return await conn.fetch(sql, batch_size, offset)


async def preprocess(
    conn: asyncpg.Connection,
    batch_size: int,
    job_id: str,
    all_rows: bool = False,
) -> dict:
    total_before = await conn.fetchval(COUNT_TOTAL_SQL)
    null_before  = await conn.fetchval(COUNT_NULL_SQL)
    logger.info(
        "preprocess_start",
        job_id=job_id,
        total_rows=total_before,
        null_before=null_before,
        mode="all" if all_rows else "null_only",
    )

    offset = 0
    total_updated = 0

    while True:
        rows = await _get_rows(conn, batch_size, offset, all_rows)
        if not rows:
            break

        records: list[tuple] = []
        for row in rows:
            dishes = parse_dishes(row["menu_full"])
            records.append((
                dishes["soup"],
                dishes["main_dish"],
                dishes["side1"],
                dishes["dessert"],
                row["id"],
            ))

        t0 = time.monotonic()
        await conn.executemany(UPDATE_SQL, records)
        duration_ms = int((time.monotonic() - t0) * 1000)

        total_updated += len(records)
        logger.info(
            "batch_updated",
            job_id=job_id,
            batch_size=len(records),
            total_updated=total_updated,
            offset=offset,
            duration_ms=duration_ms,
        )
        offset += batch_size

    null_after = await conn.fetchval(COUNT_NULL_SQL)
    fill_rate = round((1 - null_after / total_before) * 100, 2) if total_before else 0

    logger.info(
        "preprocess_complete",
        job_id=job_id,
        total_updated=total_updated,
        null_before=null_before,
        null_after=null_after,
        fill_rate_pct=fill_rate,
    )
    return {
        "total_rows": total_before,
        "null_before": null_before,
        "null_after": null_after,
        "total_updated": total_updated,
        "fill_rate_pct": fill_rate,
    }


async def main(batch_size: int = 500, all_rows: bool = False) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("missing_env", error_message="DATABASE_URL not set")
        sys.exit(1)

    job_id = uuid.uuid4().hex[:8]
    conn = await asyncpg.connect(dsn)
    try:
        result = await preprocess(conn, batch_size, job_id, all_rows=all_rows)
        logger.info("summary", job_id=job_id, **result)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="급식 메뉴 전처리")
    parser.add_argument("--batch", type=int, default=500, help="배치 크기 (기본 500)")
    parser.add_argument(
        "--all",
        action="store_true",
        help="이미 처리된 행 포함 전체 재전처리 (마커 제거 등 재적용 시 사용)",
    )
    args = parser.parse_args()
    asyncio.run(main(batch_size=args.batch, all_rows=args.all))
