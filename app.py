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

worksheet = get_worksheet()
data = worksheet.get_all_values()

df = pd.DataFrame(data[1:], columns=data[0])
df.reset_index(drop=True, inplace=True)
row_numbers = list(range(2, 2 + len(df)))   # df의 i번째 == 시트의 (i+2)번째 행

# 복합검색
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
        filtered_df = filtered_df.reset_index()  # index: 원본 df 행번호
        for idx, row in filtered_df.iterrows():
            with st.expander(f"질문: {row['질문']} | 작성자: {row['작성자']} | 날짜: {row['작성일']}"):
                st.write(f"**답변:** {row['답변']}")
                col_edit, col_del = st.columns([1, 1])

                if col_edit.button("✏️ 수정", key=f"edit_{idx}"):
                    with st.form(f"edit_form_{idx}"):
                        new_question = st.text_area("질문 내용", value=row["질문"])
                        new_answer = st.text_area("답변 내용", value=row["답변"])
                        new_writer = st.text_input("작성자", value=row["작성자"])
                        if st.form_submit_button("저장"):
                            real_row = row_numbers[row['index']]  # 원본 행번호 기반
                            worksheet.update_cell(real_row, 2, new_question)
                            worksheet.update_cell(real_row, 3, new_answer)
                            worksheet.update_cell(real_row, 4, new_writer)
                            st.success("✅ 수정이 완료되었습니다.")
                            st.experimental_rerun()

                if col_del.button("🗑️ 삭제", key=f"del_{idx}"):
                    confirm = st.warning("정말 삭제하시겠습니까? 이 작업은 복구할 수 없습니다.", icon="⚠️")
                    if st.button("진짜 삭제", key=f"confirm_del_{idx}"):
                        real_row = row_numbers[row['index']]
                        worksheet.delete_rows(real_row)
                        st.success("✅ 삭제가 완료되었습니다.")
                        st.experimental_rerun()
