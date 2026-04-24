"""학생 정보 관리 페이지"""
import streamlit as st
import pandas as pd
from loguru import logger

from utils.auth import require_login, is_admin, render_sidebar_nav
from utils.db import get_client, get_service_client, safe_query

st.set_page_config(page_title="학생 관리", page_icon="👨‍🎓", layout="wide")
require_login()
render_sidebar_nav()

# ── DB 함수 ───────────────────────────────────────────────

def load_students():
    data, err = safe_query(
        lambda: get_client()
            .table("students")
            .select("*")
            .order("grade").order("class_number").order("student_number")
            .execute(),
        "학생 목록 조회 실패"
    )
    return data or [], err


def upsert_students(rows: list[dict]):
    """신규/기존 학생 upsert (student_number 기준)"""
    return safe_query(
        lambda: get_client()
            .table("students")
            .upsert(rows, on_conflict="student_number")
            .execute(),
        "학생 저장 실패"
    )


def update_student(student_id: str, payload: dict):
    return safe_query(
        lambda: get_client()
            .table("students")
            .update(payload)
            .eq("id", student_id)
            .execute(),
        "학생 정보 수정 실패"
    )


def delete_student(student_id: str):
    return safe_query(
        lambda: get_client()
            .table("students")
            .update({"is_active": False})
            .eq("id", student_id)
            .execute(),
        "학생 삭제 실패"
    )


def delete_all_students_hard() -> str | None:
    """전체 학생 완전 삭제 (CASCADE로 급식 기록도 삭제)"""
    try:
        get_service_client().table("students").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
        return None
    except Exception as e:
        logger.error(f"학생 일괄 삭제 실패: {e}")
        return str(e)


def promote_students():
    """전체 재학생 학년 +1, 3학년은 비활성화"""
    client = get_client()
    # 3학년 → 비활성화
    safe_query(
        lambda: client.table("students")
            .update({"is_active": False})
            .eq("grade", 3).eq("is_active", True)
            .execute(),
        "3학년 졸업 처리 실패"
    )
    # 1,2학년 → +1
    for g in [2, 1]:
        safe_query(
            lambda g=g: client.table("students")
                .update({"grade": g + 1})
                .eq("grade", g).eq("is_active", True)
                .execute(),
            f"{g}학년 진급 실패"
        )


# ── CSV 검증 ──────────────────────────────────────────────

REQUIRED_COLS = {"student_number", "name", "grade", "class_number"}

def validate_csv(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        errors.append(f"필수 열 누락: {', '.join(missing)}")
        return errors

    for i, row in df.iterrows():
        row_num = i + 2  # 헤더 포함 행 번호
        if pd.isna(row["student_number"]) or str(row["student_number"]).strip() == "":
            errors.append(f"{row_num}행: 학번이 비어 있습니다.")
        if pd.isna(row["name"]) or str(row["name"]).strip() == "":
            errors.append(f"{row_num}행: 이름이 비어 있습니다.")
        try:
            grade = int(row["grade"])
            if grade not in (1, 2, 3):
                errors.append(f"{row_num}행: 학년은 1~3이어야 합니다. (현재: {grade})")
        except (ValueError, TypeError):
            errors.append(f"{row_num}행: 학년이 숫자가 아닙니다. (현재: {row['grade']})")
        try:
            cls = int(row["class_number"])
            if not (1 <= cls <= 20):
                errors.append(f"{row_num}행: 반은 1~20이어야 합니다. (현재: {cls})")
        except (ValueError, TypeError):
            errors.append(f"{row_num}행: 반이 숫자가 아닙니다. (현재: {row['class_number']})")

    return errors


def csv_to_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "student_number": str(row["student_number"]).strip(),
            "name": str(row["name"]).strip(),
            "grade": int(row["grade"]),
            "class_number": int(row["class_number"]),
            "class_roll_number": int(row["class_roll_number"]) if "class_roll_number" in df.columns and not pd.isna(row.get("class_roll_number", float("nan"))) else None,
            "is_active": True,
        })
    return rows


# ════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════

st.title("👨‍🎓 학생 정보 관리")

tab1, tab2, tab3 = st.tabs(["📋 학생 목록", "📤 CSV 업로드", "🎓 학년 진급"])


# ── 탭1: 학생 목록 ────────────────────────────────────────
with tab1:
    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 3])
    with col_filter1:
        filter_grade = st.selectbox("학년 필터", ["전체", 1, 2, 3])
    with col_filter2:
        filter_class = st.selectbox("반 필터", ["전체"] + list(range(1, 21)))
    with col_filter3:
        search_name = st.text_input("이름/학번 검색", placeholder="이름 또는 학번 입력")

    students, err = load_students()
    if err:
        st.error(f"❌ {err}")
    elif not students:
        st.info("등록된 학생이 없습니다. CSV 업로드 탭에서 학생을 추가하세요.")
    else:
        df = pd.DataFrame(students)

        # 필터 적용
        if filter_grade != "전체":
            df = df[df["grade"] == filter_grade]
        if filter_class != "전체":
            df = df[df["class_number"] == filter_class]
        if search_name:
            mask = (
                df["name"].str.contains(search_name, na=False) |
                df["student_number"].str.contains(search_name, na=False)
            )
            df = df[mask]

        st.caption(f"총 **{len(df)}명** 표시 중 (전체 {len(students)}명)")

        # 표시용 컬럼 정리
        display_df = df[["grade", "class_number", "class_roll_number", "name", "student_number"]].copy()
        display_df["class_roll_number"] = display_df["class_roll_number"].apply(
            lambda x: int(x) if pd.notna(x) else ""
        )
        display_df.columns = ["학년", "반", "번호", "이름", "학번"]

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 전체 일괄 삭제 (관리자만)
        if is_admin():
            st.divider()
            with st.expander("🔥 전체 학생 일괄 삭제"):
                st.warning(f"현재 등록된 **{len(students)}명** 전체를 삭제합니다. "
                           "급식 수령 기록도 함께 삭제되며 되돌릴 수 없습니다.")
                confirm_all = st.text_input("확인 문구: `delete all students`",
                                             key="confirm_delete_all")
                if st.button("🔥 전체 삭제 실행", type="primary",
                             use_container_width=True,
                             disabled=(confirm_all != "delete all students")):
                    with st.spinner("삭제 중..."):
                        err = delete_all_students_hard()
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("✅ 전체 학생이 삭제되었습니다.")
                        st.rerun()

        # 수정/삭제 (관리자만)
        if is_admin():
            st.divider()
            st.subheader("✏️ 학생 정보 수정 / 삭제")
            st.caption("수정할 학생의 학번을 입력하세요.")

            edit_number = st.text_input("학번 입력", key="edit_number")
            if edit_number:
                target = next(
                    (s for s in students if s["student_number"] == edit_number), None
                )
                if not target:
                    st.warning("해당 학번의 학생을 찾을 수 없습니다.")
                else:
                    with st.form("edit_form"):
                        st.markdown(f"**현재 정보:** {target['name']} ({target['grade']}학년 {target['class_number']}반)")
                        new_name = st.text_input("이름", value=target["name"])
                        new_grade = st.selectbox("학년", [1, 2, 3], index=target["grade"] - 1)
                        col_class, col_roll = st.columns(2)
                        with col_class:
                            new_class = st.number_input("반", min_value=1, max_value=20,
                                                         value=target["class_number"])
                        with col_roll:
                            new_roll = st.number_input("번호", min_value=1, max_value=99,
                                                        value=int(target.get("class_roll_number") or 1))
                        new_number = st.text_input("학번", value=target["student_number"])

                        col_save, col_del = st.columns(2)
                        with col_save:
                            save = st.form_submit_button("💾 저장", use_container_width=True)
                        with col_del:
                            delete = st.form_submit_button("🗑️ 삭제 (비활성화)",
                                                            use_container_width=True,
                                                            type="secondary")

                    if save:
                        _, err = update_student(target["id"], {
                            "student_number": new_number.strip(),
                            "name": new_name,
                            "grade": new_grade,
                            "class_number": new_class,
                            "class_roll_number": new_roll,
                        })
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            st.success("✅ 수정 완료!")
                            st.rerun()

                    if delete:
                        _, err = delete_student(target["id"])
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            st.success(f"✅ {target['name']} 학생이 비활성화되었습니다.")
                            st.rerun()


# ── 탭2: CSV 업로드 ───────────────────────────────────────
with tab2:
    st.subheader("📤 CSV 파일로 학생 일괄 등록")

    with st.expander("📌 CSV 형식 안내"):
        st.markdown("""
| 열 이름 | 설명 | 필수 |
|---|---|---|
| `student_number` | 학번 (고유값) | ✅ |
| `name` | 이름 | ✅ |
| `grade` | 학년 (1~3) | ✅ |
| `class_number` | 반 (1~20) | ✅ |
| `class_roll_number` | 번호 (1~99) | ❌ |

**예시:**
```
student_number,name,grade,class_number,class_roll_number
20240101,홍길동,1,1,1
20240102,김철수,1,1,2
```
        """)

    # 샘플 CSV 다운로드
    sample_csv = "student_number,name,grade,class_number,class_roll_number\n20240101,홍길동,1,1,1\n20240102,김철수,1,2,1\n"
    st.download_button(
        "⬇️ 샘플 CSV 다운로드",
        data=sample_csv.encode("utf-8-sig"),
        file_name="학생_샘플.csv",
        mime="text/csv",
    )

    uploaded = st.file_uploader("CSV 파일 선택", type=["csv"])

    if uploaded:
        try:
            df_upload = pd.read_csv(uploaded, dtype=str)
        except Exception as e:
            st.error(f"❌ 파일을 읽을 수 없습니다: {e}")
            st.stop()

        st.subheader("미리보기")
        st.dataframe(df_upload.head(10), use_container_width=True, hide_index=True)

        errors = validate_csv(df_upload)
        if errors:
            st.error("❌ 형식 오류가 있습니다. 수정 후 다시 업로드하세요.")
            for e in errors[:10]:
                st.markdown(f"- {e}")
            if len(errors) > 10:
                st.caption(f"... 외 {len(errors)-10}개 오류")
        else:
            st.success(f"✅ 형식 검증 통과! 총 {len(df_upload)}명")
            if is_admin():
                if st.button("📥 DB에 저장", type="primary", use_container_width=True):
                    rows = csv_to_rows(df_upload)
                    with st.spinner("저장 중..."):
                        _, err = upsert_students(rows)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success(f"✅ {len(rows)}명 저장 완료! (기존 학생은 업데이트)")
                        st.balloons()
            else:
                st.warning("⚠️ 관리자만 저장할 수 있습니다.")


# ── 탭3: 학년 진급 ────────────────────────────────────────
with tab3:
    st.subheader("🎓 학년 진급 일괄 처리")

    if not is_admin():
        st.warning("⚠️ 관리자만 사용할 수 있습니다.")
    else:
        st.warning("""
⚠️ **주의사항**
- 1학년 → 2학년, 2학년 → 3학년으로 일괄 진급됩니다.
- 3학년은 졸업 처리(비활성화)됩니다.
- **이 작업은 되돌릴 수 없습니다.** 새 학년도 시작 시에만 실행하세요.
        """)

        students_now, _ = load_students()
        if students_now:
            grade_counts = pd.DataFrame(students_now)["grade"].value_counts().sort_index()
            col1, col2, col3 = st.columns(3)
            with col1:
                cnt1 = grade_counts.get(1, 0)
                st.metric("1학년", f"{cnt1}명", "→ 2학년으로 진급")
            with col2:
                cnt2 = grade_counts.get(2, 0)
                st.metric("2학년", f"{cnt2}명", "→ 3학년으로 진급")
            with col3:
                cnt3 = grade_counts.get(3, 0)
                st.metric("3학년", f"{cnt3}명", "→ 졸업(비활성화)")

        confirm = st.checkbox("위 내용을 확인했으며, 진급 처리를 실행합니다.")
        if confirm:
            if st.button("🎓 진급 처리 실행", type="primary", use_container_width=True):
                with st.spinner("진급 처리 중..."):
                    promote_students()
                st.success("✅ 학년 진급 처리 완료!")
                st.rerun()
