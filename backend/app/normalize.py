"""
메뉴 파싱 및 정규화 유틸
"""
import re
from datetime import date
from typing import Optional


def normalize_menu_full(raw: str) -> str:
    """DDISH_NM의 <br/>, <br /> → ", " 치환"""
    return re.sub(r"<br\s*/?>", ", ", raw or "").strip().rstrip(", ")


def build_search_key(menu_full: str) -> str:
    """소문자, 공백/NBSP/탭 제거, 괄호 내부 제거, NEIS 마커 제거"""
    text = menu_full.lower()
    text = re.sub(r"\(.*?\)", "", text)           # 괄호 내부 제거
    text = re.sub(r"[\s\u00a0\t]", "", text)      # 공백/NBSP/탭
    text = re.sub(r"[a-z0-9.*☆△★]+(?=,|$)", "", text)  # 각 항목 끝 마커 제거
    text = re.sub(r"(?<=,)[*☆△★]+", "", text)         # 각 항목 앞 마커 제거 (쉼표 뒤)
    text = re.sub(r"^[*☆△★]+", "", text)               # 첫 항목 앞 마커 제거
    return text


def parse_dishes(menu_full: str) -> dict[str, Optional[str]]:
    """
    menu_full (comma-separated)을 분해해 soup/main_dish/side1/dessert 반환.

    규칙:
      items = comma split 후 각 항목 정리 (괄호 정보 제거, 공백 정리)
      body  = items[1:]  (첫 번째 밥류 제외)
      soup      = body[0] if len(body) >= 1
      main_dish = body[1] if len(body) >= 2
      side1     = body[2] if len(body) >= 3
      dessert   = body[-1] if len(body) >= 4  (마지막, 4개 이상일 때만)
    """
    if not menu_full:
        return {"soup": None, "main_dish": None, "side1": None, "dessert": None}

    raw_items = [_clean_item(i) for i in menu_full.split(", ")]
    items = [i for i in raw_items if i]  # 빈 항목 제거

    body = items[1:]  # 밥류 제외

    return {
        "soup":      body[0] if len(body) >= 1 else None,
        "main_dish": body[1] if len(body) >= 2 else None,
        "side1":     body[2] if len(body) >= 3 else None,
        "dessert":   body[-1] if len(body) >= 4 else None,
    }


def _clean_item(item: str) -> str:
    """
    VBA CleanDishNameKeepInnerSymbols 동일 로직 + NEIS 마커 제거:
      1) " (" (공백+여는괄호) 이후 전체 제거
      2) 남은 문자열에서 "(" 이후 전체 제거
      3) 끝에 붙는 NEIS 표시 마커 제거
         - 영문자 (k=알레르기, s 등)
         - * (원산지·GMO 표시)
         - ☆ (친환경 식재료), △, ★
    """
    s = item.strip()
    # 1단계: " (" 기준 절단
    idx = s.find(" (")
    if idx >= 0:
        s = s[:idx]
    # 2단계: "(" 기준 절단 (붙어있는 경우)
    idx = s.find("(")
    if idx >= 0:
        s = s[:idx]
    # 중간 정리: 공백 제거 후 마커 제거 (공백이 남으면 regex가 못 잡음)
    s = s.strip()
    # 3단계: 끝 마커 제거 (영문, *, ☆, △, ★, 숫자, 마침표)
    s = re.sub(r"[a-zA-Z0-9.*☆△★]+$", "", s)
    # 4단계: 앞 마커 제거 (*바지락살미역국 → 바지락살미역국)
    s = re.sub(r"^[*☆△★]+", "", s)
    return s.strip()


def parse_meal_date(raw: str) -> date:
    """YYYYMMDD → datetime.date"""
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def parse_meal_type(sc_nm: Optional[str], sc_code: Optional[str]) -> str:
    """MMEAL_SC_NM 우선, 없으면 코드 매핑"""
    if sc_nm:
        return sc_nm
    mapping = {"1": "조식", "2": "중식", "3": "석식"}
    return mapping.get(str(sc_code), "기타")
