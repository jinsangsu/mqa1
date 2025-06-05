
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

# 🔐 인증 설정
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)
gc = gspread.authorize(credentials)

# 📄 구글시트 열기
def get_worksheet():
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1aPo40QnxQrcY7yEUM6iHa-9XJU-MIIqsjapGP7UnKIo/edit"
    spreadsheet = gc.open_by_url(spreadsheet_url)
    worksheet = spreadsheet.get_worksheet(0)
    return worksheet

# ✅ 타이틀 및 설명
st.set_page_config(page_title="충호본부 Q&A 등록", layout="centered")

col1, col2 = st.columns([1, 4])

with col1:
    st.image("title_image.png", width=130)

with col2:
    st.markdown("""
        ## 담대한 전환! 당당한 성장!  
        ---
        안녕하세요.

        항상 현장에서 최선을 다해주시는  
        우리 충청호남본부 임직원 여러분께 깊이 감사드립니다.

        이번에 설계사분들의 반복 질문에 신속하게 대응하고  
        지점의 운영 효율을 높이기 위해 Q&A 시스템을 준비했습니다.

        여러분의 경험과 지식이  
        현장의 힘이 되고 동료에게 큰 도움이 될 것이고

        이러한 실천은  
        우리 충청호남본부의 변화와 성장에 큰 기여를 할 것입니다.

        감사합니다.
    """)


# 🖼️ UI 구성
st.markdown("### 📋 영업가족 질의응답 등록")

with st.form("qna_form", clear_on_submit=True):
    col1 = st.columns(1)[0]  # ✅ 올바른 방식

    with col1:
        manager_name = st.text_input("🧑‍💼 매니저 이름", placeholder="예: 박유림")
        question = st.text_area("❓ 질문 내용", placeholder="예: 자동이체 신청은 어떻게 하나요?")
        answer = st.text_area("💡 답변 내용", placeholder="예: KB홈페이지에서 신청 가능합니다...")

    submitted = st.form_submit_button("✅ 시트에 등록하기")

if submitted:
    worksheet = get_worksheet()
    existing_rows = worksheet.get_all_values()
    existing_questions = [row[1] for row in existing_rows[1:] if len(row) > 1]  # 질문 열만

    if is_duplicate_question(question, existing_questions):
        st.warning("⚠ 이미 유사한 질문이 등록되어 있습니다. 다시 확인해주세요.")
    else:
        next_index = len(existing_rows)
        today = datetime.date.today().strftime("%Y-%m-%d")

        worksheet.append_row([
            next_index,         # 번호
            question,           # 질문
            answer,             # 답변
            manager_name,       # 작성자
            today               # 작성일
        ])

        st.success("✅ 질의응답이 성공적으로 등록되었습니다!")

        data = worksheet.get_all_values()
else:
    worksheet = get_worksheet()
    data = worksheet.get_all_values()

st.markdown("---")
st.subheader("📄 최근 등록된 질문")

df = pd.DataFrame(data[1:], columns=data[0])
st.dataframe(df[["작성자", "질문"]].tail(5))