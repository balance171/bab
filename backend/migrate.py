"""
마이그레이션 실행기
사용법: uv run python migrate.py [--rollback]
"""
import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

import asyncpg
import structlog
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from app.logging_config import setup_logging

load_dotenv(Path(__file__).parent / ".env")
setup_logging(module="api")
logger = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        logger.error(
            "missing_env",
            step="migrate",
            error_message="DATABASE_URL 환경변수가 설정되지 않았습니다.",
        )
        sys.exit(1)
    return dsn


async def run_migration(sql_file: Path, conn: asyncpg.Connection) -> None:
    sql = sql_file.read_text(encoding="utf-8")
    logger.info("migration_start", step="migrate", file=sql_file.name)
    try:
        await conn.execute(sql)
        logger.info("migration_ok", step="migrate", file=sql_file.name)
    except Exception as exc:
        logger.error(
            "migration_failed",
            step="migrate",
            file=sql_file.name,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise


async def verify(conn: asyncpg.Connection) -> None:
    """마이그레이션 결과 검증"""
    # 테이블 존재 확인
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'meals')"
    )
    logger.info("verify_table", step="verify", table="meals", exists=exists)
    assert exists, "meals 테이블이 존재하지 않습니다."

    # pg_trgm 확장 확인
    trgm = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')"
    )
    logger.info("verify_extension", step="verify", extension="pg_trgm", exists=trgm)
    assert trgm, "pg_trgm 확장이 활성화되지 않았습니다."

    # 인덱스 확인
    indexes = await conn.fetch(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'meals'"
    )
    index_names = {row["indexname"] for row in indexes}
    required = {
        "idx_meals_meal_date",
        "idx_meals_region",
        "idx_meals_school_code",
        "idx_meals_school_name_trgm",
        "idx_meals_search_key_trgm",
    }
    missing = required - index_names
    logger.info("verify_indexes", step="verify", found=list(index_names), missing=list(missing))
    assert not missing, f"누락된 인덱스: {missing}"

    # RLS 확인
    rls = await conn.fetchval(
        "SELECT relrowsecurity FROM pg_class WHERE relname = 'meals'"
    )
    logger.info("verify_rls", step="verify", rls_enabled=rls)
    assert rls, "RLS가 활성화되지 않았습니다."

    # 샘플 upsert
    await conn.execute(
        """
        INSERT INTO meals (region, region_code, school_name, school_code,
                           meal_date, meal_type, menu_full, search_key)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (school_code, meal_date, meal_type, menu_full) DO NOTHING
        """,
        "서울", "B10", "테스트고등학교", "TEST0001",
        date(2025, 3, 14), "중식", "쌀밥, 된장국, 불고기, 김치, 과일",
        "쌀밥된장국불고기김치과일",
    )

    # 샘플 select
    row = await conn.fetchrow(
        "SELECT school_name, meal_date, menu_full FROM meals WHERE school_code = $1",
        "TEST0001",
    )
    logger.info("verify_sample_select", step="verify", row=dict(row) if row else None)
    assert row is not None, "샘플 데이터 SELECT 실패"

    # 정리 (테스트 데이터 삭제)
    await conn.execute("DELETE FROM meals WHERE school_code = $1", "TEST0001")
    logger.info("verify_cleanup", step="verify", school_code="TEST0001")

    logger.info("verify_all_passed", step="verify", result="✅ 모든 검증 통과")


async def main(rollback: bool = False) -> None:
    dsn = _get_dsn()
    conn = await asyncpg.connect(dsn)
    try:
        if rollback:
            logger.info("rollback_start", step="migrate")
            await conn.execute("DROP TABLE IF EXISTS meals CASCADE;")
            logger.info("rollback_ok", step="migrate")
        else:
            migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
            for f in migration_files:
                await run_migration(f, conn)
            await verify(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true", help="meals 테이블 삭제")
    args = parser.parse_args()
    asyncio.run(main(rollback=args.rollback))
