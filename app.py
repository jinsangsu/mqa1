import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import difflib
import datetime

def is_duplicate_question(new_question, existing_questions, threshold=0.85):
    for q in existing_questions:
        similarity = difflib.SequenceMatcher(None, new_question.strip(), q.strip()).ratio()
        if similarity > threshold:
            return True
    return False

# 🔐 인증
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
gc = gspread.authorize(credentials)

def get_worksheet():
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1aPo40QnxQrcY7yEUM6iHa-9XJU-MIIqsjapGP7UnKIo/edit"
    spreadsheet = gc.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.get_worksheet(0)
    return worksheet

# ====== 데이터 불러오기 ======
worksheet = get_worksheet()
data = worksheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

if "번호" in df.columns:
    df["번호"] = df["번호"].astype(int)
else:
    st.error("시트에 '번호' 컬럼이 없습니다. 시트 구조를 확인하세요.")

# ========== Q&A 등록 폼 ==========
st.markdown("### 📋 영업가족 질의응답 등록")
with st.form("qna_form", clear_on_submit=True):
    manager_name = st.text_input("🧑‍💼 매니저 이름", placeholder="예: 박유림")
    question = st.text_area("❓ 질문 내용", placeholder="예: 자동이체 신청은 어떻게 하나요?")
    answer = st.text_area("💡 답변 내용", placeholder="예: KB홈페이지에서 신청 가능합니다...")
    submitted = st.form_submit_button("✅ 시트에 등록하기")

if submitted:
    existing_questions = df["질문"].tolist()
    if is_duplicate_question(question, existing_questions):
        st.warning("⚠ 이미 유사한 질문이 등록되어 있습니다. 다시 확인해주세요.")
    else:
        # 새 번호(가장 큰 번호+1, 데이터가 없으면 1)
        if len(df) == 0:
            new_no = 1
        else:
            new_no = df["번호"].max() + 1
        today = datetime.date.today().strftime("%Y-%m-%d")
        worksheet.append_row([
            new_no, question, answer, manager_name, today
        ])
        st.success("✅ 질의응답이 성공적으로 등록되었습니다!")
        st.experimental_rerun()

st.markdown("---")
st.subheader("🔎 Q&A 복합검색(키워드, 작성자) 후 수정·삭제")

# ======= 복합검색: 키워드 + 작성자 이름 =======
search_query = st.text_input("질문/답변 내용 키워드로 검색", "")
search_writer = st.text_input("작성자 이름으로 검색", "")

filtered_df = df.copy()
if search_query.strip():
    filtered_df = filtered_df[
        filtered_df["질문"].str.contains(search_query, case=False, na=False) |
        filtered_df["답변"].str.contains(search_query, case=False, na=False)
    ]
if search_writer.strip():
    filtered_df = filtered_df[
        filtered_df["작성자"].str.contains(search_writer, case=False, na=False)
    ]

if search_query.strip() or search_writer.strip():
    if filtered_df.empty:
        st.info("검색 결과가 없습니다.")
    else:
        filtered_df = filtered_df.reset_index(drop=True)
        for idx, row in filtered_df.iterrows():
            with st.expander(f"질문: {row['질문']} | 작성자: {row['작성자']} | 날짜: {row['작성일']}"):
                st.write(f"**답변:** {row['답변']}")
                col_edit, col_del = st.columns([1, 1])
                # ----------- 수정 -----------
                if col_edit.button(f"✏️ 수정_{row['번호']}", key=f"edit_{row['번호']}"):
                    with st.form(f"edit_form_{row['번호']}"):
                        new_question = st.text_area("질문 내용", value=row["질문"])
                        new_answer = st.text_area("답변 내용", value=row["답변"])
                        new_writer = st.text_input("작성자", value=row["작성자"])
                        submitted_edit = st.form_submit_button(f"저장_{row['번호']}")
                        if submitted_edit:
                            try:
                                # 실제 시트에서 데이터 행 번호 = 번호 + 1 (1행은 헤더)
                                worksheet.update_cell(int(row["번호"])+1, 2, new_question)
                                worksheet.update_cell(int(row["번호"])+1, 3, new_answer)
                                worksheet.update_cell(int(row["번호"])+1, 4, new_writer)
                                st.success("✅ 수정이 완료되었습니다.")
                                st.experimental_rerun()
                            except Exception as e:
                                st.error(f"에러 발생: {e}")
                # ----------- 삭제 -----------
                if col_del.button(f"🗑️ 삭제_{row['번호']}", key=f"del_{row['번호']}"):
                    confirm = st.warning("정말 삭제하시겠습니까? 이 작업은 복구할 수 없습니다.", icon="⚠️")
                    if st.button(f"진짜 삭제_{row['번호']}", key=f"confirm_del_{row['번호']}"):
                        try:
                            worksheet.delete_rows(int(row["번호"])+1)
                            st.success("✅ 삭제가 완료되었습니다.")
                            st.experimental_rerun()
                        except Exception as e:
                            st.error(f"에러 발생: {e}")
else:
    st.info("검색 조건(질문/답변 키워드 또는 작성자 이름)을 입력하시면 결과가 표시됩니다.")

# ====== 최근 5개 질문 미리보기 ======
st.markdown("#### 🗂️ 최근 5개 질문 미리보기")
if not df.empty and "작성자" in df.columns and "질문" in df.columns:
    for idx, row in df[["작성자", "질문"]].tail(5).iterrows():
        st.markdown(f"- **{row['작성자']}**: {row['질문']}")
else:
    st.info("최근 질문 데이터가 없습니다. (컬럼명 또는 데이터 확인 필요)")
