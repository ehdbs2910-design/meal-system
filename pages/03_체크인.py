"""급식 체크인 페이지"""
import streamlit as st
from datetime import date

from utils.auth import current_user
from utils.db import get_service_client, safe_query, record_meal_checkin
from utils.qr_utils import verify_token

st.set_page_config(page_title="급식 체크인", page_icon="✅", layout="centered")

ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두",
    "15": "닭고기", "16": "쇠고기", "17": "오징어", "18": "조개류",
}


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
    """체크인 즉시 실행 후 결과 표시"""
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
# 메인 UI
# ════════════════════════════════════════════════════════════

st.title("✅ 급식 체크인")
st.caption(f"오늘: {date.today().strftime('%Y년 %m월 %d일')}")

tab_qr, tab_manual = st.tabs(["📷 QR 스캔", "⌨️ 수동 입력"])


# ── 탭1: QR 스캔 ──────────────────────────────────────────
with tab_qr:
    from components.qr_scanner import qr_scanner

    st.info("📷 학생증 QR코드를 카메라에 비춰주세요.")
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
