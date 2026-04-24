"""실시간 대시보드"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from utils.auth import require_login, render_sidebar_nav
from utils.db import get_today_meal_status, get_class_stats

st.set_page_config(page_title="대시보드", page_icon="📊", layout="wide")
require_login()
render_sidebar_nav()

ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두",
    "15": "닭고기", "16": "쇠고기", "17": "오징어", "18": "조개류",
}

# ════════════════════════════════════════════════════════════
# 데이터 로드
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_data():
    status, err1 = get_today_meal_status()
    stats, err2 = get_class_stats()
    return status or [], stats or [], err1 or err2


# ════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════

col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title("📊 실시간 대시보드")
    st.caption(f"오늘: {date.today().strftime('%Y년 %m월 %d일')} · 30초마다 자동 갱신")
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

status_list, stats_list, err = load_data()

if err:
    st.error(f"❌ {err}")
    st.stop()

if not status_list:
    st.info("등록된 학생이 없습니다.")
    st.stop()

df_status = pd.DataFrame(status_list)
df_stats = pd.DataFrame(stats_list) if stats_list else pd.DataFrame()

total = len(df_status)
received = int(df_status["has_received"].sum())
not_received = total - received
rate = received / total * 100 if total else 0

# ── 상단 지표 ─────────────────────────────────────────────
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("전체 학생", f"{total}명")
c2.metric("수령 완료", f"{received}명")
c3.metric("미수령", f"{not_received}명")
c4.metric("수령률", f"{rate:.1f}%")
st.divider()

# ── 학년별 탭 ─────────────────────────────────────────────
tab_all, tab1, tab2, tab3 = st.tabs(["전체", "1학년", "2학년", "3학년"])

def render_grade(df_s: pd.DataFrame, df_st: pd.DataFrame):
    if df_s.empty:
        st.info("해당 학년 학생이 없습니다.")
        return

    col_chart, col_table = st.columns([1, 1])

    # 반별 수령률 차트
    with col_chart:
        if not df_st.empty:
            df_st = df_st.copy()
            df_st["반"] = df_st["class_number"].astype(str) + "반"
            fig = px.bar(
                df_st, x="반", y="receipt_rate",
                color="receipt_rate",
                color_continuous_scale=["#ff6b6b", "#ffd93d", "#6bcb77"],
                range_color=[0, 100],
                labels={"receipt_rate": "수령률(%)"},
                title="반별 수령률",
            )
            fig.update_layout(
                coloraxis_showscale=False,
                margin=dict(t=40, b=20),
                yaxis_range=[0, 100],
            )
            fig.add_hline(y=100, line_dash="dot", line_color="gray")
            st.plotly_chart(fig, use_container_width=True)

    # 반별 통계 표
    with col_table:
        if not df_st.empty:
            display = df_st[["class_number", "total_students", "received_count",
                              "not_received_count", "receipt_rate"]].copy()
            display.columns = ["반", "전체", "수령", "미수령", "수령률(%)"]
            st.dataframe(display, use_container_width=True, hide_index=True)

    # 미수령 학생 목록
    not_recv = df_s[df_s["has_received"] == False].copy()
    if not_recv.empty:
        st.success("✅ 전원 수령 완료!")
    else:
        with st.expander(f"⚠️ 미수령 학생 {len(not_recv)}명", expanded=True):
            not_recv["알레르기"] = not_recv["allergies"].apply(
                lambda x: ", ".join(f"{c}.{ALLERGY_MAP.get(c,c)}" for c in (x or [])) or "없음"
            )
            show = not_recv[["grade", "class_number", "name", "student_number", "알레르기"]].copy()
            show.columns = ["학년", "반", "이름", "학번", "알레르기"]
            st.dataframe(show, use_container_width=True, hide_index=True)


with tab_all:
    render_grade(
        df_status,
        df_stats,
    )

for grade, tab in zip([1, 2, 3], [tab1, tab2, tab3]):
    with tab:
        render_grade(
            df_status[df_status["grade"] == grade],
            df_stats[df_stats["grade"] == grade] if not df_stats.empty else pd.DataFrame(),
        )

# ── 자동 새로고침 (30초) ──────────────────────────────────
st.markdown(
    """
    <script>
    setTimeout(function() { window.location.reload(); }, 30000);
    </script>
    """,
    unsafe_allow_html=True,
)
