"""실시간 대시보드 — 5단계에서 구현 예정"""
import streamlit as st
from utils.auth import require_login

st.set_page_config(page_title="대시보드", page_icon="📊", layout="wide")
require_login()

st.title("📊 실시간 대시보드")
st.info("🚧 5단계 구현 예정입니다.")
