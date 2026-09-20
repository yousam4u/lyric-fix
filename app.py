"""악보 가사 수정기 — 스캔 악보 PDF/이미지의 한글 가사를 음절 단위로 고친다 (Streamlit)."""
import hashlib, os
import streamlit as st
import engine

APP_VERSION = "1.2.0"

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

  /* ── 카드류: 업로더·익스팬더·카메라 ── */
  [data-testid="stFileUploaderDropzone"]{ background:var(--card); border:1.5px dashed var(--blue-soft);
        border-radius:22px; box-shadow:var(--shadow); }
  [data-testid="stExpander"] details{ background:var(--card); border:1px solid #E8EEFB;
        border-radius:20px; box-shadow:var(--shadow); overflow:hidden; }
  [data-testid="stAlert"]{ border-radius:18px; border:none; box-shadow:var(--shadow); }

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

  /* ── 사이드바 ── */
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
        "2. 인식된 가사 행에서 **틀린 글자만** 고치기\n"
        "3. 미리보기 → PDF 다운로드\n\n"
        "자세한 방법은 위쪽 **❓ 도움말** 탭에 있어요."
    )
    problems = engine.check_env()
    if problems:
        st.error("환경 점검 실패:\n\n" + "\n".join(f"- {p}" for p in problems))
    with st.expander("고급"):
        dpi = st.select_slider("해상도(dpi)", options=[200, 300, 400], value=300,
                               help="인식이 안 되는 행이 있으면 400으로")

EXAMPLE_RULES = (
    "# 예시: 마산가고파 로타리 (긴 규칙 먼저, 음절 수 동일)\n"
    "마상가고바로탈이=마산가고파로타리\n"
    "마상가고바로=마산가고파로\n"
    "탈이=타리\n"
    "바로=파로\n"
    "조아=초아"
)

def render_help():
    st.markdown("""
### 이 앱이 하는 일
스캔한 악보(PDF·이미지)에서 **한글 가사의 틀린 글자만** 골라 같은 자리에 다시 씁니다.
음표·코드·기호·타브는 픽셀 그대로 두고, 바뀌는 음절의 잉크만 지우고 새로 그려요.
AI 모델을 쓰지 않아서 **사용료·토큰이 전혀 들지 않아요.**

### 사용 순서
| 단계 | 할 일 | 예시 |
|---|---|---|
| ① 업로드 | PDF / PNG / JPG를 올리면 가사 행을 자동으로 찾아요 (페이지당 10~20초) | `마산가고파_로타리.pdf` |
| ② 일괄 규칙 | 반복되는 오타는 `원본=수정`을 한 줄씩 써서 「규칙을 편집 칸에 반영」 | `조아=초아` |
| ③ 행 편집 | 행별 칸에서 틀린 글자만 직접 고치기 (글자 수는 그대로) | `마상가고` → `마산가고` |
| ④ 결과 | 「미리보기」로 빨간 박스 확인 → 「수정본 PDF 만들기」 → 다운로드 | `…_수정.pdf` |

### 규칙 작성법 (②)
- **음절 수가 같아야 해요.** 음표 1개에 음절 1개가 붙어 있어서 글자를 늘리거나 줄일 수 없어요.
  `마상가고=마산가고` ✅  /  `마상가고=마산가고파` ❌ (4≠5)
- **긴 규칙을 먼저** 쓰세요. 위에서부터 차례로 적용돼요.
- **한 글자 규칙은 위험**해요. `상=산`은 `세상을`까지 `세산을`로 바꿔요. 앞뒤 글자를 붙여 `마상가고=마산가고`처럼 쓰세요.
- 가사가 줄 끝에서 잘리면 조각 규칙을 추가하세요. 예) `마상가고바로탈이=…` 외에 `마상가고바로=마산가고파로`, `탈이=타리`.
- `#` 뒤는 주석이라 무시돼요. 「예시 규칙 보기」에서 복사하거나 버튼으로 그대로 넣을 수 있어요.

### 행 편집 요령 (③)
- 칸의 글자는 **OCR이 읽은 그대로**예요. 띄어쓰기는 무시되니 붙여 써도 돼요.
- 글자 수가 같으면 음절 단위 정밀 교체, 다르면 그 행 전체를 지우고 다시 쓰는 자유 편집이 돼요 (노란 안내 표시).
- 각 칸 아래 `변경 상→산, 바→파`처럼 무엇이 바뀌는지 표시돼요.
- 「원본으로 되돌리기」를 누르면 모든 칸이 인식 결과로 돌아가요.
- **"편집할 수 없어요"** 라고 뜨는 행은 OCR이 음절 수를 잘못 센 경우예요. 사이드바 「고급」에서 dpi를 **400**으로 올리고 파일을 다시 올려보세요.

### 결과 확인 (④)
- **미리보기**: 빨간 박스 = 지워질 음절, 그 아래 빨간 글자 = 새로 들어갈 글자. 위치가 맞는지만 보면 돼요.
- **수정본 PDF 만들기**: 바뀐 음절만 다시 그려요. 안 바뀐 글자는 원본 픽셀 그대로예요.
- 결과 파일명은 `원본이름_수정.pdf`. 화면 아래에 수정된 페이지도 같이 보여줘요.

### 📱 폰에서 쓰기
- **홈 화면에 추가**하면 앱처럼 아이콘으로 열려요.
  iPhone: Safari 하단 **공유(□↑) → 홈 화면에 추가** · Android: Chrome **⋮ → 홈 화면에 추가**
- 업로드 칸을 누르면 **사진 촬영 / 앨범 / 파일** 중에 고를 수 있고, 「📷 카메라로 찍기」로 바로 찍어도 돼요.
- **촬영 팁**: 정면에서, 페이지 전체가 들어오게, 그림자 없이. 그늘·누런 종이·약간의 기울기는 자동 보정되지만 심하게 비스듬한 사진은 글자를 놓칠 수 있어요.
- 사진은 스캔보다 인식 누락이 조금 있을 수 있어요. 빠진 글자는 ③ 행 편집 칸에서 확인하세요 (글자 수가 안 맞으면 그 행은 규칙이 안 먹을 수 있어요).

### 자주 묻는 질문
- **인식이 왜 오래 걸리나요?** 300dpi 이미지를 글자 단위로 읽어요. 파일당 한 번만 걸리고, 이후 편집·미리보기는 바로 돼요.
- **글자를 추가하거나 빼고 싶어요.** 글자 수를 바꾸면 그 행은 '자유 편집'으로 전환돼 행 전체를 지우고 새로 써요. 음표와 짝이 맞아야 하는 가사 행에는 비추천(정렬 어긋남), 제목·자유 문구 수정에 적합해요.
- **텍스트가 들어 있는 PDF인데요?** 스캔이 아니라 글자를 선택할 수 있는 PDF라면 PDF 편집기로 직접 고치는 게 더 깔끔해요.
- **새 글자의 폰트가 조금 달라 보여요.** 원본 글자 높이·폭에 맞춰 Noto Sans(본고딕)로 그려요. 대부분의 악보 폰트와 거의 같지만 특수 폰트는 살짝 다를 수 있어요.
- **여러 페이지도 되나요?** 네. 페이지마다 행이 따로 나오고, 결과도 한 PDF로 합쳐져요. 10페이지가 넘으면 느려질 수 있어요.

### 문제가 생기면
| 증상 | 해결 |
|---|---|
| 가사 행이 하나도 안 잡혀요 | 스캔이 흐리거나 기울어진 경우예요. 더 선명한 스캔(300dpi 이상)으로 다시 올려보세요 |
| 규칙을 넣어도 "일치하는 행이 없어요" | 규칙의 원본 글자가 ③에 **인식된 글자와 똑같아야** 해요. ③의 칸에서 글자를 복사해 쓰세요 |
| 일부 행만 "편집할 수 없어요" | 고급 → dpi 400으로 재시도 |
| 미리보기 박스가 엉뚱한 글자에 있어요 | 그 행은 적용하지 말고 원본으로 되돌린 뒤 문의해 주세요 |

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
        st.info("악보 파일을 올리거나 사진을 찍으면 가사 행을 자동으로 찾아 편집 칸을 만들어 드려요.")
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
        st.session_state.update({"fhash": fhash, "images": images, "det": det,
                                 "preview": None, "result": None})
        # 편집 칸 초기값 = OCR 결과, 규칙 칸 초기값 = 예시 규칙(그대로 적용 가능)
        for p, d in enumerate(det):
            for r, row in enumerate(d["rows"]):
                st.session_state[f"{fhash}_{p}_{r}"] = row["text"]
        st.session_state[f"{fhash}_rules"] = EXAMPLE_RULES

    images, det = st.session_state["images"], st.session_state["det"]
    n_rows = sum(len(d["rows"]) for d in det)
    if n_rows == 0:
        st.warning("가사 행을 찾지 못했어요. 스캔이 흐리거나 크게 기울어진 경우예요 — "
                   "더 선명하게(300dpi 이상) 스캔하거나, 정면에서 다시 촬영해 주세요. "
                   "사이드바 「고급」에서 dpi 400으로 올려 재시도할 수도 있어요.")
        return
    st.success(f"{len(images)}페이지 · 가사 {n_rows}행 인식")
    if not src_name.lower().endswith(".pdf"):
        st.caption("사진은 배경을 희게 펴고 기울기를 맞춘 보정본으로 작업해요. 결과 PDF도 보정본 기준이에요.")

    # ---------- ② 일괄 규칙 ----------
    st.subheader("② 일괄 규칙 (선택)")
    with st.expander("예시 규칙 보기 · 복사 · 그대로 넣기", expanded=False):
        st.code(EXAMPLE_RULES, language=None)   # 오른쪽 위 아이콘으로 복사
        if st.button("예시를 규칙 칸에 그대로 넣기"):
            st.session_state[f"{fhash}_rules"] = EXAMPLE_RULES
            st.session_state["rules_msg"] = ("info", "예시 규칙을 넣었어요. 「규칙을 편집 칸에 반영」을 누르세요.")
    c1, c2 = st.columns([3, 1])
    with c1:
        rules_text = st.text_area(
            "한 줄에 `원본=수정` — 같은 오타가 반복될 때. 음절 수가 같아야 해요. `#` 뒤는 주석.",
            placeholder="여기에 직접 입력하세요. 예) 마상가고=마산가고",
            height=150, key=f"{fhash}_rules")
    with c2:
        st.write("")
        st.write("")
        if st.button("규칙을 편집 칸에 반영", use_container_width=True):
            try:
                rules = engine.parse_rules(rules_text)
                if not rules:
                    st.session_state["rules_msg"] = ("warning", "규칙 칸이 비어 있어요. 왼쪽 칸에 `원본=수정`을 한 줄씩 입력한 뒤 눌러주세요.")
                else:
                    n_hit = 0
                    for p, d in enumerate(det):
                        for r, row in enumerate(d["rows"]):
                            new = engine.apply_rules(row["text"], rules)
                            if new != row["text"]:
                                st.session_state[f"{fhash}_{p}_{r}"] = new; n_hit += 1
                    if n_hit:
                        st.session_state["rules_msg"] = ("success", f"{n_hit}개 행에 반영했어요. 아래 ③에서 바뀐 글자를 확인하세요.")
                    else:
                        st.session_state["rules_msg"] = ("warning", "일치하는 행이 없어요. 규칙의 '원본'은 아래 ③에 인식된 글자와 똑같아야 해요 (띄어쓰기 없이).")
            except ValueError as e:
                st.session_state["rules_msg"] = ("error", str(e))
        if st.button("원본으로 되돌리기", use_container_width=True):
            for p, d in enumerate(det):
                for r, row in enumerate(d["rows"]):
                    st.session_state[f"{fhash}_{p}_{r}"] = row["text"]
            st.session_state["preview"] = st.session_state["result"] = None
            st.session_state["rules_msg"] = ("info", "모든 행을 인식 원본으로 되돌렸어요.")
    msg = st.session_state.pop("rules_msg", None)
    if msg:
        getattr(st, msg[0])(msg[1])
    st.caption("⚠️ 한 글자 규칙(`상=산`)은 다른 단어(세상→세산)까지 바꿔요. 앞뒤 글자를 붙여 쓰세요.")

    # ---------- ③ 행별 편집 ----------
    st.subheader("③ 가사 행 편집")
    st.caption("인식된 글자 중 틀린 것만 고치세요. 글자 수를 바꾸면 그 행은 통째로 다시 쓰는 자유 편집이 됩니다.")
    new_texts, total_changed, has_error = [], 0, False
    for p, (im, d) in enumerate(zip(images, det)):
        st.markdown(f"**{p + 1}페이지**")
        col_img, col_rows = st.columns([1, 2])
        with col_img:
            st.image(im, use_container_width=True)
        with col_rows:
            page_new = []
            for r, row in enumerate(d["rows"]):
                key = f"{fhash}_{p}_{r}"
                if not row["ok"]:
                    st.text_input(f"행 {r + 1}", value=row["text"], key=key, disabled=True)
                    st.warning("이 행은 음절 분할에 실패해 편집할 수 없어요 (dpi 400으로 재시도)")
                    page_new.append(row["text"]); continue
                val = st.text_input(f"행 {r + 1}", key=key)
                val = "".join(val.split())
                if val != row["text"]:
                    if len(val) != len(row["text"]):
                        total_changed += 1
                        st.warning(f"글자 수 변경({len(row['text'])}→{len(val)}) — 이 행 전체를 지우고 새로 써요. "
                                   "음표에 붙은 가사라면 정렬이 어긋날 수 있어요 (제목·자유 문구에 적합)")
                    else:
                        diffs = [f"{o}→{n}" for o, n in zip(row["text"], val) if o != n]
                        total_changed += len(diffs)
                        st.caption("변경 " + ", ".join(diffs))
                page_new.append(val)
            new_texts.append(page_new)

    # ---------- ④ 미리보기 / 적용 ----------
    st.subheader("④ 결과")
    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        do_preview = st.button("🔍 미리보기 (빨간 박스)", use_container_width=True, disabled=has_error)
    with b2:
        do_apply = st.button("✅ 수정본 PDF 만들기", type="primary", use_container_width=True,
                             disabled=has_error or total_changed == 0)

    if do_preview:
        with st.spinner("미리보기 생성 중…"):
            st.session_state["preview"] = [engine.render_page(im, d["rows"], nt, dpi, preview=True, scale=d.get("scale"))[0]
                                           for im, d, nt in zip(images, det, new_texts)]
            st.session_state["result"] = None
    if do_apply:
        with st.spinner("가사를 다시 쓰는 중…"):
            outs, n = [], 0
            for im, d, nt in zip(images, det, new_texts):
                o, ch = engine.render_page(im, d["rows"], nt, dpi, scale=d.get("scale"))
                outs.append(o); n += len(ch)
            st.session_state["result"] = (outs, engine.to_pdf_bytes(outs, dpi), n)
            st.session_state["preview"] = None

    if st.session_state.get("result"):
        outs, pdf, n = st.session_state["result"]
        stem = os.path.splitext(src_name)[0]
        st.success(f"음절 {n}개를 고쳤어요.")
        st.download_button("⬇️ 수정본 PDF 다운로드", pdf, file_name=f"{stem}_수정.pdf",
                           mime="application/pdf", type="primary")
        for i, o in enumerate(outs):
            st.image(o, caption=f"{i + 1}페이지 (수정본)", use_container_width=True)
    elif st.session_state.get("preview"):
        st.info("빨간 박스 = 바뀔 음절, 그 아래 빨간 글자 = 새 글자. 확인 후 「수정본 PDF 만들기」를 누르세요.")
        for i, o in enumerate(st.session_state["preview"]):
            st.image(o, caption=f"{i + 1}페이지 (미리보기)", use_container_width=True)

st.markdown("""
<div class="hero">
  <div class="orb"></div>
  <div>
    <h1>악보 가사, 콕 집어 고쳐드려요</h1>
    <p>음표·코드·기호는 그대로 — 잘못된 가사 글자만 같은 자리에 다시 씁니다. 악보를 올려보세요.</p>
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
