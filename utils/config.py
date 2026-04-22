"""환경변수 로드 및 앱 설정"""
import os
from dotenv import load_dotenv
from loguru import logger
import sys

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """os.environ → st.secrets 순서로 값 조회 (Streamlit Cloud 호환)"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# ── Supabase ──────────────────────────────────────────────
SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_ANON_KEY = _get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = _get("SUPABASE_SERVICE_KEY")

# ── QR 보안 ───────────────────────────────────────────────
QR_SECRET_KEY = _get("QR_SECRET_KEY")

# ── 앱 설정 ───────────────────────────────────────────────
APP_NAME = _get("APP_NAME", "급식 관리 시스템")
SCHOOL_NAME = _get("SCHOOL_NAME", "○○고등학교")
MEAL_TYPE = _get("MEAL_TYPE", "lunch")

# ── 로그 설정 ─────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

os.makedirs("logs", exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    level=LOG_LEVEL,
    encoding="utf-8",
)


def validate_env() -> list[str]:
    """필수 환경변수 검증. 누락된 항목 목록 반환."""
    missing = []
    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_ANON_KEY": SUPABASE_ANON_KEY,
        "QR_SECRET_KEY": QR_SECRET_KEY,
    }
    for key, val in required.items():
        if not val:
            missing.append(key)
    return missing
