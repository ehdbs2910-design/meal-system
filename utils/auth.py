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


def hide_auto_nav():
    """Streamlit이 자동 생성하는 사이드바 페이지 목록 숨김."""
    st.markdown(
        "<style>[data-testid='stSidebarNav']{display:none;}</style>",
        unsafe_allow_html=True,
    )


def render_sidebar_nav():
    """모든 페이지 공통 사이드바 — 로그인 사용자에게 메뉴 표시."""
    hide_auto_nav()
    user = current_user()
    with st.sidebar:
        st.page_link("app.py", label="🏠 홈 (체크인)")
        if user:
            st.divider()
            st.markdown(f"**{user['name']}** 선생님")
            st.caption(f"권한: {'관리자' if user['role'] == 'admin' else '배식 교사'}")
            st.divider()
            st.page_link("pages/01_학생관리.py", label="👨‍🎓 학생 관리")
            st.page_link("pages/02_QR생성.py",  label="📱 QR / 학생증")
            st.page_link("pages/04_대시보드.py", label="📊 대시보드")
            st.page_link("pages/05_AI분석.py",  label="🤖 AI 분석")
            if user.get("role") == "admin":
                st.page_link("pages/06_관리도구.py", label="🛠️ 관리 도구")
            st.divider()
            if st.button("🚪 로그아웃", use_container_width=True, key="sidebar_logout"):
                logout()
                st.rerun()
        else:
            st.divider()
            with st.expander("🔐 관리자 로그인"):
                with st.form("sidebar_login_form"):
                    email = st.text_input("이메일", placeholder="teacher@school.kr")
                    password = st.text_input("비밀번호", type="password")
                    submitted = st.form_submit_button("로그인", use_container_width=True,
                                                      type="primary")
                if submitted:
                    if not email or not password:
                        st.warning("이메일과 비밀번호를 입력해주세요.")
                    else:
                        with st.spinner("인증 중..."):
                            success, msg = login(email, password)
                        if success:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)


def require_login():
    """로그인 상태 확인. 미로그인 시 로그인 페이지로 리다이렉트."""
    hide_auto_nav()
    if "user" not in st.session_state:
        st.warning("로그인이 필요합니다.")
        st.page_link("app.py", label="🏠 홈으로 이동")
        st.stop()


def require_admin():
    """관리자 권한 확인. 권한 없으면 접근 차단."""
    hide_auto_nav()
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
