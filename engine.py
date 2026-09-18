"""
engine.py — 스캔 악보 한글 가사 교체 엔진 (Streamlit 앱 백엔드)

흐름
  load_images(bytes, filename)  →  PIL 페이지 이미지들
  detect_page(img)              →  {"rows": [{"y", "text", "sylls", "ok"}]}   (가사 행 + 음절별 잉크 박스)
  render_page(img, rows, new_texts, preview)  →  수정된 PIL 이미지
  to_pdf_bytes(images)          →  PDF bytes

원리
  - Tesseract(kor)로 한글 토큰 좌표 → y로 묶어 가사 행만 추림
  - 각 행에서 실제 잉크 덩어리(연결 성분)를 찾아, OCR 음절 수에 맞춰 DP로 음절 박스를 만든다
    (P.M. 같은 비가사 덩어리는 DP가 버림)
  - 바뀐 음절만 그 잉크 박스를 흰색으로 지우고, 행 단위로 통일한 폰트 크기로 새 글자를 그린다
"""
import glob, os, re, subprocess, tempfile, io
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

DPI = 300
FONT_CANDIDATES = [
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 1),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 1),
    ("/usr/share/fonts/opentype/noto/NotoSansCJKkr-Regular.otf", 0),
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("C:/Windows/Fonts/malgun.ttf", 0),
    (os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "NotoSansKR-Regular.ttf"), 0),
]

def find_font():
    for p, i in FONT_CANDIDATES:
        if os.path.exists(p):
            return p, i
    raise RuntimeError("한글 폰트를 찾지 못했습니다. fonts/NotoSansKR-Regular.ttf 를 넣어주세요.")

# ---------------- 입력 ----------------
def load_images(data: bytes, filename: str, dpi: int = DPI):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        work = tempfile.mkdtemp(prefix="lyricfix_")
        src = os.path.join(work, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", src, os.path.join(work, "page")], check=True)
        return [Image.open(p).convert("RGB") for p in sorted(glob.glob(os.path.join(work, "page-*.png")))]
    return [Image.open(io.BytesIO(data)).convert("RGB")]

# ---------------- 규칙 ----------------
def parse_rules(text: str):
    """'원본=수정' 줄들 → [(a,b)]. 음절 수가 다르면 ValueError."""
    rules = []
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        if not ln or "=" not in ln:
            continue
        a, b = ln.split("=", 1)
        a, b = re.sub(r"\s+", "", a), re.sub(r"\s+", "", b)
        if len(a) != len(b):
            raise ValueError(f"음절 수가 다릅니다: '{a}'({len(a)}) = '{b}'({len(b)})")
        if a:
            rules.append((a, b))
    return rules

def apply_rules(s: str, rules):
    for a, b in rules:
        s = s.replace(a, b)
    return s

# ---------------- OCR ----------------
def _ocr_tokens(img: Image.Image, min_conf=55):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        img.save(tf.name)
        r = subprocess.run(["tesseract", tf.name, "stdout", "-l", "kor", "--psm", "6", "tsv"],
                           capture_output=True, text=True)
    os.unlink(tf.name)
    lines = r.stdout.strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0].split("\t")
    toks = []
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) < 12:
            continue
        d = dict(zip(header, p))
        kor = "".join(re.findall(r"[가-힣]+", d.get("text", "")))
        if not kor:
            continue
        try:
            conf = float(d["conf"])
        except ValueError:
            continue
        if conf < min_conf:
            continue
        l, t, w, h = int(d["left"]), int(d["top"]), int(d["width"]), int(d["height"])
        toks.append({"text": kor, "left": l, "top": t, "right": l + w, "bottom": t + h,
                     "cy": t + h // 2, "h": h})
    return toks

def _cluster_rows(toks, y_tol):
    toks = sorted(toks, key=lambda t: t["cy"])
    rows = []
    for t in toks:
        if rows and abs(t["cy"] - np.mean([x["cy"] for x in rows[-1]])) < y_tol:
            rows[-1].append(t)
        else:
            rows.append([t])
    for r in rows:
        r.sort(key=lambda t: t["left"])
    return rows

def _is_lyric_row(row, s):
    if sum(len(t["text"]) for t in row) < 4:
        return False
    med_h = float(np.median([t["h"] for t in row]))
    return 36 * s <= med_h <= 58 * s

# ---------------- 음절 기하 ----------------
def _glyph_groups(gray, x0, y0, x1, y1, s):
    reg = (gray[y0:y1, x0:x1] < 128).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(reg, connectivity=8)
    comps = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if area < 12 * s * s or h <= 4 * s:
            continue
        comps.append([x0 + x, y0 + y, x0 + x + w, y0 + y + h])
    comps.sort(key=lambda c: c[0])
    groups = []
    for c in comps:
        if groups:
            g = groups[-1]
            ov = min(g[2], c[2]) - max(g[0], c[0])
            if ov > 0.4 * min(g[2] - g[0], c[2] - c[0]):
                g[0], g[1], g[2], g[3] = min(g[0], c[0]), min(g[1], c[1]), max(g[2], c[2]), max(g[3], c[3])
                continue
        groups.append(list(c))
    return groups

def _partition(groups, n, target_w, skip_cost=1.5):
    m = len(groups)
    if m < n:
        return None
    INF = float("inf")
    def cost(a, b):
        w = groups[b][2] - groups[a][0]
        c = ((w - target_w) / target_w) ** 2
        for k in range(a, b):
            if groups[k + 1][0] - groups[k][2] > 0.35 * target_w:
                c += 2.0
        return c
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + skip_cost; bk[0][j] = ("skip", j - 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if dp[i][j - 1] < INF and dp[i][j - 1] + skip_cost < dp[i][j]:
                dp[i][j], bk[i][j] = dp[i][j - 1] + skip_cost, ("skip", j - 1)
            for k in range(i - 1, j):
                if dp[i - 1][k] < INF:
                    v = dp[i - 1][k] + cost(k, j - 1)
                    if v < dp[i][j]:
                        dp[i][j], bk[i][j] = v, ("take", k)
    if dp[n][m] == INF:
        return None
    sylls, i, j = [], n, m
    while i > 0 or j > 0:
        kind, k = bk[i][j]
        if kind == "skip":
            j = k
        else:
            g = groups[k:j]
            sylls.append([min(x[0] for x in g), min(x[1] for x in g), max(x[2] for x in g), max(x[3] for x in g)])
            i, j = i - 1, k
    return sylls[::-1]

# ---------------- 검출 ----------------
def detect_page(img: Image.Image, dpi: int = DPI):
    """가사 행과 음절별 잉크 박스를 계산한다. 결과는 JSON 직렬화 가능."""
    s = dpi / 300.0
    gray = np.array(img.convert("L"))
    toks = _ocr_tokens(img)
    rows = [r for r in _cluster_rows(toks, 25 * s) if _is_lyric_row(r, s)]
    rows.sort(key=lambda r: np.mean([t["cy"] for t in r]))
    out = []
    for row in rows:
        text = "".join(t["text"] for t in row)
        bx0 = max(0, min(t["left"] for t in row) - int(15 * s))
        bx1 = min(img.width, max(t["right"] for t in row) + int(15 * s))
        by0 = max(0, min(t["top"] for t in row) - int(6 * s))
        by1 = min(img.height, max(t["bottom"] for t in row) + int(6 * s))
        groups = _glyph_groups(gray, bx0, by0, bx1, by1, s)
        target_w = float(np.median([(t["right"] - t["left"]) / len(t["text"]) for t in row]))
        near = lambda g: any(t["left"] - 0.7 * target_w <= (g[0] + g[2]) / 2 <= t["right"] + 0.7 * target_w for t in row)
        groups = [g for g in groups if near(g)]
        sylls = _partition(groups, len(text), target_w)
        out.append({"y": int(np.mean([t["cy"] for t in row])), "text": text,
                    "sylls": [[int(v) for v in b] for b in sylls] if sylls else None,
                    "ok": sylls is not None})
    return {"rows": out}

# ---------------- 렌더 ----------------
def _row_font(font_path, font_index, sylls):
    hs = [b[3] - b[1] for b in sylls]; ws = [b[2] - b[0] for b in sylls]
    th, tw = float(np.percentile(hs, 90)), float(np.median(ws))
    for sz in range(int(th * 1.6), 8, -1):
        f = ImageFont.truetype(font_path, sz, index=font_index)
        b = f.getbbox("한")
        if (b[3] - b[1]) <= th * 1.02 and (b[2] - b[0]) <= tw * 1.05:
            return f
    return ImageFont.truetype(font_path, max(8, int(th * 0.8)), index=font_index)

def render_page(img: Image.Image, rows, new_texts, dpi: int = DPI, preview: bool = False):
    """rows: detect_page 결과. new_texts: 행별 수정 문자열(원본과 길이 동일). 바뀐 음절만 처리."""
    s = dpi / 300.0
    font_path, font_index = find_font()
    out = img.copy()
    draw = ImageDraw.Draw(out)
    changes = []
    m = int(2 * s)
    for ri, (row, new) in enumerate(zip(rows, new_texts)):
        old = row["text"]
        if not row["ok"] or new == old or len(new) != len(old):
            continue
        font = _row_font(font_path, font_index, row["sylls"])
        for i, (o, n) in enumerate(zip(old, new)):
            if o == n:
                continue
            x0, y0, x1, y1 = row["sylls"][i]
            changes.append((ri, i, o, n))
            if preview:
                draw.rectangle([x0 - m, y0 - m, x1 + m, y1 + m], outline=(220, 30, 30), width=max(2, int(3 * s)))
                f = ImageFont.truetype(font_path, max(10, int(22 * s)), index=font_index)
                draw.text((x0, y1 + 3 * s), n, fill=(220, 30, 30), font=f)
            else:
                draw.rectangle([x0 - m, y0 - m, x1 + m, y1 + m], fill=(255, 255, 255))
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                b = font.getbbox(n)
                draw.text((cx - (b[2] - b[0]) / 2 - b[0], cy - (b[3] - b[1]) / 2 - b[1]), n, fill=(0, 0, 0), font=font)
    return out, changes

def to_pdf_bytes(images, dpi: int = DPI) -> bytes:
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=float(dpi))
    return buf.getvalue()

def check_env():
    """앱 시작 시 의존 도구 점검 → 문제 목록(비어 있으면 OK)."""
    import shutil
    problems = []
    for tool in ("tesseract", "pdftoppm"):
        if not shutil.which(tool):
            problems.append(f"{tool} 없음 (packages.txt: tesseract-ocr, tesseract-ocr-kor, poppler-utils)")
    if shutil.which("tesseract"):
        r = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
        if "kor" not in r.stdout + r.stderr:
            problems.append("tesseract 한국어 데이터(kor) 없음 (packages.txt: tesseract-ocr-kor)")
    try:
        find_font()
    except RuntimeError as e:
        problems.append(str(e))
    return problems
