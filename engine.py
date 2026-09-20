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
TARGET_LONG_SIDE = 3400   # A4 300dpi 세로(3508)에 가깝게 — 사진도 이 크기로 맞춰 글자 크기를 스캔과 비슷하게

def _normalize_photo(img: Image.Image) -> Image.Image:
    """폰 사진용: EXIF 회전 반영 → 크기 맞춤 → 배경 조명 정규화(그늘 제거, 배경을 흰색으로)."""
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img).convert("RGB")
    long_side = max(img.size)
    if long_side < TARGET_LONG_SIDE * 0.7 or long_side > TARGET_LONG_SIDE * 1.4:
        r = TARGET_LONG_SIDE / long_side
        img = img.resize((round(img.width * r), round(img.height * r)), Image.LANCZOS)
    g = np.array(img.convert("L")).astype(np.float32)
    # 배경 추정: 큰 커널 모폴로지 closing(글자를 지워 배경만) → 나눠서 평탄화
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, k)
    flat = np.clip(g / np.maximum(bg, 1) * 255.0, 0, 255)
    # 대비 늘리기: 글자는 검게, 종이는 희게
    lo, hi = np.percentile(flat, 1), np.percentile(flat, 60)
    flat = np.clip((flat - lo) / max(hi - lo, 1) * 255.0, 0, 255).astype(np.uint8)
    # 기울기 보정: 오선(긴 수평선)의 각도 중앙값으로 회전
    ang = _skew_angle(flat)
    if abs(ang) > 0.15:
        h, w = flat.shape
        M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        flat = cv2.warpAffine(flat, M, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    return Image.fromarray(flat).convert("RGB")

def _skew_angle(gray_u8) -> float:
    """오선처럼 긴 수평선들의 평균 기울기(도). 못 찾으면 0."""
    edges = cv2.Canny(gray_u8, 50, 150)
    w = gray_u8.shape[1]
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=200, minLineLength=int(w * 0.25), maxLineGap=20)
    if lines is None:
        return 0.0
    angs = []
    for x1, y1, x2, y2 in lines[:, 0]:
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(a) < 5:
            angs.append(a)
    return float(np.median(angs)) if len(angs) >= 5 else 0.0

def is_scan_like(img: Image.Image) -> bool:
    """배경이 이미 거의 흰색이면 스캔/디지털 악보로 본다."""
    g = np.array(img.convert("L"))
    return np.percentile(g, 70) >= 235

def load_images(data: bytes, filename: str, dpi: int = DPI):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        work = tempfile.mkdtemp(prefix="lyricfix_")
        src = os.path.join(work, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-png", src, os.path.join(work, "page")], check=True)
        return [Image.open(p).convert("RGB") for p in sorted(glob.glob(os.path.join(work, "page-*.png")))]
    img = Image.open(io.BytesIO(data))
    from PIL import ImageOps
    img = ImageOps.exif_transpose(img).convert("RGB")
    if is_scan_like(img) and TARGET_LONG_SIDE * 0.7 <= max(img.size) <= TARGET_LONG_SIDE * 1.4:
        return [img]
    return [_normalize_photo(img)]

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

def _latin_tokens(img: Image.Image, min_conf=55):
    """영문/기호 토큰(제목 부제·작곡자·튜닝·코드 등). 순수 숫자는 제외."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        img.save(tf.name)
        r = subprocess.run(["tesseract", tf.name, "stdout", "--psm", "6", "tsv"],
                           capture_output=True, text=True)
    os.unlink(tf.name)
    lines = r.stdout.strip().split("\n")
    if len(lines) < 2:
        return []
    header = lines[0].split("\t")
    out = []
    for ln in lines[1:]:
        p = ln.split("\t")
        if len(p) < 12:
            continue
        d = dict(zip(header, p))
        txt = d.get("text", "").strip()
        m = re.fullmatch(r"[A-Za-z][A-Za-z0-9#.'\-]*", txt)
        if not m:
            continue
        try:
            conf = float(d["conf"])
        except ValueError:
            continue
        if conf < min_conf:
            continue
        l, t, w, h = int(d["left"]), int(d["top"]), int(d["width"]), int(d["height"])
        if h < 8:
            continue
        out.append({"text": txt, "box": [l, t, l + w, t + h]})
    return out

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
    gray = np.array(img.convert("L"))
    toks = _ocr_tokens(img)
    # 글자 크기 스케일: 스캔/사진/해상도 무관하게 OCR 글자 높이 중앙값(≈47px@300dpi 기준)에서 자동 추정
    hs = [t["h"] for t in toks if len(t["text"]) >= 2]
    s = float(np.clip(np.median(hs) / 47.0, 0.5, 2.0)) if len(hs) >= 5 else dpi / 300.0
    # 모든 한글 텍스트 행(2자 이상) — 가사 여부는 kind로 분류
    rows = [r for r in _cluster_rows(toks, 25 * s) if sum(len(t["text"]) for t in r) >= 2]
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
                    "kind": "lyric" if _is_lyric_row(row, s) else "text",
                    "tokens": [t["text"] for t in row],
                    "sylls": [[int(v) for v in b] for b in sylls] if sylls else None,
                    "ok": sylls is not None})
    return {"rows": out, "scale": round(s, 3), "latin": _latin_tokens(img)}

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

def render_page(img: Image.Image, rows, new_texts, dpi: int = DPI, preview: bool = False, scale: float = None,
                token_edits=None):
    """rows: detect_page 결과의 rows. new_texts: 행별 수정 문자열(원본과 길이 동일). 바뀐 음절만 처리."""
    s = scale if scale else dpi / 300.0
    font_path, font_index = find_font()
    out = img.copy()
    draw = ImageDraw.Draw(out)
    changes = []
    m = int(2 * s)
    for ri, (row, new) in enumerate(zip(rows, new_texts)):
        old = row["text"]
        if not row["ok"] or new == old:
            continue
        font = _row_font(font_path, font_index, row["sylls"])
        if len(new) != len(old):
            # 자유 편집: 행 전체를 지우고 새 텍스트를 다시 쓴다 (음표 비동기 행용 — 글자 수 변경 허용)
            bx0 = min(b[0] for b in row["sylls"]); by0 = min(b[1] for b in row["sylls"])
            bx1 = max(b[2] for b in row["sylls"]); by1 = max(b[3] for b in row["sylls"])
            changes.append((ri, -1, old, new))
            if preview:
                draw.rectangle([bx0 - m, by0 - m, bx1 + m, by1 + m],
                               outline=(220, 30, 30), width=max(2, int(3 * s)))
                f = ImageFont.truetype(font_path, max(10, int(22 * s)), index=font_index)
                draw.text((bx0, by1 + 3 * s), new, fill=(220, 30, 30), font=f)
            else:
                draw.rectangle([bx0 - m, by0 - m, bx1 + m, by1 + m], fill=(255, 255, 255))
                cy = (by0 + by1) / 2
                x = float(bx0)
                pitch = float(np.median([b[2] - b[0] for b in row["sylls"]])) * 1.12
                for ch in new:
                    b = font.getbbox(ch)
                    draw.text((x - b[0], cy - (b[3] - b[1]) / 2 - b[1]), ch, fill=(0, 0, 0), font=font)
                    x += max(b[2] - b[0], pitch * 0.6) + pitch * 0.12 if ch != " " else pitch * 0.6
            continue
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
    # 영문 토큰 교체 (자유 길이): 토큰 박스를 지우고 새 텍스트를 같은 높이로 그림
    for te in (token_edits or []):
        x0, y0, x1, y1 = te["box"]
        changes.append((-1, -1, te["old"], te["new"]))
        if preview:
            draw.rectangle([x0 - m, y0 - m, x1 + m, y1 + m], outline=(220, 30, 30), width=max(2, int(3 * s)))
            f = ImageFont.truetype(font_path, max(10, int(22 * s)), index=font_index)
            draw.text((x0, y1 + 3 * s), te["new"], fill=(220, 30, 30), font=f)
            continue
        draw.rectangle([x0 - int(4 * s), y0 - int(4 * s), x1 + int(4 * s), y1 + int(4 * s)], fill=(255, 255, 255))
        if te["new"]:
            fh = y1 - y0
            for sz in range(int(fh * 1.5), 7, -1):
                f = ImageFont.truetype(font_path, sz, index=font_index)
                b = f.getbbox("Ag한")
                if (b[3] - b[1]) <= fh * 1.15:
                    break
            b = f.getbbox(te["new"])
            draw.text((x0 - b[0], (y0 + y1) / 2 - (b[3] - b[1]) / 2 - b[1]), te["new"], fill=(0, 0, 0), font=f)
    return out, changes

def to_pdf_bytes(images, dpi: int = DPI) -> bytes:
    buf = io.BytesIO()
    images[0].save(buf, "PDF", save_all=True, append_images=images[1:], resolution=float(dpi))
    return buf.getvalue()

# ---------------- 맞춤법 제안 (hunspell-ko, 선택 기능) ----------------
def spell_available() -> bool:
    import shutil
    if not shutil.which("hunspell"):
        return False
    for d in ("/usr/share/hunspell/ko_KR.dic", "/usr/share/hunspell/ko.dic"):
        if os.path.exists(d):
            return True
    return False

def _hunspell_check(words):
    """words → {word: suggestions or None}. None=사전에 있음."""
    uniq = list(dict.fromkeys(w for w in words if len(w) >= 2))
    if not uniq:
        return {}
    inp = "\n".join("^" + w for w in uniq) + "\n"   # ^ = 파이프 명령 방지
    r = subprocess.run(["hunspell", "-d", "ko_KR", "-i", "UTF-8", "-a"],
                       input=inp, capture_output=True, text=True)
    res, i = {}, 0
    for ln in r.stdout.splitlines():
        if not ln or ln.startswith("@"):
            continue
        if ln[0] in "*+-":
            res[uniq[i]] = None; i += 1
        elif ln[0] == "&":
            head, sugs = ln.split(":", 1)
            res[uniq[i]] = [x.strip() for x in sugs.split(",")]; i += 1
        elif ln[0] == "#":
            res[uniq[i]] = []; i += 1
        if i >= len(uniq):
            break
    return res

def row_words(row):
    """음절 박스 간격으로 어절을 재구성 → [(word, start_idx)]"""
    text, sylls = row["text"], row.get("sylls")
    if not sylls or len(sylls) != len(text):
        return []
    pitch = float(np.median([b[2] - b[0] for b in sylls]))
    words, start = [], 0
    for i in range(1, len(text)):
        if sylls[i][0] - sylls[i - 1][2] > 0.6 * pitch:   # 어절 경계
            words.append((text[start:i], start)); start = i
    words.append((text[start:], start))
    return words

def word_boxes(row):
    """행의 어절 목록: [{"w", "i0", "i1", "box":[x0,y0,x1,y1]}] (i1은 exclusive)"""
    out = []
    text, sylls = row["text"], row.get("sylls")
    if not row.get("ok") or not sylls or len(sylls) != len(text):
        return out
    for w, i0 in row_words(row):
        i1 = i0 + len(w)
        bs = sylls[i0:i1]
        out.append({"w": w, "i0": i0, "i1": i1,
                    "box": [min(b[0] for b in bs), min(b[1] for b in bs),
                            max(b[2] for b in bs), max(b[3] for b in bs)]})
    return out

def suggest_page(rows):
    """행별 표기 검사(베타). 사전에 없는 어절을 플래그하고 후보를 보여준다 — 자동 교체는 하지 않음.
    반환: [{"notes": [str]}] (rows와 같은 길이)"""
    per_row_words = [row_words(r) if r.get("ok") else [] for r in rows]
    all_words = [w for ws in per_row_words for w, _ in ws if len(w) >= 2]
    checked = _hunspell_check(all_words)
    out = []
    for ws in per_row_words:
        notes = []
        for w, _ in ws:
            sugs = checked.get(w)
            if not sugs:                       # 사전에 있음(None) 또는 후보 없음([])
                continue
            same = [x for x in sugs if " " not in x and len(x) == len(w)
                    and sum(a != b for a, b in zip(x, w)) == 1]
            if not same:                       # 한 글자 차이 후보가 없으면 표시 안 함 (노이즈 억제)
                continue
            notes.append(f"'{w}' 확인 필요 · 비슷한 말: {', '.join(same[:3])}")
        out.append({"notes": notes})
    return out

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
