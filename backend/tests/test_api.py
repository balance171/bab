"""
STEP 5 API 통합 테스트
실행: uv run pytest tests/test_api.py -v
"""
import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

load_dotenv(Path(__file__).parent.parent / ".env")

from app.main import app

BASE = "http://test"


@pytest_asyncio.fixture(scope="session")
async def client():
    from app.db import close_pool, init_pool
    await init_pool()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        yield c
    await close_pool()


# ── 헬스 체크 ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── 빈 조건 → 400 ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_conditions(client):
    r = await client.get("/api/meals")
    assert r.status_code == 400
    assert "하나 이상" in r.json()["detail"]


# ── 잘못된 정렬 컬럼 → 400 ───────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_sort(client):
    r = await client.get("/api/meals?school=가락&sort=password")
    assert r.status_code == 400
    assert "정렬 불가" in r.json()["detail"]


# ── 월 범위 오류 → 422 ────────────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_month(client):
    r = await client.get("/api/meals?month=13")
    assert r.status_code == 422


# ── 학교명 검색 ───────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_by_school(client):
    r = await client.get("/api/meals?school=가락")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    assert all("가락" in row["school_name"] for row in body["data"])
    assert body["page"] == 1
    assert body["page_size"] == 50


# ── 요리명 검색 (search_key 기반) ─────────────────────────────
@pytest.mark.asyncio
async def test_search_by_dish(client):
    r = await client.get("/api/meals?dish=된장국")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    # search_key는 소문자+공백제거이므로 "된장국" 포함 여부 확인
    for row in body["data"]:
        assert "된장" in row["menu_full"]


# ── 월 필터 ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_by_month(client):
    r = await client.get("/api/meals?school=가락&month=3")
    assert r.status_code == 200
    body = r.json()
    for row in body["data"]:
        assert row["meal_date"][5:7] == "03"


# ── 페이지네이션 ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_pagination(client):
    r1 = await client.get("/api/meals?school=가락&page=1")
    r2 = await client.get("/api/meals?school=가락&page=2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    ids1 = {row["id"] for row in r1.json()["data"]}
    ids2 = {row["id"] for row in r2.json()["data"]}
    # 페이지가 다르면 ID 겹치지 않아야 함
    assert ids1.isdisjoint(ids2)


# ── 정렬 ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_sort_desc(client):
    r = await client.get("/api/meals?school=가락&sort=meal_date&order=desc")
    assert r.status_code == 200
    dates = [row["meal_date"] for row in r.json()["data"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_sort_asc(client):
    r = await client.get("/api/meals?school=가락&sort=meal_date&order=asc")
    assert r.status_code == 200
    dates = [row["meal_date"] for row in r.json()["data"]]
    assert dates == sorted(dates)


# ── 빈 결과 ──────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_result(client):
    r = await client.get("/api/meals?school=존재하지않는학교명xyz999")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["data"] == []
