"""급식 체크인 페이지"""
import streamlit as st
from datetime import date

from utils.auth import require_login, current_user
from utils.db import get_client, safe_query, record_meal_checkin
from utils.qr_utils import verify_token

st.set_page_config(page_title="급식 체크인", page_icon="✅", layout="centered")
require_login()

ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두",
    "15": "닭고기", "16": "쇠고기", "17": "오징어", "18": "조개류",
}


# ── DB 헬퍼 ───────────────────────────────────────────────

def get_student_by_id(student_id: str):
    return safe_query(
        lambda: get_client()
            .table("students").select("*")
            .eq("id", student_id).eq("is_active", True)
            .single().execute(),
        "학생 조회 실패"
    )


def get_student_by_number(student_number: str):
    return safe_query(
        lambda: get_client()
            .table("students").select("*")
            .eq("student_number", student_number).eq("is_active", True)
            .single().execute(),
        "학생 조회 실패"
    )


def already_received(student_id: str) -> tuple[bool, str | None]:
    data, err = safe_query(
        lambda: get_client()
            .table("meal_records")
            .select("checkin_time")
            .eq("student_id", student_id)
            .eq("meal_date", date.today().isoformat())
            .eq("meal_type", "lunch")
            .execute(),
        "중복 확인 실패"
    )
    if err:
        return False, err
    return bool(data), None


# ── UI 컴포넌트 ───────────────────────────────────────────

def render_student_card(student: dict):
    allergies = student.get("allergies") or []
    roll = student.get("class_roll_number")
    roll_str = f" {roll}번" if roll else ""

    received, err = already_received(student["id"])

    col_info, col_status = st.columns([3, 1])
    with col_info:
        st.markdown(f"### {student['name']}")
        st.markdown(f"**{student['grade']}학년 {student['class_number']}반{roll_str}** · 학번 {student['student_number']}")
    with col_status:
        st.markdown("<br>", unsafe_allow_html=True)
        if received:
            st.error("이미 수령")
        else:
            st.success("수령 가능")

    if allergies:
        labels = [f"{c}.{ALLERGY_MAP.get(c, c)}" for c in allergies]
        st.warning(f"⚠️ 알레르기: {', '.join(labels)}")

    return received


def do_checkin(student: dict) -> str | None:
    user = current_user()
    _, err = record_meal_checkin(
        student_id=student["id"],
        checked_by=user["id"] if user else None,
        device_info="web",
    )
    return err


def process_student(student: dict, key_suffix: str):
    """학생 카드 표시 + 체크인 버튼 처리"""
    received = render_student_card(student)

    if received:
        if st.button("🔄 다음 학생", key=f"next_{key_suffix}", use_container_width=True):
            st.session_state.pop(f"student_{key_suffix}", None)
            st.rerun()
        return

    col_confirm, col_cancel = st.columns(2)
    with col_confirm:
        if st.button("✅ 급식 수령 확인", type="primary",
                     key=f"confirm_{key_suffix}", use_container_width=True):
            err = do_checkin(student)
            if err:
                st.error(f"❌ {err}")
            else:
                st.success(f"✅ {student['name']} 학생 수령 완료!")
                st.session_state.pop(f"student_{key_suffix}", None)
                st.balloons()
                st.rerun()
    with col_cancel:
        if st.button("취소", key=f"cancel_{key_suffix}", use_container_width=True):
            st.session_state.pop(f"student_{key_suffix}", None)
            st.rerun()


# ════════════════════════════════════════════════════════════
# 메인 UI
# ════════════════════════════════════════════════════════════

st.title("✅ 급식 체크인")
st.caption(f"오늘 날짜: {date.today().strftime('%Y년 %m월 %d일')}")

tab_qr, tab_manual = st.tabs(["📷 QR 스캔", "⌨️ 수동 입력"])


# ── 탭1: QR 스캔 ──────────────────────────────────────────
with tab_qr:
    try:
        from streamlit_qrcode_scanner import qrcode_scanner
    except ImportError:
        st.error("❌ streamlit-qrcode-scanner 패키지가 없습니다. `pip install streamlit-qrcode-scanner`")
        st.stop()

    st.info("카메라에 학생증 QR 코드를 비춰주세요.")
    qr_result = qrcode_scanner(key="qr_scanner")

    if qr_result:
        # 중복 스캔 방지
        if st.session_state.get("last_qr_token") != qr_result:
            st.session_state["last_qr_token"] = qr_result
            student_id = verify_token(qr_result)
            if student_id is None:
                st.error("❌ 유효하지 않은 QR 코드입니다.")
            else:
                student, err = get_student_by_id(student_id)
                if err or not student:
                    st.error("❌ 학생 정보를 찾을 수 없습니다.")
                else:
                    st.session_state["student_qr"] = student

    if "student_qr" in st.session_state:
        st.divider()
        process_student(st.session_state["student_qr"], key_suffix="qr")


# ── 탭2: 수동 입력 ────────────────────────────────────────
with tab_manual:
    st.caption("QR 스캔이 어려울 때 학번으로 직접 조회합니다.")

    with st.form("manual_form", clear_on_submit=True):
        student_number = st.text_input("학번 입력", placeholder="예: 20240101",
                                       max_chars=20)
        submitted = st.form_submit_button("🔍 조회", use_container_width=True,
                                          type="primary")

    if submitted and student_number.strip():
        student, err = get_student_by_number(student_number.strip())
        if err or not student:
            st.error("❌ 해당 학번의 학생을 찾을 수 없습니다.")
        else:
            st.session_state["student_manual"] = student

    if "student_manual" in st.session_state:
        st.divider()
        process_student(st.session_state["student_manual"], key_suffix="manual")
