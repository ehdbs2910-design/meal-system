-- ============================================================
-- 급식 관리 시스템 — Supabase PostgreSQL 스키마
-- Supabase 대시보드 > SQL Editor에서 순서대로 실행
-- ============================================================

-- ── 확장 기능 ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── 1. users (교사 계정) ───────────────────────────────────
-- Supabase Auth의 auth.users와 1:1 연동
CREATE TABLE IF NOT EXISTS public.users (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'staff' CHECK (role IN ('admin', 'staff')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.users IS '교사 계정 — Supabase Auth와 연동';
COMMENT ON COLUMN public.users.role IS 'admin: 급식 담당 선생님 / staff: 배식 선생님';

-- ── 2. students (학생 정보) ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.students (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_number  TEXT NOT NULL UNIQUE,   -- 학번 (예: 20240101)
    name            TEXT NOT NULL,
    grade           SMALLINT NOT NULL CHECK (grade BETWEEN 1 AND 3),
    class_number    SMALLINT NOT NULL CHECK (class_number BETWEEN 1 AND 20),
    allergies       TEXT[] DEFAULT '{}',    -- 알레르기 코드 배열 (1~18번)
    photo_url       TEXT,                   -- 선택사항
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_students_grade_class
    ON public.students(grade, class_number);
CREATE INDEX IF NOT EXISTS idx_students_student_number
    ON public.students(student_number);
CREATE INDEX IF NOT EXISTS idx_students_active
    ON public.students(is_active);

COMMENT ON TABLE public.students IS '학생 정보';
COMMENT ON COLUMN public.students.allergies IS '알레르기 유발 식품 번호 배열 (학교급식법 기준 1~18번)';

-- ── 3. meal_records (급식 수령 기록) ──────────────────────
CREATE TABLE IF NOT EXISTS public.meal_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id      UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    meal_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_type       TEXT NOT NULL DEFAULT 'lunch' CHECK (meal_type IN ('breakfast', 'lunch', 'dinner')),
    checkin_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checked_by      UUID REFERENCES public.users(id),  -- 체크인한 교사
    device_info     TEXT,                               -- 스캔 기기 정보
    is_offline_sync BOOLEAN NOT NULL DEFAULT FALSE,     -- 오프라인 동기화 여부
    UNIQUE(student_id, meal_date, meal_type)            -- 당일 중복 수령 방지
);

CREATE INDEX IF NOT EXISTS idx_meal_records_date
    ON public.meal_records(meal_date);
CREATE INDEX IF NOT EXISTS idx_meal_records_student_date
    ON public.meal_records(student_id, meal_date);
CREATE INDEX IF NOT EXISTS idx_meal_records_checkin_time
    ON public.meal_records(checkin_time);

COMMENT ON TABLE public.meal_records IS '급식 수령 기록 — (student_id, meal_date, meal_type) UNIQUE로 중복 방지';

-- ── 4. menus (일별 메뉴) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.menus (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    menu_date       DATE NOT NULL,
    meal_type       TEXT NOT NULL DEFAULT 'lunch' CHECK (meal_type IN ('breakfast', 'lunch', 'dinner')),
    items           TEXT[] NOT NULL DEFAULT '{}',       -- 메뉴 항목 목록
    allergy_info    TEXT[] DEFAULT '{}',                -- 해당 날 알레르기 번호
    calorie         INTEGER,                            -- kcal
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(menu_date, meal_type)
);

CREATE INDEX IF NOT EXISTS idx_menus_date
    ON public.menus(menu_date);

COMMENT ON TABLE public.menus IS '일별 급식 메뉴';

-- ── updated_at 자동 갱신 트리거 ────────────────────────────
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_students_updated_at
    BEFORE UPDATE ON public.students
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================

ALTER TABLE public.users        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.menus        ENABLE ROW LEVEL SECURITY;

-- 인증된 사용자만 접근 가능 (기본 정책)
CREATE POLICY "인증된 사용자만 조회" ON public.users
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "본인 정보 수정" ON public.users
    FOR UPDATE USING (auth.uid() = id);

-- students: 인증된 사용자 전체 조회 / 관리자만 수정
CREATE POLICY "인증된 사용자 학생 조회" ON public.students
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "관리자만 학생 추가" ON public.students
    FOR INSERT WITH CHECK (
        EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "관리자만 학생 수정" ON public.students
    FOR UPDATE USING (
        EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

CREATE POLICY "관리자만 학생 삭제" ON public.students
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

-- meal_records: 인증된 사용자 조회/추가
CREATE POLICY "인증된 사용자 급식기록 조회" ON public.meal_records
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "인증된 사용자 급식기록 추가" ON public.meal_records
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');

CREATE POLICY "관리자만 급식기록 삭제" ON public.meal_records
    FOR DELETE USING (
        EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

-- menus: 인증된 사용자 조회 / 관리자만 수정
CREATE POLICY "인증된 사용자 메뉴 조회" ON public.menus
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "관리자만 메뉴 관리" ON public.menus
    FOR ALL USING (
        EXISTS (SELECT 1 FROM public.users WHERE id = auth.uid() AND role = 'admin')
    );

-- ============================================================
-- 유용한 뷰 (Views)
-- ============================================================

-- 오늘 급식 현황 뷰
CREATE OR REPLACE VIEW public.v_today_meal_status AS
SELECT
    s.id,
    s.student_number,
    s.name,
    s.grade,
    s.class_number,
    s.allergies,
    mr.checkin_time,
    CASE WHEN mr.id IS NOT NULL THEN TRUE ELSE FALSE END AS has_received
FROM public.students s
LEFT JOIN public.meal_records mr
    ON s.id = mr.student_id
    AND mr.meal_date = CURRENT_DATE
    AND mr.meal_type = 'lunch'
WHERE s.is_active = TRUE;

-- 학년/반별 수령 통계 뷰
CREATE OR REPLACE VIEW public.v_class_meal_stats AS
SELECT
    s.grade,
    s.class_number,
    COUNT(DISTINCT s.id) AS total_students,
    COUNT(DISTINCT mr.student_id) AS received_count,
    COUNT(DISTINCT s.id) - COUNT(DISTINCT mr.student_id) AS not_received_count,
    ROUND(
        COUNT(DISTINCT mr.student_id)::NUMERIC / NULLIF(COUNT(DISTINCT s.id), 0) * 100, 1
    ) AS receipt_rate
FROM public.students s
LEFT JOIN public.meal_records mr
    ON s.id = mr.student_id
    AND mr.meal_date = CURRENT_DATE
    AND mr.meal_type = 'lunch'
WHERE s.is_active = TRUE
GROUP BY s.grade, s.class_number
ORDER BY s.grade, s.class_number;

-- ============================================================
-- 컬럼 추가 (기존 DB에 실행)
-- ============================================================
ALTER TABLE public.students
    ADD COLUMN IF NOT EXISTS class_roll_number SMALLINT CHECK (class_roll_number BETWEEN 1 AND 99);

COMMENT ON COLUMN public.students.class_roll_number IS '반 번호 (출석번호, 1~99)';

-- ============================================================
-- 초기 데이터: 테스트용 관리자 계정
-- ※ Supabase Auth에서 먼저 계정 생성 후 UUID를 아래에 입력
-- ============================================================
-- INSERT INTO public.users (id, email, name, role)
-- VALUES ('<auth.users UUID>', 'admin@school.kr', '급식담당교사', 'admin');
