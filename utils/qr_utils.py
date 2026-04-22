"""QR 코드 생성 및 토큰 검증"""
from __future__ import annotations

import hmac
import hashlib
import base64
from io import BytesIO

import qrcode
from PIL import Image

from utils.config import QR_SECRET_KEY


def _make_token(student_id: str) -> str:
    """학생 ID를 HMAC-SHA256으로 서명한 영구 토큰 생성.

    학번을 그대로 QR에 넣지 않고, 서명된 토큰으로 보호.
    토큰 형식: base64(student_id) + "." + base64(HMAC서명)
    """
    id_b64 = base64.urlsafe_b64encode(student_id.encode()).decode().rstrip("=")
    sig = hmac.new(
        QR_SECRET_KEY.encode(),
        msg=id_b64.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{id_b64}.{sig_b64}"


def verify_token(token: str) -> str | None:
    """QR 토큰 검증. 유효하면 student_id 반환, 실패시 None."""
    try:
        id_b64, sig_b64 = token.split(".")

        # 서명 검증
        expected_sig = hmac.new(
            QR_SECRET_KEY.encode(),
            msg=id_b64.encode(),
            digestmod=hashlib.sha256,
        ).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_b64):
            return None

        # student_id 복원
        padding = 4 - len(id_b64) % 4
        student_id = base64.urlsafe_b64decode(id_b64 + "=" * padding).decode()
        return student_id

    except Exception:
        return None


def generate_qr_image(student_id: str, size: int = 200) -> Image.Image:
    """학생 ID로 영구 QR 이미지 생성 (고정 QR — 교사가 스캔)."""
    token = _make_token(student_id)

    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(token)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.LANCZOS)
    return img


def generate_qr_bytes(student_id: str, size: int = 200) -> bytes:
    """QR 이미지를 PNG bytes로 반환 (Streamlit 표시용)."""
    img = generate_qr_image(student_id, size)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
