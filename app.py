import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import difflib
import datetime
import os
import base64

def get_character_img_base64(img_path):
    if os.path.exists(img_path):
        with open(img_path, "rb") as img_file:
            b64 = base64.b64encode(img_file.read()).decode("utf-8")
            return f"data:image/webp;base64,{b64}"
    return None

def is_duplicate_question(new_question, existing_questions, threshold=0.85):
    for q in existing_questions:
        similarity = difflib.SequenceMatcher(None, new_question.strip(), q.strip()).ratio()
        if similarity > threshold:
            return True
    return False

# 🔐 구글 인증
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

# ====== 디자인 및 인삿말 ======
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
html, body {
    padding-top: 1.5rem !important;
    margin-top: 1.5rem !important;
}
.block-container { padding-top: 1rem !important; }

header[data-testid="stHeader"] {
    display: none !important;
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
char_img = get_character_img_base64("title_image.png")

intro_html = f"""
<div style="display: flex; align-items: flex-start; gap: 14px; margin-bottom: 1rem;">
  <img src="{char_img}" width="85" style="border-radius:16px; border:1px solid #eee;">
  <div style="font-size: 15px; line-height: 1.6; font-weight: 500; color: #222;">
    <p style="margin-top: 0;"><strong>안녕하세요.</strong></p>
    <strong>항상 최선을 다해주셔서 감사드려요~</strong>
    <strong>이번에 영업가족들의 질문에 답변하는 Q&A 시스템을 준비했습니다.</strong>
    <strong>
      (<a href="http://chung2.streamlit.app" target="_blank" style="color: red; text-decoration: none;">
        앱주소 : http://chung2.streamlit.app
      </a>)
    </strong>
    <strong>자주하는 질문과 답변을 등록해주시면</strong>
    <strong>업무에 많은 도움이 될것입니다.</strong>
    <strong>잘 부탁드립니다!</strong>
  </div>
</div>
"""

st.markdown(intro_html, unsafe_allow_html=True)# ====== 데이터 불러오기 ======
worksheet = get_worksheet()
data = worksheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])

if "번호" in df.columns:
    df["번호"] = df["번호"].astype(int)
else:
    st.error("시트에 '번호' 컬럼이 없습니다. 시트 구조를 확인하세요.")

# ========== Q&A 등록 폼 ==========
if 'reset' not in st.session_state:
    st.session_state['reset'] = False

if st.session_state['reset']:
    st.session_state['input_manager'] = ""
    st.session_state['input_question'] = ""
    st.session_state['input_answer'] = ""
    st.session_state['reset'] = False

st.markdown("### 📋 영업가족 질의응답 등록")

manager_name = st.text_input("🧑‍💼 매니저 이름", placeholder="예: 박유림", key="input_manager")
question = st.text_area("❓ 질문 내용", placeholder="예: 자동이체 신청은 어떻게 하나요?", key="input_question", height=50)

existing_questions = df["질문"].tolist()
if question.strip():
    # 유사질문(70%↑)인 DataFrame의 행 3개까지 뽑기
    similar_rows = df[
        df["질문"].apply(lambda q: difflib.SequenceMatcher(None, question.strip(), str(q).strip()).ratio() >= 0.65)
    ].head(3)
    if not similar_rows.empty:
        for _, row in similar_rows.iterrows():
            st.info(
                f"⚠️ 유사질문:\n{row['질문']}\n\n💡 등록된 답변:\n{row['답변']}"
            )
answer = st.text_area("💡 답변 내용", placeholder="예: KB홈페이지에서 신청 가능합니다...", key="input_answer", height=50)

if st.button("✅ 시트에 등록하기"):
    # 1. 질문/답변 필수값 체크 먼저!
    if not question.strip() or not answer.strip():
        st.error("⚠ 질문과 답변은 필수 입력입니다. 반드시 내용을 입력해 주세요.")
    else:
        existing_questions = [q.strip() for q in df["질문"].tolist()]
        if question.strip() and question.strip() in existing_questions:
            st.warning("⚠ 이미 동일한 질문이 등록되어 있습니다. 다시 확인해주세요.")
        else:
            if len(df) == 0:
                new_no = 1
            else:
                new_no = df["번호"].max() + 1
            today = datetime.date.today().strftime("%Y-%m-%d")
            try:
                worksheet.append_row([
                    str(new_no),
                    str(question),
                    str(answer),
                    str(manager_name),
                    str(today)
                ])
                st.success("✅ 질의응답이 성공적으로 등록되었습니다!")
                st.session_state['reset'] = True
                st.rerun()
            except Exception as e:
                st.error(f"등록 중 에러 발생: {e}")
st.markdown("---")
st.subheader("🔎 Q&A 복합검색(키워드, 작성자) 후 수정·삭제")

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

edit_num = st.session_state.get("edit_num", None)
delete_num = st.session_state.get("delete_num", None)

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
                if edit_num == row["번호"]:
                    with st.form(f"edit_form_{row['번호']}"):
                        new_question = st.text_area("질문 내용", value=row["질문"])
                        new_answer = st.text_area("답변 내용", value=row["답변"])
                        new_writer = st.text_input("작성자", value=row["작성자"])
                        submitted_edit = st.form_submit_button(f"저장_{row['번호']}")
                        if submitted_edit:
                            try:
                                번호_셀 = worksheet.find(str(row["번호"]))
                                행번호 = 번호_셀.row
                                worksheet.update_cell(행번호, 2, str(new_question))
                                worksheet.update_cell(행번호, 3, str(new_answer))
                                worksheet.update_cell(행번호, 4, str(new_writer))
                                st.success("✅ 수정이 완료되었습니다.")
                                del st.session_state["edit_num"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"수정 중 에러 발생: {e}")
                else:
                    if col_edit.button(f"✏️ 수정_{row['번호']}", key=f"edit_{row['번호']}"):
                        st.session_state["edit_num"] = row["번호"]
                        st.rerun()

                # ----------- 삭제 -----------
                if delete_num == row["번호"]:
                    st.warning("정말 삭제하시겠습니까? 이 작업은 복구할 수 없습니다.", icon="⚠️")
                    col_confirm, col_cancel = st.columns([1, 1])
                    with col_confirm:
                        if st.button(f"진짜 삭제_{row['번호']}", key=f"confirm_del_{row['번호']}"):
                            try:
                                번호_셀 = worksheet.find(str(row["번호"]))
                                행번호 = 번호_셀.row
                                worksheet.delete_rows(행번호)
                                st.success("✅ 삭제가 완료되었습니다.")
                                del st.session_state["delete_num"]
                                st.rerun()
                            except Exception as e:
                                st.error(f"삭제 중 에러 발생: {e}")
                    with col_cancel:
                        if st.button(f"취소_{row['번호']}", key=f"cancel_del_{row['번호']}"):
                            del st.session_state["delete_num"]
                            st.rerun()
                else:
                    if col_del.button(f"🗂️ 삭제_{row['번호']}", key=f"del_{row['번호']}"):
                        st.session_state["delete_num"] = row["번호"]
                        st.rerun()
else:
    st.info("검색 조건(질문/답변 키워드 또는 작성자 이름)을 입력하시면 결과가 표시됩니다.")

st.markdown("#### 🗂️ 최근 5개 질문 미리보기")
if not df.empty and "작성자" in df.columns and "질문" in df.columns:
    for idx, row in df[["작성자", "질문"]].tail(5).iterrows():
        st.markdown(f"- **{row['작성자']}**: {row['질문']}")
else:
    st.info("최근 질문 데이터가 없습니다. (컬럼명 또는 데이터 확인 필요)")

