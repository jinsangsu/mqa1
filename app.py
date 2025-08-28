import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import difflib
import datetime
import os
import base64
import io, json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


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

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]

def _get_drive_creds():
    info = st.secrets["gcp_service_account"]
    if isinstance(info, str):
        info = json.loads(info)
    return Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)

@st.cache_resource(show_spinner=False)
def get_drive_client():
    return build("drive", "v3", credentials=_get_drive_creds())

DRIVE_UPLOAD_FOLDER_ID = (
    st.secrets.get("drive_upload_folder_id")
    or (st.secrets.get("google", {}) or {}).get("uploads_folder_id", "")
)
DRIVE_LINK_SHARING = st.secrets.get("drive_link_sharing", "anyone")  # "anyone" | "domain"
ORG_DOMAIN_FOR_DRIVE = "chunghobb.com"  # 사내용 공유("domain")을 쓰는 경우 실제 조직 도메인으로 맞추기


def _image_embed_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=view&id={file_id}"

def _pdf_preview_url(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/preview"

def resolve_upload_folder_id(drive):
    """secrets의 폴더 ID를 그대로 신뢰해서 사용 (화면에 로그 출력 안 함)."""
    folder_id = DRIVE_UPLOAD_FOLDER_ID or (st.secrets.get("google", {}) or {}).get("uploads_folder_id", "")
    if not folder_id:
        # 화면에 불필요한 info/warning을 남기지 않기 위해 error만 사용
        st.error("업로드용 폴더 ID가 비어 있습니다. secrets.toml의 drive_upload_folder_id 또는 [google].uploads_folder_id를 확인해 주세요.")
        raise RuntimeError("Missing DRIVE_UPLOAD_FOLDER_ID")
    return folder_id

def upload_to_drive(uploaded_file) -> dict:
    """Streamlit UploadedFile → Drive 업로드 + (가능하면) 링크공개. 진단/예외 처리 강화."""
    drive = get_drive_client()

    # 0) 업로드 폴더 ID 검증 (빈 값/권한 오류를 업로드 전에 잡음)
    if not DRIVE_UPLOAD_FOLDER_ID:
        st.error("업로드용 폴더 ID가 비어 있습니다. secrets.toml의 drive_upload_folder_id 또는 [google].uploads_folder_id를 확인해 주세요.")
        raise RuntimeError("Missing DRIVE_UPLOAD_FOLDER_ID")

    try:
        target_folder_id = resolve_upload_folder_id(drive)
    except Exception as e:
        st.error("업로드 폴더를 확정하지 못해 중단합니다.")
        raise

# (이 아래부터는 target_folder_id 사용)
    meta = {
        "name": uploaded_file.name,
        "parents": [target_folder_id],
        # "mimeType": mime,  ← 필요시 주석 해제
    }
    # 1) 파일 생성
    file_bytes = uploaded_file.getvalue()
    mime = getattr(uploaded_file, "type", None) or "application/octet-stream"
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime, resumable=True)

    meta = {
        "name": uploaded_file.name,
        "parents": [target_folder_id],
        # "mimeType": mime,  # 굳이 지정 안 해도 무방 (문제시 주석 해제)
    }

    f = drive.files().create(
        body=meta,
        media_body=media,
        fields="id,name,mimeType,webViewLink,iconLink",
        supportsAllDrives=True,
    ).execute()

    # 생성 결과 점검 (문제 없으면 주석 처리 가능)
    # st.write({"created_file": f})

    file_id = f.get("id")
    if not file_id:
        st.error("Drive 파일 생성에 실패했습니다. 응답에 id가 없습니다.")
        raise RuntimeError(f"Drive create() response: {f}")

    # 2) 권한 부여(조직 정책에 따라 실패할 수 있으므로 예외 허용)
    try:
        if DRIVE_LINK_SHARING == "anyone":
            perm_body = {"role": "reader", "type": "anyone"}
        else:  # "domain"
            perm_body = {"role": "reader", "type": "domain", "domain": ORG_DOMAIN_FOR_DRIVE, "allowFileDiscovery": False}

        drive.permissions().create(
            fileId=file_id,
            body=perm_body,
            supportsAllDrives=True
        ).execute()
    except Exception as e:
        # 공개 정책/조직 정책으로 실패해도 업로드는 성공이므로 경고만 띄우고 계속
        st.warning(f"권한 부여 실패(조직 정책 가능성): {e}\n파일은 생성되었습니다. 기본 링크로 계속 진행합니다.")
        st.exception(e)

    # 3) 반환 메타 구성
    is_image = (f.get("mimeType", "").startswith("image/"))
    return {
        "id": file_id,
        "name": f.get("name"),
        "mime": f.get("mimeType"),
        "view_url": f.get("webViewLink"),  # 새탭 열람
        "embed_url": _image_embed_url(file_id) if is_image
                     else (_pdf_preview_url(file_id) if f.get("mimeType") == "application/pdf" else f.get("webViewLink")),
        "is_image": is_image,
        "icon": f.get("iconLink"),
    }

def get_worksheet():
    sheet_key = (st.secrets.get("google", {}) or {}).get("qa_sheet_key")
    if not sheet_key:
        st.error("secrets에 [google].qa_sheet_key가 없습니다.")
        st.stop()

    spreadsheet = gc.open_by_key(sheet_key)
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
    <strong>현장에서 항상 최선을 다해주셔서 감사드립니다. 꾸벅~</strong>
    <br><strong>이번에 영업가족 질문에 답변하는 Q&A 시스템을 준비했습니다.</strong></br>
    <strong>
      (<a href="http://chung2.streamlit.app" target="_blank" style="color: red; text-decoration: none;">
        앱주소 : http://chung2.streamlit.app
      </a>)
    </strong>
    <br><strong>자주하는 질문과 답변을 등록해주시면</strong></br>
    <strong>업무에 많은 도움이 될것입니다.</strong>
    <strong>잘 부탁드립니다!</strong>
  </div>
</div>
"""

st.markdown(intro_html, unsafe_allow_html=True)# ====== 데이터 불러오기 ======
worksheet = get_worksheet()
data = worksheet.get_all_values()
df = pd.DataFrame(data[1:], columns=data[0])
# '첨부_JSON' 헤더 자동 보정
if "첨부_JSON" not in df.columns:
    try:
        worksheet.update_cell(1, len(df.columns)+1, "첨부_JSON")
        data = worksheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])  # 헤더 갱신
    except Exception as e:
        st.error(f"'첨부_JSON' 헤더 추가 중 오류: {e}")

if "번호" in df.columns:
    df["번호"] = df["번호"].astype(int)
else:
    st.error("시트에 '번호' 컬럼이 없습니다. 시트 구조를 확인하세요.")

# ========== Q&A 등록 폼 ==========
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
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
uploaded_files = st.file_uploader(
    "📎 이미지/파일 첨부 (이미지, PDF, Office 문서)",
    accept_multiple_files=True,
    type=["png","jpg","jpeg","webp","pdf","ppt","pptx","xls","xlsx","doc","docx"],
    help="이미지·PDF는 설계사 화면에서 미리보기가 가능합니다.",
)

if st.button("✅ 시트에 등록하기"):
    # 1. 질문/답변 필수값 체크 먼저!
    if not question.strip() or not answer.strip():
        st.error("⚠ 질문과 답변은 필수 입력입니다. 반드시 내용을 입력해 주세요.")
    else:
        existing_questions = [q.strip() for q in df["질문"].tolist()]

        is_near_duplicate = any(
        difflib.SequenceMatcher(None, question.strip(), q).ratio() >= 0.9
        for q in existing_questions
        )

        if question.strip() and is_near_duplicate:
            st.warning("⚠ 매니저님 감사합니다. 그런데 이미 유사한 질문이 등록되어 있네요.")

            similar_list = sorted(
                (
                    (q, difflib.SequenceMatcher(None, question.strip(), q).ratio())
                    for q in existing_questions
                ),
                key=lambda x: x[1],
                reverse=True
            )[:3]

            for q, r in similar_list:
                st.info(f"• 유사도 {r:.0%} → {q}")
        else:
            if len(df) == 0:
                new_no = 1
            else:
                new_no = df["번호"].max() + 1
            today = datetime.date.today().strftime("%Y-%m-%d")

            try:
                # ✅ 파일 업로드는 try문 안, 버튼 클릭 내부에서 실행되어야 합니다.
                attachments = []
                if uploaded_files:
                    for uf in uploaded_files:
                        try:
                            attachments.append(upload_to_drive(uf))
                        except Exception as e:
                            st.error(f"첨부 업로드 실패: {uf.name} — {e}")
                            st.exception(e)

                attachments_json = json.dumps(attachments, ensure_ascii=False)

                worksheet.append_row([
                    str(new_no),
                    str(question),
                    str(answer),
                    str(manager_name),
                    str(today),
                    attachments_json,   # ← 6번째 컬럼: 첨부_JSON
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
