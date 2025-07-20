import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import difflib
import time

# 구글 시트 연동 함수 (기존 코드와 동일)
@st.cache_resource(ttl=3600) # 1시간마다 새로고침
def get_worksheet():
    # Streamlit Secrets에서 서비스 계정 정보 로드
    creds_info = st.secrets["gcp_service_account"]
    
    # Credentials 객체 생성
    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    
    # gspread 클라이언트 인증
    gc = gspread.authorize(creds)
    
    # 스프레드시트 이름으로 열기
    spreadsheet_name = "질의응답시트"  # 스프레드시트 이름을 여기에 입력
    worksheet_name = "질의응답시트"     # 워크시트 이름을 여기에 입력
    
    sh = gc.open(spreadsheet_name)
    worksheet = sh.worksheet(worksheet_name)
    return worksheet

# Q&A 데이터를 DataFrame으로 로드 (기존 코드와 동일)
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_data():
    worksheet = get_worksheet()
    data = worksheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0]) # 첫 행은 헤더로 사용
    
    # 'rowid' 컬럼 추가 (구글 시트의 실제 행 번호와 매핑)
    # 실제 데이터가 시작하는 행이 2행이므로 2부터 시작
    df["rowid"] = range(2, 2 + len(df)) 
    return df

# 유사 질문 체크 함수 (기존 코드와 동일)
def is_duplicate_question(new_question, existing_questions, threshold=0.85):
    for eq in existing_questions:
        if difflib.SequenceMatcher(None, new_question, eq).ratio() >= threshold:
            return True
    return False

# CSS (기존 코드와 동일)
st.markdown("""
<style>
    .stApp {
        background-color: #f0f2f6; /* Light mode background */
        color: #333;
    }
    .dark-mode .stApp {
        background-color: #1a1a1a; /* Dark mode background */
        color: #eee;
    }
    .stButton>button {
        background-color: #4CAF50; /* Green */
        color: white;
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stTextInput>div>div>input {
        border-radius: 5px;
        border: 1px solid #ccc;
        padding: 8px;
    }
    .stTextArea>div>div>textarea {
        border-radius: 5px;
        border: 1px solid #ccc;
        padding: 8px;
    }
    .stAlert {
        border-radius: 5px;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #004A99; /* KB손해보험 대표색상 */
    }
    .dark-mode h1, .dark-mode h2, .dark-mode h3, .dark-mode h4, .dark-mode h5, .dark-mode h6 {
        color: #007bff; /* Dark mode light blue */
    }
    .stExpander {
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .stExpander>div>div>p {
        font-weight: bold;
    }
    .column-header {
        font-weight: bold;
        background-color: #e6e6e6;
        padding: 5px;
        border-bottom: 1px solid #ccc;
    }
    .dark-mode .column-header {
        background-color: #333;
    }
</style>
""", unsafe_allow_html=True)

# 초기 세션 상태 설정 (수정 모드 관리)
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False
if 'edit_row_data' not in st.session_state:
    st.session_state.edit_row_data = None

# 메인 앱 로직 시작
st.title("🌟 KB손해보험 충청호남본부 Q&A 센터 🌟")

# 상단 이미지 및 인사말 (기존 코드와 동일)
col1, col2 = st.columns([1, 4])
with col1:
    st.image("https://github.com/streamlit/docs/blob/main/docs/images/streamlit-logo-secondary-light.png?raw=true", width=100) # 여기에 충청호남본부 관련 이미지 URL 삽입
with col2:
    st.write("### 진상수 본부장입니다! 매니저 여러분의 노고에 항상 감사드립니다.")
    st.write("궁금한 점은 언제든 질문하고, 함께 답변을 공유하며 성장해 나갑시다!")

st.markdown("---")

# 데이터 로드
try:
    df = load_data()
    existing_questions = df['질문'].tolist()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다. 구글 시트 연결을 확인해주세요: {e}")
    df = pd.DataFrame(columns=['작성자', '질문', '답변', '등록일', 'rowid'])
    existing_questions = []

# --- Q&A 등록 섹션 ---
st.header("💡 새로운 Q&A 등록")

with st.form("new_qa_form", clear_on_submit=True):
    manager_name = st.text_input("🙋‍♀️ 매니저 이름", placeholder="본인 이름을 입력해주세요")
    new_question = st.text_area("❓ 질문 내용", placeholder="궁금한 내용을 입력해주세요")
    new_answer = st.text_area("✅ 답변 내용 (나중에 추가 가능)", placeholder="답변을 입력해주세요 (선택 사항)")
    
    submitted = st.form_submit_button("등록하기")
    if submitted:
        if not manager_name or not new_question:
            st.warning("매니저 이름과 질문 내용은 필수 입력 사항입니다.")
        elif is_duplicate_question(new_question, existing_questions):
            st.warning("유사한 질문이 이미 존재합니다. 기존 질문을 확인해주세요.")
        else:
            try:
                worksheet = get_worksheet()
                current_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                new_row = [manager_name, new_question, new_answer, current_time]
                worksheet.append_row(new_row)
                st.success("새로운 Q&A가 성공적으로 등록되었습니다!")
                st.cache_data.clear() # 캐시 데이터 새로고침
                st.experimental_rerun() # 앱 새로고침
            except Exception as e:
                st.error(f"Q&A 등록 중 오류가 발생했습니다: {e}")

st.markdown("---")

# --- Q&A 검색 및 관리 섹션 ---
st.header("🔍 Q&A 검색 및 관리")

search_col1, search_col2 = st.columns(2)
with search_col1:
    search_keyword = st.text_input("키워드 검색 (질문/답변)", placeholder="예: 보험료, 가입, 특약")
with search_col2:
    search_author = st.text_input("작성자 검색", placeholder="예: 홍길동")

filtered_df = df.copy()

# 검색 필터링
if search_keyword:
    filtered_df = filtered_df[
        filtered_df['질문'].str.contains(search_keyword, case=False, na=False) |
        filtered_df['답변'].str.contains(search_keyword, case=False, na=False)
    ]
if search_author:
    filtered_df = filtered_df[
        filtered_df['작성자'].str.contains(search_author, case=False, na=False)
    ]

# 검색 결과 표시
if not filtered_df.empty:
    st.subheader(f"총 {len(filtered_df)}개의 Q&A가 검색되었습니다.")
    
    # 컬럼 헤더 표시
    st.markdown(
        f"""
        <div style="display: flex; background-color: #e6e6e6; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-weight: bold;">
            <div style="flex: 0.5;">ID</div>
            <div style="flex: 2;">작성자</div>
            <div style="flex: 5;">질문 내용</div>
            <div style="flex: 1.5;">등록일</div>
            <div style="flex: 2;">관리</div>
        </div>
        """, unsafe_allow_html=True
    )

    for index, row in filtered_df.iterrows():
        # 각 행을 expander로 표시
        with st.expander(f"**Q. {row['질문']}** (작성자: {row['작성자']}, 등록일: {row['등록일']})"):
            st.markdown(f"**질문:** {row['질문']}")
            st.markdown(f"**답변:** {row['답변']}")
            st.write(f"**작성자:** {row['작성자']}")
            st.write(f"**등록일:** {row['등록일']}")

            edit_col, delete_col = st.columns([1, 1])
            with edit_col:
                if st.button(f"✏️ 수정", key=f"edit_{row['rowid']}"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_row_data = row.to_dict() # 딕셔너리로 저장
                    st.experimental_rerun() # 수정 폼을 보여주기 위해 새로고침
            with delete_col:
                if st.button(f"🗑️ 삭제", key=f"delete_{row['rowid']}"):
                    try:
                        worksheet = get_worksheet()
                        # 구글 시트의 실제 행 번호로 삭제 (rowid는 1부터 시작하는 구글 시트 행 번호)
                        worksheet.delete_rows(row["rowid"]) 
                        st.success(f"Q&A (ID: {row['rowid']})가 성공적으로 삭제되었습니다.")
                        st.cache_data.clear() # 캐시 데이터 새로고침
                        st.experimental_rerun() # 앱 새로고침
                    except Exception as e:
                        st.error(f"Q&A 삭제 중 오류가 발생했습니다: {e}")
                        
else:
    st.info("검색 결과가 없습니다.")

st.markdown("---")

# --- Q&A 수정 폼 ---
if st.session_state.edit_mode and st.session_state.edit_row_data:
    st.header("📝 Q&A 수정")
    row_to_edit = st.session_state.edit_row_data
    original_row_id = row_to_edit['rowid'] # 수정할 원본 rowid (구글 시트의 실제 행 번호)

    st.subheader(f"Q&A (ID: {original_row_id}) 수정")
    
    with st.form(key=f"edit_qa_form_{original_row_id}"):
        edited_manager = st.text_input("매니저 이름", value=row_to_edit['작성자'])
        edited_question = st.text_area("질문 내용", value=row_to_edit['질문'])
        edited_answer = st.text_area("답변 내용", value=row_to_edit['답변'])

        col_save, col_cancel = st.columns(2)
        with col_save:
            save_button = st.form_submit_button("저장")
        with col_cancel:
            cancel_button = st.form_submit_button("취소")

        if save_button:
            if not edited_manager or not edited_question:
                st.warning("매니저 이름과 질문 내용은 필수 입력 사항입니다.")
            else:
                try:
                    worksheet = get_worksheet()
                    # 구글 시트의 실제 행 번호와 컬럼 인덱스 매핑 (헤더는 1행, 데이터는 2행부터 시작)
                    # '작성자', '질문', '답변', '등록일' 순서 (인덱스 1, 2, 3, 4)
                    
                    # 각 셀을 개별적으로 업데이트 (가장 안전한 방법)
                    worksheet.update_cell(original_row_id, 1, edited_manager) # 작성자
                    worksheet.update_cell(original_row_id, 2, edited_question) # 질문
                    worksheet.update_cell(original_row_id, 3, edited_answer) # 답변
                    # 등록일은 수정 시 변경하지 않는 것이 일반적. 필요하다면 현재 시간으로 업데이트
                    # worksheet.update_cell(original_row_id, 4, pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")) 

                    st.success(f"Q&A (ID: {original_row_id})가 성공적으로 수정되었습니다.")
                    st.session_state.edit_mode = False # 수정 모드 해제
                    st.session_state.edit_row_data = None # 저장된 데이터 초기화
                    st.cache_data.clear() # 캐시 데이터 새로고침
                    st.experimental_rerun() # 앱 새로고침
                except Exception as e:
                    st.error(f"Q&A 수정 중 오류가 발생했습니다: {e}")
        
        if cancel_button:
            st.session_state.edit_mode = False # 수정 모드 해제
            st.session_state.edit_row_data = None # 저장된 데이터 초기화
            st.experimental_rerun() # 앱 새로고침


st.markdown("---")

# --- 최근 5개 질문 미리보기 섹션 (기존 코드와 동일) ---
st.header("📚 최근 5개 Q&A 미리보기")
if not df.empty:
    recent_qa = df.sort_values(by='등록일', ascending=False).head(5)
    for index, row in recent_qa.iterrows():
        st.subheader(f"Q. {row['질문']}")
        st.write(f"A. {row['답변']}")
        st.caption(f"작성자: {row['작성자']} | 등록일: {row['등록일']}")
        st.markdown("---")
else:
    st.info("아직 등록된 Q&A가 없습니다. 새로운 질문을 등록해주세요!")