"""QR 코드 생성 및 학생증 PDF 출력"""
import streamlit as st
import pandas as pd
from io import BytesIO

from utils.auth import require_login, is_admin
from utils.db import get_client, safe_query
from utils.qr_utils import generate_qr_bytes
from utils.pdf_utils import generate_student_cards_pdf

st.set_page_config(page_title="QR 생성", page_icon="📱", layout="wide")
require_login()

# ── DB ────────────────────────────────────────────────────
def load_students():
    data, err = safe_query(
        lambda: get_client()
            .table("students")
            .select("id, student_number, name, grade, class_number, allergies")
            .eq("is_active", True)
            .order("grade").order("class_number").order("student_number")
            .execute(),
        "학생 목록 조회 실패"
    )
    return data or [], err

# ════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════
st.title("📱 QR 생성 / 학생증 출력")

students, err = load_students()
if err:
    st.error(f"❌ {err}")
    st.stop()
if not students:
    st.info("등록된 학생이 없습니다. 먼저 학생 관리에서 학생을 추가하세요.")
    st.stop()

df = pd.DataFrame(students)

tab1, tab2 = st.tabs(["🔍 개별 QR 조회", "📄 학생증 PDF 출력"])

# ── 탭1: 개별 QR 조회 ─────────────────────────────────────
with tab1:
    st.subheader("학생 QR 코드 조회")
    st.caption("QR 코드는 학생마다 **고정된 고유 코드**입니다. 학생증에 인쇄해서 사용하세요.")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        sel_grade = st.selectbox("학년", ["전체"] + [1, 2, 3], key="qr_grade")
    with col_f2:
        sel_class = st.selectbox("반", ["전체"] + list(range(1, 21)), key="qr_class")

    filtered = df.copy()
    if sel_grade != "전체":
        filtered = filtered[filtered["grade"] == sel_grade]
    if sel_class != "전체":
        filtered = filtered[filtered["class_number"] == sel_class]

    if filtered.empty:
        st.warning("해당 조건의 학생이 없습니다.")
    else:
        # 학생 선택
        student_options = {
            f"{r['grade']}학년 {r['class_number']}반 {r['name']} ({r['student_number']})": r
            for _, r in filtered.iterrows()
        }
        selected_label = st.selectbox("학생 선택", list(student_options.keys()))
        selected = student_options[selected_label]

        col_qr, col_info = st.columns([1, 2])
        with col_qr:
            qr_bytes = generate_qr_bytes(selected["id"], size=250)
            st.image(qr_bytes, caption="오늘 유효한 QR", width=200)

        with col_info:
            st.markdown(f"### {selected['name']}")
            st.markdown(f"- **학번:** {selected['student_number']}")
            st.markdown(f"- **학년/반:** {selected['grade']}학년 {selected['class_number']}반")
            allergies = selected.get("allergies") or []
            if allergies:
                allergy_names = {
                    "1":"난류","2":"우유","3":"메밀","4":"땅콩","5":"대두",
                    "6":"밀","7":"고등어","8":"게","9":"새우","10":"돼지고기",
                    "11":"복숭아","12":"토마토","13":"아황산류","14":"호두",
                    "15":"닭고기","16":"쇠고기","17":"오징어","18":"조개류",
                }
                labels = [f"{c}.{allergy_names.get(c,c)}" for c in allergies]
                st.error(f"⚠️ 알레르기: {', '.join(labels)}")
            else:
                st.success("알레르기 없음")

            st.download_button(
                "⬇️ QR 이미지 저장",
                data=qr_bytes,
                file_name=f"QR_{selected['student_number']}_{selected['name']}.png",
                mime="image/png",
            )


# ── 탭2: 학생증 PDF 출력 ──────────────────────────────────
with tab2:
    st.subheader("📄 학생증 PDF 일괄 출력")
    st.caption("A4 용지에 학생증을 2열×4행으로 배치합니다. QR은 학생마다 고정된 고유 코드입니다.")

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        pdf_grade = st.selectbox("학년", ["전체"] + [1, 2, 3], key="pdf_grade")
    with col_p2:
        pdf_class = st.selectbox("반", ["전체"] + list(range(1, 21)), key="pdf_class")
    with col_p3:
        st.markdown("<br>", unsafe_allow_html=True)

    pdf_targets = df.copy()
    if pdf_grade != "전체":
        pdf_targets = pdf_targets[pdf_targets["grade"] == pdf_grade]
    if pdf_class != "전체":
        pdf_targets = pdf_targets[pdf_targets["class_number"] == pdf_class]

    if pdf_targets.empty:
        st.warning("해당 조건의 학생이 없습니다.")
    else:
        st.info(f"총 **{len(pdf_targets)}명**의 학생증이 PDF에 포함됩니다.")

        # 인원 많으면 경고
        if len(pdf_targets) > 100:
            st.warning("⚠️ 100명 초과 시 생성에 시간이 걸릴 수 있습니다.")

        if st.button("📄 PDF 생성", type="primary", use_container_width=True):
            with st.spinner("PDF 생성 중... (QR 코드 포함)"):
                try:
                    student_list = pdf_targets.to_dict("records")
                    pdf_bytes = generate_student_cards_pdf(student_list)

                    grade_str = f"{pdf_grade}학년" if pdf_grade != "전체" else "전체"
                    class_str = f"{pdf_class}반" if pdf_class != "전체" else ""
                    filename = f"학생증_{grade_str}{class_str}.pdf"

                    st.success(f"✅ PDF 생성 완료! ({len(pdf_targets)}명)")
                    st.download_button(
                        label="⬇️ PDF 다운로드",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"❌ PDF 생성 실패: {e}")
