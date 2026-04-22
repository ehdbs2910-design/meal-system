"""AI 데이터 분석 페이지"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from utils.auth import require_login
from utils.db import get_meal_history, get_students

st.set_page_config(page_title="AI 분석", page_icon="🤖", layout="wide")
require_login()


# ════════════════════════════════════════════════════════════
# 데이터 로드
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def load_history(days: int):
    data, err = get_meal_history(days)
    return data or [], err

@st.cache_data(ttl=300)
def load_students():
    data, err = get_students()
    return data or [], err


# ════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════

st.title("🤖 AI 데이터 분석")

# 기간 선택
days = st.select_slider("분석 기간", options=[7, 14, 30, 60, 90], value=30,
                         format_func=lambda x: f"최근 {x}일")

records, err = load_history(days)
students, _ = load_students()

if err:
    st.error(f"❌ {err}")
    st.stop()

if not records:
    st.warning("급식 기록이 없습니다. 체크인 데이터가 쌓이면 분석이 가능합니다.")
    st.stop()

# 데이터 전처리
df = pd.DataFrame(records)
df["meal_date"] = pd.to_datetime(df["meal_date"])
df["dow"] = df["meal_date"].dt.dayofweek  # 0=월 ~ 6=일
df["dow_name"] = df["meal_date"].dt.strftime("%a")

total_students = len(students) if students else df.groupby("meal_date").size().max()

# 일별 수령 인원
daily = (
    df.groupby("meal_date").size()
    .reset_index(name="count")
    .sort_values("meal_date")
)
daily["rate"] = (daily["count"] / total_students * 100).round(1)
daily["date_str"] = daily["meal_date"].dt.strftime("%m/%d")

tab1, tab2, tab3, tab4 = st.tabs(["📈 수령 추이 & 예측", "📅 요일 패턴", "🚨 이상치 탐지", "👥 학생 클러스터링"])


# ── 탭1: 수령 추이 & 예측 ─────────────────────────────────
with tab1:
    st.subheader("일별 급식 수령 추이")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily["meal_date"], y=daily["rate"],
        mode="lines+markers", name="수령률(%)",
        line=dict(color="#4C9BE8", width=2),
        marker=dict(size=6),
    ))
    fig.add_hline(y=daily["rate"].mean(), line_dash="dash", line_color="gray",
                  annotation_text=f"평균 {daily['rate'].mean():.1f}%")
    fig.update_layout(yaxis_title="수령률 (%)", yaxis_range=[0, 105],
                      margin=dict(t=20, b=20), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # Prophet 예측
    st.subheader("향후 7일 수령률 예측")
    if len(daily) < 7:
        st.info("예측을 위해 최소 7일치 데이터가 필요합니다.")
    else:
        try:
            from prophet import Prophet
            import logging
            logging.getLogger("prophet").setLevel(logging.ERROR)
            logging.getLogger("cmdstanpy").setLevel(logging.ERROR)

            with st.spinner("예측 모델 학습 중..."):
                prophet_df = daily[["meal_date", "rate"]].rename(
                    columns={"meal_date": "ds", "rate": "y"}
                )
                m = Prophet(
                    yearly_seasonality=False,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                )
                m.fit(prophet_df)
                future = m.make_future_dataframe(periods=7)
                forecast = m.predict(future)
                forecast["yhat"] = forecast["yhat"].clip(0, 100)
                forecast["yhat_lower"] = forecast["yhat_lower"].clip(0, 100)
                forecast["yhat_upper"] = forecast["yhat_upper"].clip(0, 100)

            fig2 = go.Figure()
            hist = forecast[forecast["ds"] <= daily["meal_date"].max()]
            pred = forecast[forecast["ds"] > daily["meal_date"].max()]

            fig2.add_trace(go.Scatter(
                x=daily["meal_date"], y=daily["rate"],
                mode="lines+markers", name="실제", line=dict(color="#4C9BE8")
            ))
            fig2.add_trace(go.Scatter(
                x=pred["ds"], y=pred["yhat"],
                mode="lines+markers", name="예측", line=dict(color="#FF6B6B", dash="dash")
            ))
            fig2.add_trace(go.Scatter(
                x=pd.concat([pred["ds"], pred["ds"][::-1]]),
                y=pd.concat([pred["yhat_upper"], pred["yhat_lower"][::-1]]),
                fill="toself", fillcolor="rgba(255,107,107,0.15)",
                line=dict(color="rgba(255,107,107,0)"), name="예측 범위"
            ))
            fig2.update_layout(yaxis_title="수령률 (%)", yaxis_range=[0, 105],
                               margin=dict(t=20, b=20), hovermode="x unified")
            st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(
                pred[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(columns={
                    "ds": "날짜", "yhat": "예측 수령률(%)",
                    "yhat_lower": "하한(%)", "yhat_upper": "상한(%)"
                }).assign(**{
                    "날짜": lambda d: d["날짜"].dt.strftime("%Y-%m-%d"),
                    "예측 수령률(%)": lambda d: d["예측 수령률(%)"].round(1),
                    "하한(%)": lambda d: d["하한(%)"].round(1),
                    "상한(%)": lambda d: d["상한(%)"].round(1),
                }),
                use_container_width=True, hide_index=True
            )

        except ImportError:
            st.warning("Prophet 패키지가 없어 예측을 건너뜁니다. (`pip install prophet`)")
        except Exception as e:
            st.warning(f"예측 중 오류: {e}")


# ── 탭2: 요일 패턴 ────────────────────────────────────────
with tab2:
    st.subheader("요일별 평균 수령률")

    dow_map = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}
    dow_avg = (
        df.groupby("dow").size()
        .reset_index(name="count")
    )
    # 날짜별 요일 횟수도 고려해 평균 계산
    dow_days = daily.copy()
    dow_days["dow"] = dow_days["meal_date"].dt.dayofweek
    dow_rate = dow_days.groupby("dow")["rate"].mean().reset_index()
    dow_rate["요일"] = dow_rate["dow"].map(dow_map)
    dow_rate["수령률(%)"] = dow_rate["rate"].round(1)

    fig3 = px.bar(
        dow_rate, x="요일", y="수령률(%)",
        color="수령률(%)",
        color_continuous_scale=["#ff6b6b", "#ffd93d", "#6bcb77"],
        range_color=[dow_rate["수령률(%)"].min() - 5, 100],
        text="수령률(%)",
    )
    fig3.update_traces(textposition="outside")
    fig3.update_layout(coloraxis_showscale=False, yaxis_range=[0, 110],
                       margin=dict(t=20, b=20))
    st.plotly_chart(fig3, use_container_width=True)

    best = dow_rate.loc[dow_rate["수령률(%)"].idxmax(), "요일"]
    worst = dow_rate.loc[dow_rate["수령률(%)"].idxmin(), "요일"]
    c1, c2 = st.columns(2)
    c1.metric("수령률 가장 높은 요일", f"{best}요일", f"{dow_rate['수령률(%)'].max():.1f}%")
    c2.metric("수령률 가장 낮은 요일", f"{worst}요일", f"{dow_rate['수령률(%)'].min():.1f}%")


# ── 탭3: 이상치 탐지 ──────────────────────────────────────
with tab3:
    st.subheader("수령률 이상치 탐지")
    st.caption("평균에서 크게 벗어난 날을 자동으로 감지합니다.")

    if len(daily) < 5:
        st.info("이상치 탐지를 위해 최소 5일치 데이터가 필요합니다.")
    else:
        mean = daily["rate"].mean()
        std = daily["rate"].std()
        daily["z_score"] = ((daily["rate"] - mean) / std).round(2)
        daily["이상치"] = daily["z_score"].abs() > 2.0

        anomalies = daily[daily["이상치"]]

        fig4 = go.Figure()
        normal = daily[~daily["이상치"]]
        fig4.add_trace(go.Scatter(
            x=normal["meal_date"], y=normal["rate"],
            mode="markers+lines", name="정상",
            marker=dict(color="#4C9BE8", size=7),
        ))
        if not anomalies.empty:
            fig4.add_trace(go.Scatter(
                x=anomalies["meal_date"], y=anomalies["rate"],
                mode="markers", name="이상치",
                marker=dict(color="#FF6B6B", size=12, symbol="x"),
            ))
        fig4.add_hrect(y0=mean - 2*std, y1=mean + 2*std,
                       fillcolor="rgba(76,155,232,0.08)", line_width=0,
                       annotation_text="정상 범위 (±2σ)")
        fig4.update_layout(yaxis_title="수령률 (%)", yaxis_range=[0, 105],
                           margin=dict(t=20, b=20), hovermode="x unified")
        st.plotly_chart(fig4, use_container_width=True)

        if anomalies.empty:
            st.success("✅ 이상치가 감지되지 않았습니다.")
        else:
            st.warning(f"⚠️ {len(anomalies)}개의 이상치 날짜 감지")
            st.dataframe(
                anomalies[["date_str", "count", "rate", "z_score"]].rename(columns={
                    "date_str": "날짜", "count": "수령 인원",
                    "rate": "수령률(%)", "z_score": "Z-Score"
                }),
                use_container_width=True, hide_index=True
            )


# ── 탭4: 학생 클러스터링 ──────────────────────────────────
with tab4:
    st.subheader("학생 수령 패턴 클러스터링")
    st.caption("K-Means로 학생들의 급식 수령 패턴을 그룹화합니다.")

    if len(daily) < 5:
        st.info("클러스터링을 위해 최소 5일치 데이터가 필요합니다.")
    else:
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler

            # 학생별 특성 생성
            student_ids = df["student_id"].unique()
            date_range = pd.date_range(daily["meal_date"].min(), daily["meal_date"].max())
            total_days = len(date_range)

            student_features = []
            for sid in student_ids:
                s_df = df[df["student_id"] == sid]
                freq = len(s_df) / total_days  # 수령 빈도
                dow_counts = s_df["dow"].value_counts()
                fav_dow = dow_counts.idxmax() if not dow_counts.empty else -1
                student_features.append({
                    "student_id": sid,
                    "freq": freq,
                    "fav_dow": fav_dow,
                    "total": len(s_df),
                })

            feat_df = pd.DataFrame(student_features)

            n_clusters = st.slider("클러스터 수", min_value=2, max_value=5, value=3)

            X = feat_df[["freq", "total"]].values
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            feat_df["cluster"] = km.fit_predict(X_scaled).astype(str)

            # 학생 이름 연결
            if students:
                stu_df = pd.DataFrame(students)[["id", "name", "grade", "class_number"]]
                feat_df = feat_df.merge(stu_df, left_on="student_id", right_on="id", how="left")

            fig5 = px.scatter(
                feat_df, x="total", y="freq",
                color="cluster",
                hover_data=["name", "grade", "class_number"] if "name" in feat_df.columns else [],
                labels={"total": "총 수령 횟수", "freq": "일평균 수령 빈도", "cluster": "그룹"},
                title="학생 수령 패턴 클러스터",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig5.update_traces(marker=dict(size=9))
            fig5.update_layout(margin=dict(t=40, b=20))
            st.plotly_chart(fig5, use_container_width=True)

            # 클러스터별 요약
            summary = feat_df.groupby("cluster").agg(
                인원=("student_id", "count"),
                평균수령횟수=("total", lambda x: round(x.mean(), 1)),
                평균빈도=("freq", lambda x: round(x.mean(), 3)),
            ).reset_index().rename(columns={"cluster": "그룹"})
            st.dataframe(summary, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"클러스터링 오류: {e}")
