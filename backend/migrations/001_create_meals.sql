-- ============================================================
-- 001_create_meals.sql
-- NEIS 급식 검색 시스템 — meals 테이블 초기 마이그레이션
-- ============================================================

-- 1. pg_trgm 확장 활성화 (trigram 인덱스 필요)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. meals 테이블 생성
CREATE TABLE IF NOT EXISTS meals (
    id              bigint          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    acquired_at     timestamptz     NOT NULL DEFAULT now(),

    -- 지역 정보
    region          text            NOT NULL,
    region_code     text            NOT NULL,

    -- 학교 정보
    school_name     text            NOT NULL,
    school_code     text            NOT NULL,

    -- 급식 기본 정보
    meal_date       date            NOT NULL,
    meal_type       text            NOT NULL,  -- 조식 / 중식 / 석식

    -- 메뉴 전체 (원본 파싱 결과, <br/> → ", " 치환)
    menu_full       text            NOT NULL,

    -- 검색 키 (소문자, 공백/괄호 제거)
    search_key      text            NOT NULL,

    -- 메뉴 분해
    soup            text,
    main_dish       text,
    side1           text,
    dessert         text
);

-- 3. 중복 방지 UNIQUE 제약
ALTER TABLE meals
    DROP CONSTRAINT IF EXISTS uq_meals_school_date_type_menu;

ALTER TABLE meals
    ADD CONSTRAINT uq_meals_school_date_type_menu
    UNIQUE (school_code, meal_date, meal_type, menu_full);

-- 4. btree 인덱스 (범위 검색용)
CREATE INDEX IF NOT EXISTS idx_meals_meal_date
    ON meals (meal_date);

CREATE INDEX IF NOT EXISTS idx_meals_region
    ON meals (region);

CREATE INDEX IF NOT EXISTS idx_meals_school_code
    ON meals (school_code);

-- 5. trigram 인덱스 (부분 일치 검색용)
CREATE INDEX IF NOT EXISTS idx_meals_school_name_trgm
    ON meals USING gin (school_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_meals_search_key_trgm
    ON meals USING gin (search_key gin_trgm_ops);

-- 6. RLS 활성화
ALTER TABLE meals ENABLE ROW LEVEL SECURITY;

-- 7. 공개 SELECT 허용 정책
DROP POLICY IF EXISTS "public_select" ON meals;

CREATE POLICY "public_select"
    ON meals
    FOR SELECT
    TO anon, authenticated
    USING (true);
