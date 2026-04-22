"""급식 관리 시스템 — 메인 진입점 (로그인 페이지)"""
import streamlit as st
from utils.config import APP_NAME, SCHOOL_NAME, validate_env
from utils.auth import login, logout, current_user

st.set_page_config(
    page_title=f"{SCHOOL_NAME} 급식 관리",
    page_icon="🍱",
    layout="centered",
    initial_sidebar_state="auto",
)

# ── 환경변수 경고 ────────────────────────────────────────
missing = validate_env()
if missing:
    st.error(f"⚠️ 환경변수 누락: {', '.join(missing)}\n\n`.env.example`을 참고해 `.env` 파일을 생성하세요.")
    st.stop()

# ── 사이드바 내비게이션 ──────────────────────────────────
user = current_user()
if user:
    with st.sidebar:
        st.markdown(f"**{user['name']}** 선생님")
        st.caption(f"권한: {'관리자' if user['role'] == 'admin' else '배식 교사'}")
        st.divider()
        if st.button("🚪 로그아웃", use_container_width=True):
            logout()
            st.rerun()

# ── 로그인 폼 ────────────────────────────────────────────
if not user:
    st.title(f"🍱 {APP_NAME}")
    st.subheader(SCHOOL_NAME)
    st.divider()

    with st.form("login_form"):
        email = st.text_input("이메일", placeholder="teacher@school.kr")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", use_container_width=True)

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

    st.info("💡 계정이 없으면 급식 담당 선생님께 문의하세요.")

else:
    # 로그인 상태 → 메인 화면
    st.title(f"🍱 {APP_NAME}")
    st.subheader(f"안녕하세요, **{user['name']}** 선생님!")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/01_학생관리.py", label="👨‍🎓 학생 관리", use_container_width=True)
        st.page_link("pages/02_QR생성.py",  label="📱 QR 생성 / 학생증 출력", use_container_width=True)
    with col2:
        st.page_link("pages/03_체크인.py",  label="✅ 급식 체크인", use_container_width=True)
        st.page_link("pages/04_대시보드.py", label="📊 실시간 대시보드", use_container_width=True)
    with col3:
        st.page_link("pages/05_AI분석.py",  label="🤖 AI 데이터 분석", use_container_width=True)

    st.divider()
    st.caption("좌측 사이드바에서도 메뉴를 탐색할 수 있습니다.")
