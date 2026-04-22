"""인증 유틸리티 — Supabase Auth 연동"""
from __future__ import annotations

import streamlit as st
from loguru import logger

from utils.db import get_client, safe_query


def login(email: str, password: str) -> tuple[bool, str]:
    """이메일/비밀번호 로그인. (성공여부, 메시지) 반환."""
    try:
        client = get_client()
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        session = res.session

        # users 테이블에서 역할 조회
        profile, err = safe_query(
            lambda: client.table("users").select("*").eq("id", user.id).single().execute(),
            "사용자 정보 조회 실패"
        )
        if err or not profile:
            return False, "사용자 프로필을 찾을 수 없습니다. 관리자에게 문의하세요."

        st.session_state["user"] = {
            "id": user.id,
            "email": user.email,
            "name": profile["name"],
            "role": profile["role"],
            "access_token": session.access_token,
        }
        logger.info(f"로그인 성공: {email} (role={profile['role']})")
        return True, f"{profile['name']} 선생님, 환영합니다!"

    except Exception as e:
        logger.warning(f"로그인 실패: {email} — {e}")
        return False, "이메일 또는 비밀번호가 올바르지 않습니다."


def logout():
    """세션 초기화 및 Supabase 로그아웃"""
    try:
        get_client().auth.sign_out()
    except Exception:
        pass
    st.session_state.clear()
    logger.info("로그아웃")


def require_login():
    """로그인 상태 확인. 미로그인 시 로그인 페이지로 리다이렉트."""
    if "user" not in st.session_state:
        st.warning("로그인이 필요합니다.")
        st.page_link("app.py", label="로그인 페이지로 이동")
        st.stop()


def require_admin():
    """관리자 권한 확인. 권한 없으면 접근 차단."""
    require_login()
    if st.session_state["user"].get("role") != "admin":
        st.error("관리자 권한이 필요합니다.")
        st.stop()


def current_user() -> dict | None:
    """현재 로그인된 사용자 정보 반환."""
    return st.session_state.get("user")


def is_admin() -> bool:
    user = current_user()
    return user is not None and user.get("role") == "admin"
