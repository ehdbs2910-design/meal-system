"""급식 관리 시스템 — 메인 진입점 (급식 체크인)"""
import streamlit as st
from datetime import date

from utils.config import APP_NAME, SCHOOL_NAME, validate_env
from utils.auth import login, logout, current_user
from utils.db import get_service_client, safe_query, record_meal_checkin
from utils.qr_utils import verify_token
from components.qr_scanner import qr_scanner

st.set_page_config(
    page_title=f"{SCHOOL_NAME} 급식 체크인",
    page_icon="✅",
    layout="centered",
    initial_sidebar_state="auto",
)

# ── 환경변수 검증 ────────────────────────────────────────
missing = validate_env()
if missing:
    st.error(f"⚠️ 환경변수 누락: {', '.join(missing)}")
    st.stop()


ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두",
    "15": "닭고기", "16": "쇠고기", "17": "오징어", "18": "조개류",
}


# ── DB 헬퍼 ───────────────────────────────────────────────

def get_student_by_id(student_id: str):
    return safe_query(
        lambda: get_service_client()
            .table("students").select("*")
            .eq("id", student_id).eq("is_active", True)
            .single().execute(),
        "학생 조회 실패"
    )


def get_student_by_number(student_number: str):
    return safe_query(
        lambda: get_service_client()
            .table("students").select("*")
            .eq("student_number", student_number).eq("is_active", True)
            .single().execute(),
        "학생 조회 실패"
    )


def checkin_and_show(student: dict):
    user = current_user()
    allergies = student.get("allergies") or []
    roll = student.get("class_roll_number")
    roll_str = f" {roll}번" if roll else ""
    label = f"**{student['name']}** ({student['grade']}학년 {student['class_number']}반{roll_str})"

    _, err = record_meal_checkin(
        student_id=student["id"],
        checked_by=user["id"] if user else None,
        device_info="web",
    )

    if err and "이미" in err:
        st.warning(f"⚠️ {label} — 이미 수령했습니다.")
    elif err:
        st.error(f"❌ {label} — {err}")
    else:
        if allergies:
            labels = [f"{c}.{ALLERGY_MAP.get(c, c)}" for c in allergies]
            st.error(f"⚠️ 알레르기 주의: {', '.join(labels)}")
        st.success(f"✅ {label} — 수령 완료!")


# ════════════════════════════════════════════════════════════
# 사이드바: 관리자 로그인 / 메뉴
# ════════════════════════════════════════════════════════════
user = current_user()

with st.sidebar:
    if user:
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
        if st.button("🚪 로그아웃", use_container_width=True):
            logout()
            st.rerun()
    else:
        with st.expander("🔐 관리자 로그인"):
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


# ════════════════════════════════════════════════════════════
# 메인: 체크인 UI
# ════════════════════════════════════════════════════════════

st.markdown(
    f"<div style='display:flex;justify-content:space-between;align-items:center;"
    f"margin-bottom:8px;'>"
    f"<h4 style='margin:0;'>✅ 급식 체크인</h4>"
    f"<span style='color:#888;font-size:13px;'>{date.today().strftime('%Y-%m-%d')}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

tab_qr, tab_manual = st.tabs(["📷 QR 스캔", "⌨️ 수동 입력"])

# ── 탭1: QR 스캔 ──────────────────────────────────────────
with tab_qr:
    qr_result = qr_scanner(key="qr_scanner")

    if qr_result and st.session_state.get("last_qr") != qr_result:
        st.session_state["last_qr"] = qr_result
        student_id = verify_token(qr_result)
        if not student_id:
            st.error("❌ 유효하지 않은 QR 코드입니다.")
        else:
            student, err = get_student_by_id(student_id)
            if err or not student:
                st.error("❌ 학생 정보를 찾을 수 없습니다.")
            else:
                checkin_and_show(student)


# ── 탭2: 수동 입력 ────────────────────────────────────────
with tab_manual:
    st.caption("QR 스캔이 어려울 때 학번으로 직접 조회합니다.")

    with st.form("manual_form", clear_on_submit=True):
        student_number = st.text_input("학번 입력", placeholder="예: 20240101", max_chars=20)
        submitted = st.form_submit_button("✅ 체크인", use_container_width=True, type="primary")

    if submitted and student_number.strip():
        student, err = get_student_by_number(student_number.strip())
        if err or not student:
            st.error("❌ 해당 학번의 학생을 찾을 수 없습니다.")
        else:
            checkin_and_show(student)


# ── 하단: 관리자 로그인 / 상태 표시 ──────────────────────
st.divider()
if user:
    cols = st.columns([3, 1])
    cols[0].caption(f"👤 {user['name']} 선생님으로 로그인됨 — 좌측 사이드바에서 메뉴 이용")
    if cols[1].button("로그아웃", use_container_width=True):
        logout()
        st.rerun()
else:
    with st.expander("🔐 관리자 로그인"):
        with st.form("login_form_main"):
            email = st.text_input("이메일", placeholder="teacher@school.kr")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")
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
