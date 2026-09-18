# 악보 가사 수정기 (lyric-fix-app)

스캔 악보 PDF/이미지의 **한글 가사 오타를 음절 단위로 고치는** Streamlit 앱.
음표·코드·기호는 픽셀 그대로 두고, 바뀌는 음절의 잉크만 지우고 같은 자리에 다시 씁니다.

## 사용 흐름
1. PDF/PNG/JPG 업로드 → 가사 행 자동 인식 (페이지당 10~20초)
2. 행별 편집 칸에서 틀린 글자만 수정 (음절 수 유지) — 반복 오타는 「일괄 규칙」에 `원본=수정`
3. 미리보기(빨간 박스) 확인 → 「수정본 PDF 만들기」 → 다운로드

## 📱 모바일
- 같은 주소를 폰 브라우저로 열면 1열 레이아웃으로 바뀝니다. 홈 화면에 추가하면 앱처럼 실행돼요
  (iPhone: Safari 공유 → 홈 화면에 추가 / Android: Chrome ⋮ → 홈 화면에 추가).
- 업로드 칸에서 사진 촬영을 고르거나 「📷 카메라로 찍기」로 바로 찍을 수 있어요.
- 폰 사진은 자동 보정됩니다: EXIF 회전 → 크기 맞춤(긴 변 3400px) → 배경 조명 정규화(그늘 제거) → 오선 기준 기울기 보정.
  글자 크기 스케일은 OCR 결과에서 자동 추정해 해상도에 무관하게 동작해요.

## Streamlit Community Cloud 배포
1. 이 폴더를 GitHub 저장소로 push (`app.py`, `engine.py`, `requirements.txt`, `packages.txt`, `.streamlit/`)
2. https://share.streamlit.io → New app → 저장소/브랜치 선택, Main file: `app.py`
3. Deploy — `packages.txt`가 tesseract(kor)·poppler·Noto CJK 폰트를 자동 설치합니다

## 로컬 실행
```bash
# Ubuntu/Debian
sudo apt-get install -y tesseract-ocr tesseract-ocr-kor poppler-utils fonts-noto-cjk
pip install -r requirements.txt
streamlit run app.py
```
Windows: Tesseract(kor 데이터 포함)와 poppler를 설치해 PATH에 추가하고, 한글 폰트는 `engine.py`의 `FONT_CANDIDATES`에 맑은 고딕이 포함돼 있어 그대로 동작합니다.

## 한계
- 텍스트 레이어가 있는 PDF는 이 방식이 과함(그땐 PDF 편집기로 직접 수정)
- 음절 수가 달라지는 수정(글자 추가/삭제)은 지원하지 않음
- OCR이 행의 음절 수를 잘못 세면 그 행은 편집 불가로 표시됨 → dpi 400 재시도

## 구조
- `engine.py` — 검출(OCR + 잉크 덩어리 DP 분할) / 렌더 / PDF
- `app.py` — Streamlit UI
