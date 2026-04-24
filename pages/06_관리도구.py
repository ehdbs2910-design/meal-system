"""관리 도구 — 가상 데이터 생성 / 초기화 (관리자 전용)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import date, timedelta, datetime, timezone

import streamlit as st
from loguru import logger

from utils.auth import require_admin, render_sidebar_nav
from utils.db import get_service_client, safe_query

st.set_page_config(page_title="관리 도구", page_icon="🛠️", layout="centered")
require_admin()
render_sidebar_nav()

st.title("🛠️ 관리 도구")
st.caption("데이터 생성·초기화는 되돌릴 수 없으니 신중히 사용하세요.")


# ── 헬퍼 ──────────────────────────────────────────────────

def get_all_students():
    return safe_query(
        lambda: get_service_client()
            .table("students").select("id")
            .eq("is_active", True).execute(),
        "학생 조회 실패"
    )


def delete_records_in_range(start: str, end: str) -> str | None:
    try:
        get_service_client().table("meal_records").delete() \
            .gte("meal_date", start).lte("meal_date", end).execute()
        return None
    except Exception as e:
        logger.error(f"기존 기록 삭제 실패: {e}")
        return str(e)


def insert_meal_records(records: list[dict]) -> tuple[int, str | None]:
    """대량 insert."""
    client = get_service_client()
    inserted = 0
    batch = 200
    last_err = None
    for i in range(0, len(records), batch):
        chunk = records[i:i + batch]
        try:
            client.table("meal_records").insert(chunk).execute()
            inserted += len(chunk)
        except Exception as e:
            last_err = str(e)
            logger.error(f"insert 실패 (chunk {i}): {e}")
    return inserted, last_err


def delete_all_meal_records() -> tuple[int, str | None]:
    def _q():
        return get_service_client().table("meal_records").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
    _, err = safe_query(_q, "급식 기록 삭제 실패")
    return (0 if err else -1), err


def delete_all_students() -> tuple[int, str | None]:
    def _q():
        return get_service_client().table("students").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
    _, err = safe_query(_q, "학생 삭제 실패")
    return (0 if err else -1), err


# ════════════════════════════════════════════════════════════
# 탭
# ════════════════════════════════════════════════════════════
tab_seed, tab_reset = st.tabs(["🌱 가상 데이터 생성", "🗑️ 데이터 초기화"])


# ── 탭1: 가상 데이터 생성 ─────────────────────────────────
with tab_seed:
    st.subheader("🌱 급식 수령 기록 자동 생성")
    st.caption("등록된 학생들을 대상으로 과거 N일간의 급식 수령 기록을 무작위로 생성합니다.")

    col1, col2 = st.columns(2)
    with col1:
        n_days = st.number_input("과거 며칠치", min_value=1, max_value=180, value=30)
    with col2:
        receipt_rate = st.slider("평균 수령률", 50, 100, 85) / 100

    include_weekend = st.checkbox("주말 포함", value=False)

    st.caption("⚠️ 해당 기간의 기존 기록은 삭제 후 새로 생성됩니다.")

    if st.button("🌱 생성 시작", type="primary", use_container_width=True):
        students, err = get_all_students()
        if err or not students:
            st.error("❌ 학생이 없습니다. 먼저 학생을 등록하세요.")
        else:
            student_ids = [s["id"] for s in students]
            today = date.today()
            start_d = (today - timedelta(days=n_days)).isoformat()
            end_d = (today - timedelta(days=1)).isoformat()

            with st.spinner("기존 기록 정리 중..."):
                del_err = delete_records_in_range(start_d, end_d)
            if del_err:
                st.warning(f"기존 기록 삭제 중 경고: {del_err}")

            records = []

            for d in range(n_days, 0, -1):
                day = today - timedelta(days=d)
                if not include_weekend and day.weekday() >= 5:
                    continue

                # 요일별 소폭 변동 (금요일 낮음, 월요일 높음 등)
                dow_modifier = {0: 1.0, 1: 0.97, 2: 0.95, 3: 0.93, 4: 0.88, 5: 0.6, 6: 0.5}
                day_rate = max(0.3, min(1.0, receipt_rate * dow_modifier[day.weekday()]
                                         + random.uniform(-0.08, 0.05)))

                for sid in student_ids:
                    if random.random() < day_rate:
                        # 학생별 개인 패턴(일부는 자주/드물게 수령)
                        hour = random.choice([11, 12, 12, 12, 13])
                        minute = random.randint(0, 59)
                        sec = random.randint(0, 59)
                        checkin = datetime.combine(day, datetime.min.time()).replace(
                            hour=hour, minute=minute, second=sec, tzinfo=timezone.utc
                        )
                        records.append({
                            "student_id": sid,
                            "meal_date": day.isoformat(),
                            "meal_type": "lunch",
                            "checkin_time": checkin.isoformat(),
                            "device_info": "seed",
                        })

            with st.spinner(f"{len(records):,}건 저장 중..."):
                count, err2 = insert_meal_records(records)
            if err2:
                st.warning(f"일부 오류: {err2} ({count}건 저장됨)")
            else:
                st.success(f"✅ 총 {count:,}건 생성 완료!")
                st.balloons()


# ── 탭2: 초기화 ───────────────────────────────────────────
with tab_reset:
    st.subheader("🗑️ 데이터 초기화")
    st.warning("⚠️ 이 작업은 **되돌릴 수 없습니다.**")

    st.markdown("#### 급식 수령 기록만 초기화")
    st.caption("학생 정보는 유지하고 모든 체크인 기록만 삭제합니다.")
    confirm1 = st.text_input("확인 문구 입력: `reset records`", key="confirm_records")
    if st.button("📋 급식 기록 전체 삭제", use_container_width=True,
                 disabled=(confirm1 != "reset records")):
        with st.spinner("삭제 중..."):
            _, err = delete_all_meal_records()
        if err:
            st.error(f"❌ {err}")
        else:
            st.success("✅ 모든 급식 기록이 삭제되었습니다.")

    st.divider()

    st.markdown("#### 학생 + 급식 기록 전체 초기화")
    st.caption("학생과 관련된 모든 데이터를 삭제합니다. (CASCADE로 급식 기록도 같이 삭제)")
    confirm2 = st.text_input("확인 문구 입력: `reset all`", key="confirm_all")
    if st.button("🔥 학생 + 기록 전체 삭제", type="primary", use_container_width=True,
                 disabled=(confirm2 != "reset all")):
        with st.spinner("삭제 중..."):
            _, err = delete_all_students()
        if err:
            st.error(f"❌ {err}")
        else:
            st.success("✅ 모든 학생과 급식 기록이 삭제되었습니다.")
