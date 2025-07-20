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

# ------- 디자인 부분(기존 CSS 유지) -------
st.markdown("""
<style>
@media (prefers-color-scheme: dark) {
    .stApp { background-color: #1A1A1A !important; color: #eee !important; }
    html, body, .stTextInput>div>div>input, .stTextArea>div>textarea,
    .stForm, .stMarkdown, .stSubheader, .stHeader {
        background-color: #222 !important; color: #fff !important;
    }
}
@media (prefers-color-scheme: light) {
    .stApp { background-color: #fff !important; color: #222 !important; }
}
.stApp, .title-text, .element-container, .block-container, .stColumn, .stContainer, .stMarkdown, div[role="list"], hr {
    margin-top: 0px !important; margin-bottom: 0px !important; padding-top: 0px !important; padding-bottom: 0px !important;
}
.intro-container { margin-top: 0px !important; margin-bottom: 0px !important; padding-top: 0px !important; padding-bottom: 0px !important; }
.stColumns { gap: 8px !important; margin-top: 0px !important; margin-bottom: 0px !important; }
.stForm, .stTextInput, .stTextArea, .stButton, .stMarkdown, .stSubheader, .stHeader { margin-top: 0px !important; margin-bottom: 0px !important; padding-top: 2px !important; padding-bottom: 2px !important; }
hr { margin-top: 2px !important; margin-bottom: 2px !important; }
@media screen and (max-width: 768px) {
    .intro-container { flex-direction: column !important; align-items: center !important; }
}
</style>
""", unsafe_allow_html=True)

# ------- 상단 캐릭터+인사말 -------
container = st.container()
with container:
    cols = st.columns([1, 4])
    with cols[0]:
        st.image("title_image.png", width=130)
    with cols[1]:
        st.markdown("""
        <div style="font-size: 15px; line-height: 1.6; font-weight: 500; color: #222;">
            <p><strong>안녕하세요.</strong></p>
            <p>항상 현장에서 최선을 다해주시는 <strong>충청호남본부 임직원 여러분께 깊이 감사드립니다.</strong></p>
            <p>이번에 설계사분들의 반복 질문에 신속하게 대응하고 지점의 운영 효율을 높이기 위해 <strong>Q&A 시스템</strong>을 준비했습니다.</p>
            <p>현장에서 자주 반복되는 질문과 그에 대한 명확한 답변을 등록해주시면, 설계사분들이 스스로 찾아보는 데 큰 도움이 될 것입니다.</p>
            <p>바쁘시겠지만 <strong>하루에 하나씩</strong>만이라도 참여해 주신다면 우리 충청호남본부의 변화와 성장에 큰 기여가 될 것입니다.</p>
            <p>감사합니다.</p>
        </div>
        """, unsafe_allow_html=True)

# ========== Q&A 등록 폼 ==========
st.markdown("### 📋 영업가족 질의응답 등록")
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
        data = worksheet.get_all_values()

st.markdown("---")
st.subheader("🔎 Q&A 복합검색(키워드, 작성자) 후 수정·삭제")

# ======= 데이터프레임 준비 및 시트 행번호 매핑 =======
df = pd.DataFrame(data[1:], columns=data[0])
df["rowid"] = range(2, 2 + len(df))  # 2번 행부터 실제 시트 rowid 부여

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
        # ⭐️ 인덱스 리셋! 'index' 컬럼이 원본 df에서의 실제 인덱스(=row_numbers의 idx)
        filtered_df = filtered_df.reset_index()  # index 컬럼 추가

        for idx, row in filtered_df.iterrows():
            with st.expander(f"질문: {row['질문']} | 작성자: {row['작성자']} | 날짜: {row['작성일']}"):
                st.write(f"**답변:** {row['답변']}")
                col_edit, col_del = st.columns([1, 1])
                # ----------- 수정 -----------
                if col_edit.button("✏️ 수정", key=f"edit_{idx}"):
                    with st.form(f"edit_form_{idx}"):
                        new_question = st.text_area("질문 내용", value=row["질문"])
                        new_answer = st.text_area("답변 내용", value=row["답변"])
                        new_writer = st.text_input("작성자", value=row["작성자"])
                        if st.form_submit_button("저장"):
                         st.write("저장 버튼 눌림!")  # 1. 버튼 동작 확인
                         try:    
                            worksheet.update_cell(row["rowid"], 2, new_question)
                            worksheet.update_cell(row["rowid"], 3, new_answer)
                            worksheet.update_cell(row["rowid"], 4, new_writer)
                         except Exception as e:
                            st.error(f"에러 발생: {e}")
                            st.success("✅ 수정이 완료되었습니다.")

                            data = worksheet.get_all_values()
                            st.experimental_rerun()
                # ----------- 삭제 -----------
                if col_del.button("🗑️ 삭제", key=f"del_{idx}"):
                    confirm = st.warning("정말 삭제하시겠습니까? 이 작업은 복구할 수 없습니다.", icon="⚠️")
                    if st.button("진짜 삭제", key=f"confirm_del_{idx}"):
                        
                        worksheet.delete_rows(row["rowid"])
                        st.success("✅ 삭제가 완료되었습니다.")
                        data = worksheet.get_all_values()
                        st.experimental_rerun()
else:
    st.info("검색 조건(질문/답변 키워드 또는 작성자 이름)을 입력하시면 결과가 표시됩니다.")

st.markdown("#### 🗂️ 최근 5개 질문 미리보기")
if not df.empty and "작성자" in df.columns and "질문" in df.columns:
    for idx, row in df[["작성자", "질문"]].tail(5).iterrows():
        st.markdown(f"- **{row['작성자']}**: {row['질문']}")
else:
    st.info("최근 질문 데이터가 없습니다. (컬럼명 또는 데이터 확인 필요)")
