"""PDF 학생증 생성 — A4에 2열×4행 배치"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from utils.qr_utils import generate_qr_image
from utils.config import SCHOOL_NAME

# 한글 폰트 등록 (Windows 맑은 고딕 사용)
import os

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕 (Windows)
    "C:/Windows/Fonts/malgunbd.ttf",     # 맑은 고딕 Bold
    "C:/Windows/Fonts/gulim.ttc",        # 굴림
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux NanumGothic
]

FONT_NORMAL = "Helvetica"  # 폴백
for _path in _FONT_CANDIDATES:
    if os.path.exists(_path):
        pdfmetrics.registerFont(TTFont("KoreanFont", _path))
        FONT_NORMAL = "KoreanFont"
        break

FONT_BOLD = FONT_NORMAL

# 학생증 레이아웃
CARD_W_MM = 88.0   # 카드 너비 (mm)
CARD_H_MM = 56.0   # 카드 높이 (mm)
COLS      = 2      # 가로 장수
QR_SIZE   = 160    # QR 픽셀


ALLERGY_MAP = {
    "1":"난류","2":"우유","3":"메밀","4":"땅콩","5":"대두",
    "6":"밀","7":"고등어","8":"게","9":"새우","10":"돼지고기",
    "11":"복숭아","12":"토마토","13":"아황산류","14":"호두",
    "15":"닭고기","16":"쇠고기","17":"오징어","18":"조개류",
}


def _allergy_text(codes: list) -> str:
    if not codes:
        return ""
    names = [ALLERGY_MAP.get(str(c), str(c)) for c in codes]
    return "알레르기: " + ", ".join(names)


def _make_card(student: dict[str, Any]) -> Table:
    """학생 1명의 카드 Table 반환"""
    # 스타일
    school_style  = ParagraphStyle("school",  fontName=FONT_NORMAL, fontSize=7,  leading=9,  textColor=colors.grey)
    name_style    = ParagraphStyle("name",    fontName=FONT_BOLD,   fontSize=13, leading=16)
    info_style    = ParagraphStyle("info",    fontName=FONT_NORMAL, fontSize=8,  leading=11)
    allergy_style = ParagraphStyle("allergy", fontName=FONT_NORMAL, fontSize=7,  leading=9,  textColor=colors.red)

    allergies   = student.get("allergies") or []
    allergy_txt = _allergy_text(allergies)

    # 좌측 텍스트 블록
    left_items = [
        [Paragraph(SCHOOL_NAME, school_style)],
        [Spacer(1, 1*mm)],
        [Paragraph(student["name"], name_style)],
        [Paragraph(f"{student['grade']}학년 {student['class_number']}반", info_style)],
        [Paragraph(f"학번  {student['student_number']}", info_style)],
    ]
    if allergy_txt:
        left_items.append([Paragraph(allergy_txt, allergy_style)])

    left_table = Table(left_items, colWidths=[(CARD_W_MM - 26) * mm])
    left_table.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    # 우측 QR 이미지
    qr_pil = generate_qr_image(student["id"], size=QR_SIZE)
    buf = BytesIO()
    qr_pil.save(buf, format="PNG")
    buf.seek(0)
    qr_img = RLImage(buf, width=22*mm, height=22*mm)

    # 카드 전체 Table
    card = Table(
        [[left_table, qr_img]],
        colWidths=[(CARD_W_MM - 26) * mm, 26 * mm],
        rowHeights=[CARD_H_MM * mm - 8 * mm],
    )
    card.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.8, colors.HexColor("#CCCCCC")),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
        ("LEFTPADDING",   (0, 0), (0, 0),   4 * mm),
        ("RIGHTPADDING",  (0, 0), (0, 0),   2 * mm),
        ("LEFTPADDING",   (1, 0), (1, 0),   1 * mm),
        ("RIGHTPADDING",  (1, 0), (1, 0),   2 * mm),
        ("TOPPADDING",    (0, 0), (-1, -1), 4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # 좌측 파란 띠
        ("LINEWIDTH",     (0, 0), (0, 0),   3),
        ("LINEBEFORE",    (0, 0), (0, 0),   3, colors.HexColor("#1976D2")),
    ]))
    return card


def generate_student_cards_pdf(students: list[dict[str, Any]]) -> bytes:
    """학생 목록으로 학생증 PDF 생성. PDF bytes 반환."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    elements: list = []
    row_buffer: list = []

    for student in students:
        row_buffer.append(_make_card(student))

        if len(row_buffer) == COLS:
            row_table = Table(
                [row_buffer],
                colWidths=[CARD_W_MM * mm] * COLS,
            )
            row_table.setStyle(TableStyle([
                ("LEFTPADDING",   (0, 0), (-1, -1), 2 * mm),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 2 * mm),
                ("TOPPADDING",    (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]))
            elements.append(row_table)
            elements.append(Spacer(1, 3 * mm))
            row_buffer = []

    # 남은 카드 처리
    if row_buffer:
        while len(row_buffer) < COLS:
            row_buffer.append(Spacer(CARD_W_MM * mm, CARD_H_MM * mm))
        row_table = Table(
            [row_buffer],
            colWidths=[CARD_W_MM * mm] * COLS,
        )
        elements.append(row_table)

    doc.build(elements)
    return buf.getvalue()
