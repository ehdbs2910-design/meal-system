"""Supabase 연결 및 공통 DB 유틸리티"""
from __future__ import annotations

import streamlit as st
from supabase import create_client, Client
from loguru import logger

from utils.config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY


@st.cache_resource
def get_client() -> Client:
    """anon key 클라이언트 (세션 기반 인증용)"""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase 설정이 없습니다. .env 파일을 확인하세요.")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@st.cache_resource
def get_service_client() -> Client:
    """service role 클라이언트 (RLS 우회 — 서버사이드 전용)"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("Supabase service key가 없습니다.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# ── 공통 쿼리 헬퍼 ────────────────────────────────────────

def safe_query(fn, error_msg: str = "데이터 조회 중 오류가 발생했습니다."):
    """DB 작업을 try-except로 감싸고 (data, error) 반환."""
    try:
        result = fn()
        return result.data, None
    except Exception as e:
        logger.error(f"DB 오류: {e}")
        return None, error_msg


def get_students(active_only: bool = True) -> tuple[list | None, str | None]:
    """전체 학생 목록 조회"""
    def _query():
        client = get_client()
        q = client.table("students").select("*").order("grade").order("class_number").order("student_number")
        if active_only:
            q = q.eq("is_active", True)
        return q.execute()
    return safe_query(_query, "학생 목록 조회 실패")


def get_today_meal_status() -> tuple[list | None, str | None]:
    """오늘 급식 수령 현황 뷰 조회"""
    def _query():
        return get_client().from_("v_today_meal_status").select("*").execute()
    return safe_query(_query, "오늘 급식 현황 조회 실패")


def get_class_stats() -> tuple[list | None, str | None]:
    """학년/반별 수령 통계 뷰 조회"""
    def _query():
        return get_client().from_("v_class_meal_stats").select("*").execute()
    return safe_query(_query, "학급별 통계 조회 실패")


def record_meal_checkin(
    student_id: str,
    checked_by: str | None = None,
    device_info: str | None = None,
    is_offline_sync: bool = False,
    meal_type: str = "lunch",
) -> tuple[dict | None, str | None]:
    """급식 수령 체크인 등록 (중복 시 에러 반환)"""
    def _query():
        return get_service_client().table("meal_records").insert({
            "student_id": student_id,
            "meal_type": meal_type,
            "checked_by": checked_by,
            "device_info": device_info,
            "is_offline_sync": is_offline_sync,
        }).execute()

    data, err = safe_query(_query, "체크인 등록 실패")
    if err:
        # UNIQUE 제약 위반이면 중복 메시지로 변환
        return None, "이미 오늘 급식을 수령한 학생입니다."
    return data, None


def get_meal_history(days: int = 30) -> tuple[list | None, str | None]:
    """최근 N일 급식 기록 조회 (분석용)"""
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=days)).isoformat()

    def _query():
        return (
            get_client()
            .table("meal_records")
            .select("*, students(grade, class_number, student_number)")
            .gte("meal_date", start)
            .order("meal_date")
            .execute()
        )
    return safe_query(_query, f"최근 {days}일 기록 조회 실패")
