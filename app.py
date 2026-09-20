"""악보 가사 수정기 — 스캔 악보 PDF/이미지의 한글 가사를 클릭해서 고친다 (Streamlit).
빨간 박스 클릭 → 수정/삭제 → 규칙란 자동 기입 → ✔ 수정완료(미리보기) → PDF."""
import hashlib, os, re as _re
import streamlit as st
import engine

APP_VERSION = "2.3.0"

st.set_page_config(page_title="악보 가사 수정기", page_icon="🎼", layout="wide",
                   initial_sidebar_state="collapsed")
# 디자인 시스템: 아이스블루 그라데이션 · 알약 버튼 · 소프트 섀도 카드 (참조: voice-AI coach UI)
st.markdown("""
<style>
  :root{
    --blue:#4A7DFF; --blue-soft:#A7C4FF; --ink:#171B26; --ink-2:#5A6475;
    --card:#FFFFFF; --shadow:0 10px 30px rgba(74,125,255,.10), 0 2px 8px rgba(23,27,38,.06);
  }
  .stApp{
    background:
      radial-gradient(1200px 500px at 15% -5%, rgba(167,196,255,.45), transparent 60%),
      radial-gradient(1000px 600px at 105% 10%, rgba(202,222,255,.5), transparent 55%),
      linear-gradient(180deg,#F6F9FF 0%,#EFF4FE 100%);
  }
  .block-container{ padding-top:1.1rem; padding-bottom:3rem; max-width:1150px; }
  [data-testid="stToolbar"], #MainMenu, footer{ visibility:hidden; height:0; }

  /* ── 히어로 ── */
  .hero{ display:flex; align-items:center; gap:20px; padding:26px 30px; margin-bottom:6px;
         background:rgba(255,255,255,.65); backdrop-filter:blur(8px);
         border:1px solid rgba(255,255,255,.9); border-radius:28px; box-shadow:var(--shadow); }
  .orb{ position:relative; flex:0 0 74px; width:74px; height:74px; border-radius:50%;
        background:radial-gradient(circle at 32% 26%, #CFE0FF 0%, #7AA3FF 45%, #4A7DFF 78%, #3B67E8 100%);
        box-shadow:0 16px 34px rgba(74,125,255,.45), inset 0 -8px 18px rgba(30,60,160,.25); }
  .orb::before,.orb::after{ content:""; position:absolute; top:30px; width:16px; height:13px;
        background:#fff; border-radius:52% 48% 60% 40%; opacity:.95; }
  .orb::before{ left:16px; transform:rotate(-14deg); }
  .orb::after{ right:16px; transform:rotate(14deg); }
  .hero h1{ font-size:1.75rem; font-weight:800; letter-spacing:-.02em; color:var(--ink); margin:0 0 4px; }
  .hero p{ margin:0; color:var(--ink-2); font-size:.98rem; }

  /* ── 탭: 알약 세그먼트 ── */
  [data-testid="stTabs"] [role="tablist"]{ gap:8px; border-bottom:none; background:rgba(255,255,255,.6);
        padding:6px; border-radius:999px; width:fit-content; box-shadow:var(--shadow); }
  [data-testid="stTabs"] [data-testid="stTab"]{ border-radius:999px !important; padding:7px 18px;
        color:var(--ink-2); font-weight:600; }
  [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"]{ background:var(--ink) !important; }
  [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p{ color:#fff !important; }
  .react-aria-SelectionIndicator, div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"]{ display:none !important; }

  /* ── 카드류 ── */
  [data-testid="stFileUploaderDropzone"]{ background:var(--card); border:1.5px dashed var(--blue-soft);
        border-radius:22px; box-shadow:var(--shadow); }
  [data-testid="stExpander"] details{ background:var(--card); border:1px solid #E8EEFB;
        border-radius:20px; box-shadow:var(--shadow); overflow:hidden; }
  [data-testid="stAlert"]{ border-radius:18px; border:none; box-shadow:var(--shadow); }
  div[data-testid="stDialog"] > div:first-child{ border-radius:24px;
        max-width:min(540px, 92vw) !important; max-height:70vh; overflow-y:auto; }
  @media (max-width:640px){
    div[data-testid="stDialog"] > div:first-child{ max-height:78vh; }
  }

  /* ── 버튼: 알약 ── */
  .stButton>button, .stDownloadButton>button, [data-testid="stCameraInput"] button{
        border-radius:999px !important; min-height:3rem; font-size:1.02rem; font-weight:700;
        border:1px solid #E4EAF7; background:var(--card); color:var(--ink); box-shadow:var(--shadow);
        transition:transform .08s ease; }
  .stButton>button:hover, .stDownloadButton>button:hover{ transform:translateY(-1px); border-color:var(--blue-soft); color:var(--ink); }
  .stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"],
  [data-testid="stBaseButton-primary"]{
        background:var(--ink) !important; color:#fff !important; border:none !important; }
  .stButton>button[kind="primary"]:hover{ background:#232838 !important; color:#fff !important; }

  /* ── 입력 ── */
  .stTextInput input{ border-radius:14px; font-size:1.03rem; background:var(--card); border:1px solid #E4EAF7; }
  .stTextInput input:focus{ border-color:var(--blue); box-shadow:0 0 0 3px rgba(74,125,255,.18); }
  .stTextArea textarea{ border-radius:16px; font-size:1.0rem; background:var(--card); border:1px solid #E4EAF7; }
  h3{ letter-spacing:-.01em; }

  [data-testid="stSidebar"]{ background:rgba(255,255,255,.85); backdrop-filter:blur(10px); }

  @media (max-width:640px){
    .hero{ padding:18px 18px; gap:14px; border-radius:22px; }
    .hero h1{ font-size:1.28rem; } .hero p{ font-size:.88rem; }
    .orb{ flex-basis:56px; width:56px; height:56px; }
    .orb::before,.orb::after{ top:22px; width:12px; height:10px; }
    .orb::before{ left:12px; } .orb::after{ right:12px; }
    .block-container{ padding-left:.8rem; padding-right:.8rem; }
  }
</style>
""", unsafe_allow_html=True)

# ---------- 사이드바 ----------
with st.sidebar:
    st.markdown("## 🎼 악보 가사 수정기")
    st.caption(f"You쌤융합교육원 by YouDefine · v{APP_VERSION}")
    st.markdown(
        "**3단계**\n"
        "1. 악보 PDF/이미지 업로드\n"
        "2. **빨간 박스를 클릭**해 수정·삭제\n"
        "3. ✔ 수정완료(미리보기) → PDF 다운로드\n\n"
        "자세한 방법은 위쪽 **❓ 도움말** 탭에 있어요."
    )
    problems = engine.check_env()
    if problems:
        st.error("환경 점검 실패:\n\n" + "\n".join(f"- {p}" for p in problems))
    with st.expander("고급"):
        dpi = st.select_slider("해상도(dpi)", options=[200, 300, 400], value=300,
                               help="인식이 안 되는 행이 있으면 400으로")

RULES_HEADER = (
    "# 빨간 박스를 클릭하면 여기에 규칙이 자동으로 쌓여요.\n"
    "# 형식: 원본=수정  /  원본=삭제   (# 뒤는 주석 — 적용 안 됨)\n"
)
EXAMPLE_RULES = (
    "# 예시: 마산가고파 로타리\n"
    "마상가고바로탈이=마산가고파로타리\n"
    "탈이=타리\n"
    "바로=파로\n"
    "조아=초아\n"
    "# 단어를 지우려면: 우리들의=삭제"
)


def render_help():
    st.markdown("""
### 이 앱이 하는 일
스캔한 악보(PDF·이미지)에서 **한글 가사의 틀린 글자를 클릭해서** 같은 자리에 다시 씁니다.
음표·코드·기호·타브는 픽셀 그대로 두고, 바뀌는 음절의 잉크만 지우고 새로 그려요.
글자를 **삭제해도 나머지 글자의 위치는 그대로** 유지돼요. AI 모델을 쓰지 않아 **사용료·토큰이 들지 않아요.**

### 사용 순서
| 단계 | 할 일 |
|---|---|
| ① 업로드 | PDF / PNG / JPG를 올리면 가사·문구를 자동으로 찾아요 (페이지당 10~20초) |
| ② 클릭 편집 | 악보 위 **🟥 빨간 박스를 클릭** → 팝업에서 **✏️ 수정** 또는 **🗑 삭제** 선택 → 규칙란에 자동 기입 |
| ③ 수정완료 | **✔ 수정완료 (미리보기)** 를 누르면 규칙이 한꺼번에 반영된 결과를 보여줘요 → **⬇ PDF 다운로드** |

### ② 클릭 편집 — 화면 읽는 법
- **🟥 빨간 박스** = 클릭해서 고칠 수 있는 단어·영문·코드예요.
- **🟩 초록 박스** = 이미 규칙이 걸려 있어 ③에서 바뀔 단어예요. 박스 위에 바뀔 글자가 초록색으로 보여요.
- 팝업에서 **✏️ 수정**: 새 글자를 입력하면 규칙란에 `원본=수정`이 적혀요. **글자 수가 달라도 돼요.**
- 팝업에서 **🗑 삭제**: 규칙란에 `원본=삭제`가 적히고, 반영 시 그 단어만 지워져요. **나머지 글자 위치는 그대로예요.**
- 같은 문구가 여러 곳에 있으면 규칙 하나로 **모두 함께** 바뀌어요 (팝업에 몇 곳인지 표시).

### 규칙란 (📋 일괄 규칙 팝업)
- 클릭으로 쌓인 규칙을 직접 고치거나, `원본=수정`을 손으로 추가할 수 있어요. 한 줄에 하나씩.
- `원본=삭제`라고 쓰면 그 단어를 지워요. `#` 뒤는 주석이라 무시돼요.
- 업로드 직후, 사전에 없는 어절은 `# 확인:` 제안 주석으로 미리 채워드려요. `#`을 지우고 `=` 뒤를 채우면 그대로 적용돼요.
- ⚠️ 한 글자 규칙(`상=산`)은 다른 단어(세상→세산)까지 바꿔요. 앞뒤 글자를 붙여 `마상가고=마산가고`처럼 쓰세요.
- 긴 규칙을 먼저 쓰세요. 위에서부터 차례로 적용돼요.

### ⌨️ 행 전체 편집 팝업
- 행 단위로 통째로 고치고 싶을 때 사용해요. 인식된 행 옆 칸에 새 내용을 쓰고 **✔ 완료**를 누르면 규칙란에 행 규칙이 추가돼요.
- 칸을 비우면 그 행 전체가 삭제 규칙이 돼요 (위치는 유지).

### ③ 결과 확인
- **🔍 바뀔 위치 확인**: 빨간 박스 = 지워질 음절, 그 아래 빨간 글자 = 새 글자. 위치만 확인하면 돼요.
- **✔ 수정완료 (미리보기)**: 규칙을 모두 반영한 수정본을 화면에 보여주고, 바로 **⬇ PDF 다운로드**가 가능해요.
- 결과 파일명은 `원본이름_수정.pdf` — 저장 칸에서 바꿀 수 있어요.

### 📱 폰에서 쓰기
- **홈 화면에 추가**하면 앱처럼 아이콘으로 열려요.
  iPhone: Safari 하단 **공유(□↑) → 홈 화면에 추가** · Android: Chrome **⋮ → 홈 화면에 추가**
- 업로드 칸에서 **사진 촬영 / 앨범 / 파일**을 고를 수 있고, 「📷 카메라로 찍기」로 바로 찍어도 돼요.
- **촬영 팁**: 정면에서, 페이지 전체가 들어오게, 그림자 없이. 그늘·누런 종이·약간의 기울기는 자동 보정돼요.

### 자주 묻는 질문
- **인식이 왜 오래 걸리나요?** 300dpi 이미지를 글자 단위로 읽어요. 파일당 한 번만 걸리고, 이후 클릭·미리보기는 바로 돼요.
- **글자 수가 달라져도 되나요?** 네. 삭제·삽입되는 부분만 바뀌고 나머지 글자는 원본 픽셀·위치 그대로예요.
- **영문 제목이나 코드도 고칠 수 있나요?** 네, 영문·숫자 문구도 빨간 박스로 잡혀요. 글자 수 제한이 없어요.
- **새 글자의 폰트가 조금 달라 보여요.** 원본 글자 높이에 맞춰 Noto Sans(본고딕)로 그려요. 특수 폰트는 살짝 다를 수 있어요.
- **여러 페이지도 되나요?** 네. 페이지별 캔버스가 나오고, 결과는 한 PDF로 합쳐져요.

### 문제가 생기면
| 증상 | 해결 |
|---|---|
| 가사 행이 하나도 안 잡혀요 | 더 선명한 스캔(300dpi 이상)이나 정면 촬영으로 다시 올려보세요 |
| 회색 박스라 클릭이 안 돼요 | OCR이 음절 수를 잘못 센 행이에요. 사이드바 「고급」→ dpi 400으로 재시도 |
| 규칙을 넣어도 안 바뀌어요 | 규칙의 '원본'이 **인식된 글자와 똑같아야** 해요 (띄어쓰기 없이). 박스를 클릭해 만들면 정확해요 |
| 미리보기 박스가 엉뚱한 글자에 있어요 | 그 규칙만 지우고 다시 시도하거나 문의해 주세요 |

문의: yousam4u@gmail.com · You쌤융합교육원 by YouDefine
""")


def render_editor():
    # ---------- ① 업로드 & 인식 ----------
    up = st.file_uploader("악보 파일 (PDF · PNG · JPG) — 폰에서는 여기서 바로 '사진 촬영'도 골라져요",
                          type=["pdf", "png", "jpg", "jpeg"])
    shot = None
    with st.expander("📷 카메라로 찍기 (폰)", expanded=False):
        st.caption("악보를 정면에서 평평하게, 페이지 전체가 들어오게 찍으세요. 그늘·기울기는 자동 보정돼요.")
        shot = st.camera_input("촬영", label_visibility="collapsed")
    src = up or shot
    if not src:
        st.info("악보 파일을 올리거나 사진을 찍으면, 악보 위에서 글자를 클릭해 바로 고칠 수 있어요.")
        return

    data = src.getvalue()
    src_name = getattr(src, "name", None) or "악보사진.jpg"
    fhash = hashlib.md5(data + str(dpi).encode()).hexdigest()[:10]

    if st.session_state.get("fhash") != fhash:
        try:
            with st.spinner("가사 행을 찾는 중… (페이지당 10~20초)"):
                images = engine.load_images(data, src_name, dpi)
                det = [engine.detect_page(im, dpi) for im in images]
        except Exception:
            st.error("파일을 여는 데 실패했어요. 손상되지 않은 PDF/이미지인지 확인하고 다시 올려주세요.")
            return
        # 표기 검사(베타): 사전에 없는 어절을 규칙란에 '# 확인:' 주석 제안으로 프리필
        sug_lines = []
        if engine.spell_available():
            try:
                for d in det:
                    for g in engine.suggest_page(d["rows"]):
                        for note in g["notes"]:
                            m = _re.match(r"'(.+?)' 확인 필요 · 비슷한 말: (.+)", note)
                            if m:
                                sug_lines.append(f"# 확인: {m.group(1)}=?   (비슷한 말: {m.group(2)})")
            except Exception:
                pass
        init_rules = RULES_HEADER
        if sug_lines:
            init_rules += "# ── 표기 검사 제안(참고용) — #을 지우고 = 뒤를 채우면 적용돼요\n" + "\n".join(dict.fromkeys(sug_lines)) + "\n"
        st.session_state.update({"fhash": fhash, "images": images, "det": det,
                                 "preview": None, "result": None, "sel_word": None, "open_dlg": None})
        st.session_state[f"{fhash}_rules"] = init_rules

    images, det = st.session_state["images"], st.session_state["det"]
    n_rows = sum(len(d["rows"]) for d in det)
    if n_rows == 0 and not any(d.get("latin") for d in det):
        st.warning("가사 행을 찾지 못했어요. 스캔이 흐리거나 크게 기울어진 경우예요 — "
                   "더 선명하게(300dpi 이상) 스캔하거나, 정면에서 다시 촬영해 주세요. "
                   "사이드바 「고급」에서 dpi 400으로 올려 재시도할 수도 있어요.")
        return
    st.success(f"{len(images)}페이지 · 가사 {n_rows}행 인식 — 🟥 빨간 박스를 클릭해 고쳐보세요")
    if not src_name.lower().endswith(".pdf"):
        st.caption("사진은 배경을 희게 펴고 기울기를 맞춘 보정본으로 작업해요. 결과 PDF도 보정본 기준이에요.")

    RK = f"{fhash}_rules"

    def parse_current_rules():
        try:
            return engine.parse_rules(st.session_state.get(RK, ""))
        except ValueError:
            return []

    def upsert_rule(a, b):
        """규칙란에 a=b를 추가. 같은 원본의 규칙이 이미 있으면 그 줄을 교체."""
        a = "".join(a.split())
        b = "".join(b.split()) or "삭제"
        lines = st.session_state.get(RK, "").splitlines()
        out, done = [], False
        for ln in lines:
            body = ln.split("#")[0].strip()
            if "=" in body and body.split("=", 1)[0].strip() == a:
                if not done:
                    out.append(f"{a}={b}"); done = True
                continue
            out.append(ln)
        if not done:
            out.append(f"{a}={b}")
        st.session_state[RK] = "\n".join(out).rstrip() + "\n"

    rules_now = parse_current_rules()
    n_rules = len(rules_now)

    # ---------- ② 클릭 편집 ----------
    st.subheader("② 클릭 편집")
    st.caption("🟥 빨간 박스 = 클릭해서 수정·삭제 · 🟩 초록 = 규칙이 걸려 ③에서 바뀔 단어 (위에 새 글자 표시) · "
               "회색 = 인식 불완전(클릭 불가)")

    # 팝업(다이얼로그) 정의 ------------------------------------------------
    @st.dialog("📋 일괄 규칙")
    def rules_dialog():
        st.caption("클릭으로 쌓인 규칙을 직접 다듬거나, `원본=수정`·`원본=삭제`를 손으로 추가하세요. 한 줄에 하나, `#` 뒤는 주석.")
        ta_key = RK + "_ta"
        with st.expander("예시 규칙 보기 · 그대로 넣기", expanded=False):
            st.code(EXAMPLE_RULES, language=None)
            if st.button("예시를 규칙 칸 끝에 추가", key="rules_ex"):
                nv = st.session_state.get(RK, "").rstrip() + "\n" + EXAMPLE_RULES + "\n"
                st.session_state[RK] = nv
                st.session_state[ta_key] = nv

        def _sync_rules():
            st.session_state[RK] = st.session_state[ta_key]
        st.text_area("규칙", value=st.session_state.get(RK, ""), height=160, key=ta_key,
                     on_change=_sync_rules, label_visibility="collapsed")
        st.caption("⚠️ 한 글자 규칙(`상=산`)은 다른 단어(세상→세산)까지 바꿔요. 반영은 아래 「✔ 수정완료 (미리보기)」에서 한꺼번에 돼요.")
        if st.button("닫기", use_container_width=True, key="rules_close"):
            st.session_state["open_dlg"] = None; st.rerun()

    @st.dialog("⌨️ 행 전체 편집")
    def rows_dialog():
        st.caption("행을 통째로 고칠 때 사용하세요. 새 내용을 쓰고 ✔ 완료를 누르면 행 규칙이 규칙란에 추가돼요. 칸을 비우면 행 전체 삭제(위치 유지).")
        rl = parse_current_rules()
        for p, d in enumerate(det):
            if len(det) > 1:
                st.markdown(f"**{p + 1}페이지**")
            for r, row in enumerate(d["rows"]):
                key = f"rowedit_{fhash}_{p}_{r}"
                if not row["ok"]:
                    st.text_input(f"행 {r + 1} (인식 불완전 — 편집 불가)", value=row["text"],
                                  key=key + "_ro", disabled=True)
                    continue
                applied = engine.apply_rules(row["text"], rl)
                st.text_input(f"행 {r + 1} — 인식: `{row['text']}`", value=applied, key=key)
        if st.button("✔ 완료 (규칙란에 반영)", type="primary", use_container_width=True, key="rows_done"):
            rl2 = parse_current_rules()
            n_add = 0
            for p, d in enumerate(det):
                for r, row in enumerate(d["rows"]):
                    if not row["ok"]:
                        continue
                    key = f"rowedit_{fhash}_{p}_{r}"
                    val = "".join(st.session_state.get(key, "").split())
                    if val != engine.apply_rules(row["text"], rl2):
                        upsert_rule(row["text"], val or "삭제"); n_add += 1
            st.session_state["open_dlg"] = None
            if n_add:
                st.toast(f"행 규칙 {n_add}개를 규칙란에 추가했어요")
            st.rerun()
        if st.button("닫기", use_container_width=True, key="rows_close"):
            st.session_state["open_dlg"] = None; st.rerun()

    @st.dialog("✏️ 단어 수정 · 삭제")
    def word_dialog():
        sel = st.session_state.get("sel_word")
        if not sel:
            st.write("선택된 단어가 없어요."); return
        w = sel["w"]
        same_n = sum(1 for wm in word_map if wm["w"] == w and wm["cur"] is not None)
        cur_rule = next((b for a, b in parse_current_rules() if a == w), None)
        st.markdown(f"**인식된 텍스트:** `{w}`"
                    + (f" — 현재 규칙: `{w}={cur_rule or '삭제'}`" if cur_rule is not None else ""))
        if same_n > 1:
            st.caption(f"같은 문구가 {same_n}곳에 있어요 — 규칙 하나로 모두 함께 바뀌어요.")
        raw = st.text_input("수정할 텍스트 (글자 수가 달라도 돼요)",
                            value=cur_rule if cur_rule else w,
                            key=f"we_{fhash}_{sel['p']}_{sel['r']}_{sel['i0']}")
        nv = raw.strip() if sel.get("tok") else "".join(raw.split())
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✔ 수정 규칙 추가", type="primary", use_container_width=True, key="wd_fix"):
                if nv == w:
                    st.toast("바뀐 내용이 없어요 — 새 글자를 입력해 주세요")
                else:
                    upsert_rule(w, nv or "삭제")
                    st.session_state["sel_word"] = None
                    st.toast(f"규칙 추가: {w}={nv or '삭제'}"); st.rerun()
        with c2:
            if st.button("🗑 삭제 규칙 추가", use_container_width=True, key="wd_del"):
                upsert_rule(w, "삭제")
                st.session_state["sel_word"] = None
                st.toast(f"규칙 추가: {w}=삭제"); st.rerun()
        if st.button("닫기 (반영 안 함)", use_container_width=True, key="wd_close"):
            st.session_state["sel_word"] = None; st.rerun()

    # 툴바 ------------------------------------------------------------------
    tb1, tb2, tb3 = st.columns([1.2, 1.2, 1])
    with tb1:
        if st.button(f"📋 일괄 규칙 ({n_rules}개)", use_container_width=True):
            st.session_state["open_dlg"] = "rules"; st.session_state["sel_word"] = None
    with tb2:
        if st.button("⌨️ 행 전체 편집", use_container_width=True):
            st.session_state["open_dlg"] = "rows"; st.session_state["sel_word"] = None
    with tb3:
        if st.button("↺ 규칙 비우기", use_container_width=True):
            st.session_state[RK] = RULES_HEADER
            for k in list(st.session_state):
                if k.startswith(f"rowedit_{fhash}_") or k.startswith(f"we_{fhash}_"):
                    del st.session_state[k]
            st.session_state.update({"preview": None, "result": None, "sel_word": None, "open_dlg": None})
            st.rerun()

    # 단어 지도 + 캔버스 ------------------------------------------------------
    from streamlit_image_coordinates import streamlit_image_coordinates
    from PIL import ImageDraw as _ImageDraw, ImageFont as _IF

    word_map = []
    for p_, d_ in enumerate(det):
        for r_, row_ in enumerate(d_["rows"]):
            for wb in engine.word_boxes(row_):
                word_map.append({"p": p_, "r": r_, **wb, "cur": wb["w"]})
        for ti, tk in enumerate(d_.get("latin", [])):
            word_map.append({"p": p_, "r": -1, "i0": ti, "i1": -1, "w": tk["text"],
                             "box": tk["box"], "cur": tk["text"], "tok": True})
    for wm in word_map:
        new = engine.apply_rules(wm["w"], rules_now)
        wm["new"] = None if new == wm["w"] else new

    sel = st.session_state.get("sel_word")
    for p_, (im_, d_) in enumerate(zip(images, det)):
        ann = im_.copy(); drw = _ImageDraw.Draw(ann)
        # 인식 불완전 행 = 회색 박스
        for row_ in d_["rows"]:
            if not row_["ok"] and row_.get("sylls"):
                bs = row_["sylls"]
                drw.rectangle([min(b[0] for b in bs) - 6, min(b[1] for b in bs) - 6,
                               max(b[2] for b in bs) + 6, max(b[3] for b in bs) + 6],
                              outline=(170, 170, 170), width=2)
        for wm in word_map:
            if wm["p"] != p_:
                continue
            x0, y0, x1, y1 = wm["box"]
            col, wd = ((16, 150, 72), 5) if wm["new"] is not None else ((220, 30, 30), 3)
            if sel and (wm["p"], wm["r"], wm["i0"]) == (sel["p"], sel["r"], sel["i0"]) \
                    and sel.get("tok", False) == wm.get("tok", False):
                col, wd = (37, 99, 235), 7
            drw.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], outline=col, width=wd)
            if wm["new"] is not None:
                fp, fi = engine.find_font()
                _f = _IF.truetype(fp, max(18, int((y1 - y0) * 0.8)), index=fi)
                drw.text((x0, max(0, y0 - (y1 - y0) - 12)), wm["new"] or "␡", fill=(16, 150, 72), font=_f)
        disp_w = 860
        val = streamlit_image_coordinates(ann, width=disp_w, key=f"imgclick_{fhash}_{p_}")
        lk = f"lastclick_{fhash}_{p_}"
        if val and st.session_state.get(lk) != (val["x"], val["y"]):
            st.session_state[lk] = (val["x"], val["y"])
            sc = im_.width / disp_w
            cx, cy = val["x"] * sc, val["y"] * sc
            hit = None
            for wm in word_map:
                if wm["p"] != p_:
                    continue
                x0, y0, x1, y1 = wm["box"]
                if x0 - 10 <= cx <= x1 + 10 and y0 - 12 <= cy <= y1 + 12:
                    hit = wm; break
            if hit:
                st.session_state["sel_word"] = hit
                st.session_state["open_dlg"] = None
                st.rerun()

    # 수정 예정 목록
    pending = [(wm["w"], wm["new"]) for wm in word_map if wm["new"] is not None]
    if pending:
        uniq = list(dict.fromkeys(pending))
        with st.expander(f"📝 바뀔 단어 ({len(pending)}곳)", expanded=False):
            st.markdown("\n".join(f"- `{o}` → **`{n or '(삭제)'}`**" for o, n in uniq))

    # 팝업 디스패치 (열려 있는 동안 매 rerun마다 호출해야 내부 버튼이 동작)
    _dlg = st.session_state.get("open_dlg")
    if _dlg == "rules":
        rules_dialog()
    elif _dlg == "rows":
        rows_dialog()
    elif st.session_state.get("sel_word"):
        word_dialog()

    # ---------- ③ 수정완료 ----------
    st.subheader("③ 수정완료")

    def build_news_and_tokens():
        rl = parse_current_rules()
        news, tokens = [], []
        for d in det:
            news.append([engine.apply_rules(row["text"], rl) if row["ok"] else row["text"]
                         for row in d["rows"]])
            tks = []
            for tk in d.get("latin", []):
                t2 = engine.apply_rules(tk["text"], rl)
                if t2 != tk["text"]:
                    tks.append({"box": tk["box"], "old": tk["text"], "new": t2})
            tokens.append(tks)
        return news, tokens

    b1, b2, _sp = st.columns([1, 1.2, 1])
    with b1:
        do_check = st.button("🔍 바뀔 위치 확인", use_container_width=True)
    with b2:
        do_done = st.button("✔ 수정완료 (미리보기)", type="primary", use_container_width=True)

    if do_check:
        news, tokens = build_news_and_tokens()
        if not any(n != [r["text"] for r in d["rows"]] for n, d in zip(news, det)) and not any(tokens):
            st.warning("아직 바뀌는 내용이 없어요. 빨간 박스를 클릭해 규칙을 만들어 주세요.")
        else:
            with st.spinner("확인용 미리보기 생성 중…"):
                st.session_state["preview"] = [
                    engine.render_page(im, d["rows"], nt, dpi, preview=True, scale=d.get("scale"))[0]
                    for im, d, nt in zip(images, det, news)]
                st.session_state["result"] = None
    if do_done:
        news, tokens = build_news_and_tokens()
        if not any(n != [r["text"] for r in d["rows"]] for n, d in zip(news, det)) and not any(tokens):
            st.warning("아직 바뀌는 내용이 없어요. 빨간 박스를 클릭해 규칙을 만들어 주세요.")
        else:
            with st.spinner("가사를 다시 쓰는 중…"):
                outs, n = [], 0
                for im, d, nt, tks in zip(images, det, news, tokens):
                    o, ch = engine.render_page(im, d["rows"], nt, dpi, scale=d.get("scale"),
                                               token_edits=tks)
                    outs.append(o); n += len(ch) + len(tks)
                st.session_state["result"] = (outs, engine.to_pdf_bytes(outs, dpi), n)
                st.session_state["preview"] = None

    if st.session_state.get("result"):
        outs, pdf, n = st.session_state["result"]
        stem = os.path.splitext(src_name)[0]
        st.success(f"{n}곳을 고쳤어요. 아래 미리보기를 확인하고 PDF로 저장하세요.")
        fname = st.text_input("저장 파일명", value=f"{stem}_수정.pdf")
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        st.download_button("⬇️ 수정본 PDF 다운로드", pdf, file_name=fname,
                           mime="application/pdf", type="primary")
        st.caption("저장 위치는 브라우저 다운로드 폴더예요. 다른 곳에 저장하려면 브라우저 설정에서 「다운로드 전에 위치 확인」을 켜세요.")
        for i, o in enumerate(outs):
            st.image(o, caption=f"{i + 1}페이지 (수정본 미리보기)", use_container_width=True)
    elif st.session_state.get("preview"):
        st.info("빨간 박스 = 지워질 음절, 그 아래 빨간 글자 = 새 글자. 위치 확인 후 「✔ 수정완료 (미리보기)」를 누르세요.")
        for i, o in enumerate(st.session_state["preview"]):
            st.image(o, caption=f"{i + 1}페이지 (바뀔 위치)", use_container_width=True)


st.markdown("""
<div class="hero">
  <div class="orb"></div>
  <div>
    <h1>악보 가사, 클릭해서 고쳐드려요</h1>
    <p>음표·코드·기호는 그대로 — 빨간 박스를 클릭해 수정·삭제하면 같은 자리에 다시 씁니다.</p>
  </div>
</div>
""", unsafe_allow_html=True)
tab_edit, tab_help = st.tabs(["🎼 편집기", "❓ 도움말"])
with tab_help:
    render_help()
with tab_edit:
    render_editor()

st.divider()
st.caption(f"악보 가사 수정기 v{APP_VERSION} · You쌤융합교육원 by YouDefine · AI is what YOU define · 문의 yousam4u@gmail.com")
