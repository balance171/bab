"""
Vercel Serverless Function — 순수 Python + psycopg2
/api/* 요청을 처리
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import psycopg2
import psycopg2.extras

DEFAULT_PAGE_SIZE = 30
MAX_PAGE_SIZE = 200

SORTABLE = {
    "meal_date", "meal_year", "school_name", "region",
    "meal_type", "soup", "main_dish", "side1", "dessert", "search_key",
}

SELECT_COLS = (
    "id, region, school_name, meal_date, meal_type, "
    "soup, main_dish, side1, dessert, menu_full, search_key"
)


def _build_search_key(text):
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[\s\u00a0\t]", "", text)
    text = re.sub(r"[a-z0-9.*#☆△★]+(?=,|$)", "", text)
    text = re.sub(r"(?<=,)[*#☆△★]+", "", text)
    text = re.sub(r"^[*#☆△★]+", "", text)
    return text


def _get_conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise Exception("DATABASE_URL not configured")
    conn = psycopg2.connect(dsn)
    conn.cursor().execute("SET statement_timeout = '25000'")  # 25초 (Vercel 30초 제한 내)
    return conn


def _json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _handle_meals(handler, params):
    school = params.get("school", [None])[0]
    school_code = params.get("school_code", [None])[0]
    dish = params.get("dish", [None])[0]
    month_str = params.get("month", [None])[0]
    month = int(month_str) if month_str else None
    months_list = [int(m) for m in params.get("months", [])]
    years = [int(y) for y in params.get("years", [])]
    school_types = params.get("school_types", [])
    sort = params.get("sort", ["meal_date"])[0]
    order = params.get("order", ["default"])[0]
    page_str = params.get("page", ["1"])[0]
    page = max(1, int(page_str))
    ps_str = params.get("page_size", [str(DEFAULT_PAGE_SIZE)])[0]
    page_size = min(MAX_PAGE_SIZE, max(1, int(ps_str)))

    if not school and not school_code and not dish and month is None and not months_list:
        return _json_response(handler, {"detail": "학교명, 요리명, 월 중 하나 이상 입력해야 합니다."}, 400)

    if sort not in SORTABLE:
        sort = "meal_date"

    sort_dir = "ASC" if order == "asc" else ("DESC" if order == "desc" else "ASC")

    # 쿼리 빌더 — fast/slow 파라미터를 분리하여 CTE 순서 일치
    fast_clauses, slow_clauses = [], []
    fast_params, slow_params = [], []

    if school_code:
        fast_clauses.append("school_code = %s")
        fast_params.append(school_code)
    elif school:
        slow_clauses.append("school_name ILIKE %s")
        slow_params.append(f"%{school}%")

    if dish:
        normalized = _build_search_key(dish)
        slow_clauses.append("search_key LIKE %s")
        slow_params.append(f"%{normalized}%")

    if months_list:
        placeholders = ", ".join(["%s"] * len(months_list))
        fast_clauses.append(f"meal_month IN ({placeholders})")
        fast_params.extend(months_list)
    elif month:
        fast_clauses.append("meal_month = %s")
        fast_params.append(month)

    if years:
        placeholders = ", ".join(["%s"] * len(years))
        fast_clauses.append(f"meal_year IN ({placeholders})")
        fast_params.extend(years)

    if school_types:
        placeholders = ", ".join(["%s"] * len(school_types))
        # school_name LIKE '%초등학교%' 대신 school_name 끝 매칭
        type_clauses = " OR ".join(["school_name LIKE %s" for _ in school_types])
        slow_clauses.append(f"({type_clauses})")
        slow_params.extend([f"%{t}" for t in school_types])

    if sort == "meal_year":
        order_sql = f"ORDER BY meal_year {sort_dir}, meal_date ASC, id ASC"
    else:
        order_sql = f"ORDER BY meal_year DESC, {sort} {sort_dir}, id ASC"
    offset = (page - 1) * page_size

    # school_code가 있으면 소량 데이터이므로 CTE 없이 직접 WHERE
    # CTE는 month/year + text 대량 필터링에만 사용
    has_school_code = any("school_code" in c for c in fast_clauses)
    use_cte = fast_clauses and slow_clauses and not has_school_code

    if use_cte:
        fast_where = "WHERE " + " AND ".join(fast_clauses)
        slow_where = "WHERE " + " AND ".join(slow_clauses)
        cte = f"WITH base AS MATERIALIZED (SELECT * FROM meals {fast_where})"
        count_sql = f"{cte} SELECT COUNT(*) FROM base {slow_where}"
        data_sql = f"{cte} SELECT {SELECT_COLS} FROM base {slow_where} {order_sql} LIMIT {page_size} OFFSET {offset}"
        query_params = fast_params + slow_params
    else:
        all_clauses = fast_clauses + slow_clauses
        where_sql = ("WHERE " + " AND ".join(all_clauses)) if all_clauses else ""
        count_sql = f"SELECT COUNT(*) FROM meals {where_sql}"
        data_sql = f"SELECT {SELECT_COLS} FROM meals {where_sql} {order_sql} LIMIT {page_size} OFFSET {offset}"
        query_params = fast_params + slow_params

    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(count_sql, query_params)
        total = cur.fetchone()["count"]
        cur.execute(data_sql, query_params)
        rows = cur.fetchall()
    finally:
        conn.close()

    def _strip(v):
        """DB에 남아있는 끝 마커(#.*숫자 등) 실시간 제거"""
        if not v:
            return v
        return re.sub(r"[a-zA-Z0-9.*#☆△★]+$", "", v).strip() or v

    data = []
    for r in rows:
        data.append({
            "id": r["id"],
            "region": r["region"],
            "school_name": r["school_name"],
            "meal_date": str(r["meal_date"]),
            "meal_type": r["meal_type"],
            "soup": _strip(r["soup"]),
            "main_dish": _strip(r["main_dish"]),
            "side1": _strip(r["side1"]),
            "dessert": _strip(r["dessert"]),
            "menu_full": r["menu_full"],
            "search_key": re.sub(r"[0-9.*#☆△★]+(?=,|$)", "", r["search_key"] or ""),
        })

    return _json_response(handler, {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data,
    })


def _handle_schools(handler, params):
    q = params.get("q", [""])[0]
    limit = min(100, int(params.get("limit", ["20"])[0]))

    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT DISTINCT school_name, school_code, region FROM meals ORDER BY school_name")
        rows = cur.fetchall()
    finally:
        conn.close()

    schools = [dict(r) for r in rows]
    if q:
        q_lower = q.lower()
        schools = [s for s in schools if q_lower in s["school_name"].lower()]

    return _json_response(handler, schools[:limit])


def _handle_health(handler):
    return _json_response(handler, {"status": "ok"})


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/api/meals":
                _handle_meals(self, params)
            elif path == "/api/schools":
                _handle_schools(self, params)
            elif path == "/api/health":
                _handle_health(self)
            else:
                _json_response(self, {"detail": "Not found"}, 404)
        except Exception as e:
            _json_response(self, {"detail": str(e)}, 500)

    def log_message(self, format, *args):
        pass  # suppress logs
