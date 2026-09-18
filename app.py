"""악보 가사 수정기 — 스캔 악보 PDF/이미지의 한글 가사를 음절 단위로 고친다 (Streamlit)."""
import hashlib, os
import streamlit as st
import engine

st.set_page_config(page_title="악보 가사 수정기", page_icon="🎼", layout="wide")

# ---------- 사이드바 ----------
with st.sidebar:
    st.markdown("## 🎼 악보 가사 수정기")
    st.caption("You쌤융합교육원 by YouDefine")
    st.markdown(
        "**사용법**\n"
        "1. 악보 PDF/이미지 업로드\n"
        "2. 자동 인식된 가사 행을 **글자만 고쳐서** 수정\n"
        "3. 미리보기 확인 → PDF 다운로드\n\n"
        "**규칙**: 음표 1개 = 음절 1개. 음절 수는 바꿀 수 없어요."
    )
    problems = engine.check_env()
    if problems:
        st.error("환경 점검 실패:\n\n" + "\n".join(f"- {p}" for p in problems))
    with st.expander("고급"):
        dpi = st.select_slider("해상도(dpi)", options=[200, 300, 400], value=300,
                               help="인식이 안 되는 행이 있으면 400으로")

st.title("악보 가사 수정기")
st.caption("악보의 음표·코드·기호는 그대로 두고, 잘못된 가사 글자만 같은 자리에 다시 씁니다.")

# ---------- ① 업로드 & 인식 ----------
up = st.file_uploader("악보 파일 (PDF · PNG · JPG)", type=["pdf", "png", "jpg", "jpeg"])
if not up:
    st.info("악보 파일을 올리면 가사 행을 자동으로 찾아 편집 칸을 만들어 드려요.")
    st.stop()

data = up.getvalue()
fhash = hashlib.md5(data + str(dpi).encode()).hexdigest()[:10]

if st.session_state.get("fhash") != fhash:
    with st.spinner("가사 행을 찾는 중… (페이지당 10~20초)"):
        images = engine.load_images(data, up.name, dpi)
        det = [engine.detect_page(im, dpi) for im in images]
    st.session_state.update({"fhash": fhash, "images": images, "det": det,
                             "preview": None, "result": None})
    # 편집 칸 초기값 = OCR 결과
    for p, d in enumerate(det):
        for r, row in enumerate(d["rows"]):
            st.session_state[f"{fhash}_{p}_{r}"] = row["text"]

images, det = st.session_state["images"], st.session_state["det"]
n_rows = sum(len(d["rows"]) for d in det)
st.success(f"{len(images)}페이지 · 가사 {n_rows}행 인식")

# ---------- ② 일괄 규칙 ----------
st.subheader("② 일괄 규칙 (선택)")
c1, c2 = st.columns([3, 1])
with c1:
    rules_text = st.text_area(
        "한 줄에 `원본=수정` — 같은 오타가 반복될 때. 음절 수가 같아야 해요. (예: `마상가고=마산가고`)",
        placeholder="여기에 직접 입력하세요. 회색 글씨는 입력이 아니에요.",
        height=110, key=f"{fhash}_rules")
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
st.caption("인식된 글자 중 틀린 것만 고치세요. 글자 수가 달라지면 빨간 경고가 뜹니다.")
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
            if len(val) != len(row["text"]):
                st.error(f"음절 수 {len(val)} ≠ 원본 {len(row['text'])} — 글자 수는 같아야 해요")
                has_error = True
            elif val != row["text"]:
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
        st.session_state["preview"] = [engine.render_page(im, d["rows"], nt, dpi, preview=True)[0]
                                       for im, d, nt in zip(images, det, new_texts)]
        st.session_state["result"] = None
if do_apply:
    with st.spinner("가사를 다시 쓰는 중…"):
        outs, n = [], 0
        for im, d, nt in zip(images, det, new_texts):
            o, ch = engine.render_page(im, d["rows"], nt, dpi)
            outs.append(o); n += len(ch)
        st.session_state["result"] = (outs, engine.to_pdf_bytes(outs, dpi), n)
        st.session_state["preview"] = None

if st.session_state.get("result"):
    outs, pdf, n = st.session_state["result"]
    stem = os.path.splitext(up.name)[0]
    st.success(f"음절 {n}개를 고쳤어요.")
    st.download_button("⬇️ 수정본 PDF 다운로드", pdf, file_name=f"{stem}_수정.pdf",
                       mime="application/pdf", type="primary")
    for i, o in enumerate(outs):
        st.image(o, caption=f"{i + 1}페이지 (수정본)", use_container_width=True)
elif st.session_state.get("preview"):
    st.info("빨간 박스 = 바뀔 음절, 그 아래 빨간 글자 = 새 글자. 확인 후 「수정본 PDF 만들기」를 누르세요.")
    for i, o in enumerate(st.session_state["preview"]):
        st.image(o, caption=f"{i + 1}페이지 (미리보기)", use_container_width=True)
