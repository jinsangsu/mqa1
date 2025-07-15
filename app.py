import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import difflib
import datetime

# ======= 기존 함수 및 인증 =======
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

st.markdown("""
<style>
@media screen and (max-width: 600px) {
    .title-text { font-size: 20px !important; padding: 0 10px; }
}
@media screen and (min-width: 601px) {
    .title-text { font-size: 30px !important; }
}
</style>
<div style='text-align: center; margin-top: 20px; margin-bottom: 10px;'>
    <h1 class='title-text' style='font-weight: 900; margin: 0px; line-height: 1.4;'>
        담대한 전환! 당당한 성장! 충청호남본부!!
    </h1>
    <hr style='border: none; border-top: 2px solid #eee; width: 60%; margin: 15px auto 25px;'>
</div>
""", unsafe_allow_html=True)

st.markdown("### 📋 영업가족 질의응답 등록")

# ======= Q&A 등록 폼 =======
with st.form("qna_form", clear_on_submit=True):
    manager_name = st.text_input("🧑‍💼 매니저 이름", placeholder="예: 박유림")
    question = st.text_area("❓ 질문 내용", placeholder="예: 자동이체 신청은 어떻게 하나요?")
    answer = st.text_area("💡 답변 내용", placeholder="예: KB홈페이지에서 신청 가능합니다...")
    submitted = st.form_submit_button("✅ 시트에 등록하기")

worksheet = get_worksheet()
data = worksheet.get_all_values()

# 등록 처리
if submitted:
    existing_rows = data
    existing_questions = [row[1] for row in existing_rows[1:] if len(row) > 1]
    if is_duplicate_question(question, existing_questions):
        st.warning("⚠ 이미 유사한 질문이 등록되어 있습니다. 다시 확인해주세요.")
    else:
        next_index = len(existing_rows)
        today = datetime.date.today().strftime("%Y-%m-%d")
        worksheet.append_row([
            next_index, question, answer, manager_name, today
        ])
        st.success("✅ 질의응답이 성공적으로 등록되었습니다!")
        data = worksheet.get_all_values()  # 새로고침

st.markdown("---")
st.subheader("🔎 Q&A 검색 후 수정·삭제")

# ======= 데이터프레임 준비 =======
df = pd.DataFrame(data[1:], columns=data[0])
df.reset_index(drop=True, inplace=True)

# ======= 검색창 =======
search_query = st.text_input("질문 또는 답변 내용 키워드로 검색", "")

if search_query.strip() != "":
    # 키워드가 하나라도 포함된 행만 추출
    filtered_df = df[df["질문"].str.contains(search_query, case=False, na=False) | 
                     df["답변"].str.contains(search_query, case=False, na=False)]
else:
    filtered_df = df.copy()  # 아무것도 입력 안하면 전체

if filtered_df.empty:
    st.info("검색 결과가 없습니다.")
else:
    for idx, row in filtered_df.iterrows():
        with st.expander(f"질문: {row['질문']} | 작성자: {row['작성자']} | 날짜: {row['작성일']}"):
            st.write(f"**답변:** {row['답변']}")
            col_edit, col_del = st.columns([1, 1])
            # ========== [수정] ==========
            if col_edit.button("✏️ 수정", key=f"edit_{idx}"):
                with st.form(f"edit_form_{idx}"):
                    new_question = st.text_area("질문 내용", value=row["질문"])
                    new_answer = st.text_area("답변 내용", value=row["답변"])
                    new_writer = st.text_input("작성자", value=row["작성자"])
                    if st.form_submit_button("저장"):
                        real_row = idx + 2  # 시트에서의 실제 행 번호
                        worksheet.update_cell(real_row, 2, new_question)
                        worksheet.update_cell(real_row, 3, new_answer)
                        worksheet.update_cell(real_row, 4, new_writer)
                        st.success("✅ 수정이 완료되었습니다.")
                        st.experimental_rerun()
            # ========== [삭제] ==========
            if col_del.button("🗑️ 삭제", key=f"del_{idx}"):
                confirm = st.warning("정말 삭제하시겠습니까? 이 작업은 복구할 수 없습니다.", icon="⚠️")
                if st.button("진짜 삭제", key=f"confirm_del_{idx}"):
                    real_row = idx + 2
                    worksheet.delete_rows(real_row)
                    st.success("✅ 삭제가 완료되었습니다.")
                    st.experimental_rerun()

# 최근 5개 미리보기
st.markdown("#### 🗂️ 최근 5개 질문 미리보기")
st.dataframe(df[["작성자", "질문"]].tail(5))
