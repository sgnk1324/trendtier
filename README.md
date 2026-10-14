# TrendTier MVP

한국 인터넷 유행어의 검색 관심도와 YouTube 공개 댓글 신호를 비교하는 Streamlit MVP.

## 현재 구현 상태

- 대시보드, 검색, 티어표, 점수 계산, 차트: 구현
- 샘플 데이터: 포함 (실제 플랫폼 데이터가 아님)
- YouTube 공식 API 댓글 수집 모듈: 구현 (API 키 필요)
- Google Trends 공식 API: 알파 접근 제한 때문에 실제 연결부는 의도적으로 비활성화
- 매일 자동 수집: 아직 구현되지 않음. GitHub Actions 파일은 플레이스홀더

## 로컬 실행

1. Python 3.10 이상 설치
2. 터미널에서 프로젝트 폴더로 이동
3. 아래 실행:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 Streamlit이 알려주는 주소를 엽니다.

## YouTube API 설정

1. Google Cloud Console에서 프로젝트 생성
2. YouTube Data API v3 활성화
3. API key 발급
4. 키를 환경변수 `YOUTUBE_API_KEY`로 설정
5. 공개 댓글이 활성화된 동영상 ID를 사용해 테스트:

```bash
python collectors/youtube_comments.py --video-id VIDEO_ID --pages 1
```

Windows PowerShell:
```powershell
$env:YOUTUBE_API_KEY="YOUR_KEY"
python collectors/youtube_comments.py --video-id VIDEO_ID --pages 1
```

API 키를 GitHub에 올리거나 공개 저장소에 커밋하지 마세요. 키 제한 설정을 적용하세요.

YouTube API의 기본 쿼터와 정책을 확인하고, 댓글 데이터 저장·갱신·삭제 요건을 준수해야 합니다. 댓글 수집 모듈은 공개 댓글 스레드만 요청하며, 검색 API 기반 자동 후보 발굴은 아직 연결되지 않았습니다.

## Google Trends

공식 Google Trends API는 제한된 알파 접근 프로그램입니다. 접근 승인이 확인되지 않은 상태에서 임의의 비공식 엔드포인트나 웹 스크래핑을 사용하지 않습니다.

- 공식 문서: https://developers.google.com/search/apis/trends
- 웹 인터페이스: https://trends.google.com/trends/

공식 API 권한을 확보하면 `collectors/google_trends.py`를 실제 API 규격에 맞춰 구현해야 합니다. 그전에는 허용된 CSV 내보내기 데이터를 `data/metrics.csv`에 넣어 대시보드를 테스트할 수 있습니다.

## CSV 입력 형식

`data/metrics.csv`는 다음 컬럼이 필요합니다:

- `term`: 유행어
- `meaning`: 뜻/설명
- `search_index`: 동일한 수집 범위 안에서 정규화한 검색 관심도
- `comment_rate`: 댓글 언급률(퍼센트가 아닌 비율 값; 예 0.9는 0.9%)
- `search_growth`: 검색 관심도 상승 지표
- `comment_growth`: 댓글 언급률 상승 지표

이 파일의 샘플 값은 예시입니다. 실제 측정값으로 오인하지 않도록 출처와 수집 날짜를 별도 관리해야 합니다.

## 배포: Streamlit Community Cloud

1. GitHub 계정 생성 또는 로그인
2. 새 저장소를 만들고 이 폴더의 파일을 업로드
3. https://share.streamlit.io/ 접속
4. 저장소, 브랜치, 메인 파일 `app.py`를 선택해 배포
5. 현재 버전은 데모 모드로 공개 가능

API 키는 GitHub 코드에 넣지 말고, 배포 서비스의 Secrets 설정 또는 환경변수로 저장하세요.

## 점수 공식

각 지표를 후보 유행어 집합 안에서 백분위 점수(0~100)로 변환하고 아래 가중치로 합산합니다.

`score = 0.35*search + 0.20*search_growth + 0.30*comment_rate + 0.15*comment_growth`

이 가중치는 검증된 통계 모델이 아니라 초기 가설입니다. 실제 설문/미래 데이터와 비교해 검증하고 조정해야 합니다. 작은 후보 집합에서는 티어가 불안정할 수 있습니다.

## 한계

- 검색 관심도는 절대 검색량이 아닙니다.
- YouTube 댓글 표본은 한국 10~20대 전체를 대표하지 않습니다.
- Google Trends 자동 API 연결은 승인 전에는 동작하지 않습니다.
- 이 MVP는 실데이터 자동 수집이 완성된 서비스가 아니라, 화면과 점수 계산이 실행되는 기반 프로젝트입니다.
