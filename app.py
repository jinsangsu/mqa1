
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import difflib

def is_duplicate_question(new_question, existing_questions, threshold=0.85):
    for q in existing_questions:
        similarity = difflib.SequenceMatcher(None, new_question.strip(), q.strip()).ratio()
        if similarity > threshold:
            return True
    return False

# 🔐 인증 설정
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
gc = gspread.authorize(credentials)

# 📄 구글시트 열기
def get_worksheet():
    spreadsheet_key = "1rJdNc_cYw3iOkOWCItjgRLw-EqjqImkZ"
    spreadsheet = gc.open_by_key(spreadsheet_key)
    worksheet = spreadsheet.get_worksheet(0)  # 첫 번째 탭
    return worksheet
# ✅ 타이틀 및 설명
st.set_page_config(page_title="mqa1 - 매니저 Q&A 입력", layout="centered")
st.title("📝 매니저 Q&A 등록 시스템 (mqa1)")
st.markdown("매니저님들께서는 아래 양식을 통해 자주 묻는 질문과 답변을 입력해주세요. 등록된 내용은 자동으로 본부장님 구글 시트에 반영됩니다.")


# 🖼️ UI 구성
st.markdown("### 📋 매니저 질의응답 등록")

with st.form("qna_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        manager_name = st.text_input("🧑‍💼 매니저 이름", placeholder="예: 박유림")
    with col2:
        region = st.text_input("📍 소속 지점/지역단", placeholder="예: 청주TC지점")

    question = st.text_area("❓ 질문 내용", placeholder="예: 자동이체 신청은 어떻게 하나요?")
    answer = st.text_area("💡 답변 내용", placeholder="예: KB홈페이지에서 신청 가능합니다...")

    submitted = st.form_submit_button("✅ 시트에 등록하기")

    if submitted:
        worksheet = get_worksheet()
        existing_rows = worksheet.get_all_values()
        existing_questions = [row[2] for row in existing_rows[1:] if len(row) > 2]  # 질문만 추출

        if is_duplicate_question(question, existing_questions):
            st.warning("⚠ 이미 유사한 질문이 등록되어 있습니다. 다시 확인해주세요.")
        else:
            worksheet.append_row([manager_name, region, question, answer])
            st.success("✅ 질의응답이 성공적으로 등록되었습니다!")

        data = worksheet.get_all_values()

st.markdown("---")
st.subheader("📄 최근 등록된 질문")

df = pd.DataFrame(data[1:], columns=data[0])
st.dataframe(df[["이름", "지역", "질문"]].tail(5))