"""서울/경기 중학교 급식 수집 — 50건 배치 INSERT"""
import asyncio
import os
import sys
import time
from pathlib import Path

import httpx
import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from app.ingest import _neis_get, fetch_meals, _build_record, REGIONS, PAGE_SIZE

load_dotenv(Path(__file__).parent / ".env")
DSN = os.environ["DATABASE_URL"]

UPSERT_SQL = """INSERT INTO meals (
    region, region_code, school_name, school_code,
    meal_date, meal_type, menu_full, search_key,
    soup, main_dish, side1, dessert, meal_month, meal_year
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (school_code, meal_date, meal_type, menu_full) DO NOTHING"""

BATCH_SIZE = 50  # 50건씩 INSERT


def get_conn():
    c = psycopg2.connect(DSN, connect_timeout=10)
    c.autocommit = True
    cur = c.cursor()
    cur.execute("SET statement_timeout = '30000'")
    return c


def batch_insert(conn, records):
    """50건씩 나눠서 INSERT"""
    cur = conn.cursor()
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        try:
            cur.executemany(UPSERT_SQL, batch)
        except Exception as e:
            print(f"    batch {i}-{i+len(batch)} ERR: {e}", flush=True)
            # 연결 복구
            try:
                conn.close()
            except:
                pass
            time.sleep(2)
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.executemany(UPSERT_SQL, batch)
            except:
                pass  # skip this batch
    return conn


async def fetch_middle(client, rc):
    schools, page = [], 1
    while True:
        rows = await _neis_get(
            client, "schoolInfo",
            {"ATPT_OFCDC_SC_CODE": rc, "SCHUL_KND_SC_NM": "중학교", "pIndex": page},
            "mid",
        )
        if not rows:
            break
        schools.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        page += 1
    return schools


async def main():
    conn = get_conn()
    cur = conn.cursor()
    print("DB 연결 성공", flush=True)

    # ON CONFLICT DO NOTHING이 중복 처리 → 존재 체크 불필요
    async with httpx.AsyncClient() as client:
        for rc, rn in [("B10", "서울"), ("J10", "경기")]:
            schools = await fetch_middle(client, rc)
            print(f"{rn} 중학교: {len(schools)}개", flush=True)

            for i, s in enumerate(schools):
                name = s["SCHUL_NM"]
                code = s["SD_SCHUL_CODE"]

                # NEIS에서 급식 데이터 가져오기
                try:
                    meals = await fetch_meals(client, rc, code, "mid")
                    if not meals:
                        continue
                    records = [
                        r for row in meals
                        if (r := _build_record(rn, rc, name, code, row))
                    ]
                    if records:
                        conn = batch_insert(conn, records)
                        cur = conn.cursor()
                        print(f"  {name}: {len(records)}건", flush=True)
                except Exception as e:
                    print(f"  ERR {name}: {e}", flush=True)
                    try:
                        conn.close()
                    except:
                        pass
                    time.sleep(2)
                    conn = get_conn()
                    cur = conn.cursor()

                if (i + 1) % 50 == 0:
                    print(f"  === {rn} {i+1}/{len(schools)} ===", flush=True)

            print(f"{rn} 완료", flush=True)

    conn.close()
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
