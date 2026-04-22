"""AI 데이터 분석 페이지 — 6단계에서 구현 예정"""
import streamlit as st
from utils.auth import require_login

st.set_page_config(page_title="AI 분석", page_icon="🤖", layout="wide")
require_login()

st.title("🤖 AI 데이터 분석")
st.info("🚧 6단계 구현 예정입니다.")
