"""급식 관리 시스템 — 메인 진입점 (급식 체크인)"""
import streamlit as st
from datetime import date

from utils.config import APP_NAME, SCHOOL_NAME, validate_env
from utils.auth import current_user, render_sidebar_nav
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

# 자동 페이지 목록 숨김 (커스텀 page_link로만 제어)
st.markdown(
    "<style>[data-testid='stSidebarNav']{display:none;}</style>",
    unsafe_allow_html=True,
)


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

    _, err = record_meal_checkin(
        student_id=student["id"],
        checked_by=user["id"] if user else None,
        device_info="web",
    )

    status = "duplicate" if (err and "이미" in err) else ("error" if err else "ok")
    st.session_state["last_checkin"] = {
        "student_number": student["student_number"],
        "name": student["name"],
        "status": status,
        "error": err if status == "error" else None,
    }


render_sidebar_nav()
user = current_user()


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


def render_last_checkin():
    last = st.session_state.get("last_checkin")
    if not last:
        return
    box = (
        f"<div style='padding:14px 18px;border-radius:8px;margin-top:8px;"
        f"background:{ {'ok':'#d4edda','duplicate':'#fff3cd','error':'#f8d7da'}[last['status']] };"
        f"color:#222;font-size:20px;font-weight:600;'>"
        f"{last['student_number']} · {last['name']}"
        f"{ {'ok':' ✅','duplicate':' ⚠️ 중복','error':' ❌'}[last['status']] }"
        f"</div>"
    )
    st.markdown(box, unsafe_allow_html=True)

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

    render_last_checkin()


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

    render_last_checkin()


