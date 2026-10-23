# 작은 방명록

`Codex.md`를 기준으로 AI4의 Day1~Day8 예제를 살펴보고 만든 학습용 방명록입니다. 이름과 글을 남기면 SQLite에 저장하고 최신순으로 보여 줍니다.

## 현재 AI4에서 바로 실행

PowerShell에서 실행합니다.

```powershell
cd C:\AI4\DAY1-DAY8
.\run.cmd
```

- 앱: <http://127.0.0.1:8008>
- API 실습 문서: <http://127.0.0.1:8008/docs>
- 서버 상태: <http://127.0.0.1:8008/health>
- 종료: 실행한 터미널에서 `Ctrl+C`
- 다른 포트: `.\run.cmd 8018`

`run.cmd`는 이 폴더의 `.venv`를 우선 사용합니다. 없으면 기존 `DAY7/sync_async_shop/.runtime/python/python.exe`를 사용합니다. 기존 루트 `.venv`는 원본 Python 실행 경로가 없어 현재 실행되지 않으므로 사용하지 않습니다. 새 패키지를 설치하거나 기존 환경을 수정하지 않았습니다. PowerShell의 스크립트 실행 정책을 변경할 필요도 없습니다.

## 다른 PC에서 설치

Python 3.12~3.14가 설치되어 있어야 합니다. Python 3.13.9에서 검증했습니다.

```powershell
cd C:\AI4\DAY1-DAY8
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.cmd
```

`python` 명령 대신 `py -3.13`을 사용하는 환경에서는 첫 번째 Python 명령을 바꾸세요. 가상환경을 활성화하지 않아도 됩니다.

직접 서버를 실행할 수도 있습니다.

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8008 --workers 1
```

## 사용 방법

1. 이름 또는 별명을 1~20자로 입력합니다.
2. 남기고 싶은 말을 1~500자로 입력하고 **마음 남기기**를 누릅니다.
3. 등록한 글을 오른쪽 목록에서 확인합니다. 휴대전화 화면에서는 작성란 아래에 목록이 배치됩니다.
4. 10개보다 많으면 이전·다음 링크로 이동합니다.

앞뒤 공백은 정리하며 공백뿐인 글은 등록되지 않습니다. 작성한 글은 방문자 모두에게 공개됩니다. 화면에 표시되는 시간은 한국 시간입니다.

## 구성

```text
DAY1-DAY8/
├── Codex.md               # 사용자가 작성한 원본 요구사항
├── main.py                # 모델, DB, HTML 렌더링, FastAPI 경로
├── templates/index.html   # HTML 화면
├── static/style.css       # 반응형 CSS
├── requirements.txt       # 기존 FastAPI·Pydantic·Uvicorn
├── requirements-dev.txt   # 기존 Day8의 TestClient용 HTTPX
├── run.cmd                # 현재 AI4에서 실행
├── test_app.py            # 자동 검증
├── verify_http.py         # 실제 서버 시작·등록·재시작 검증
├── STUDY_NOTES.md          # Day1~Day8와 구현의 연결
├── DEPLOY.md              # 무료 배포 후보와 배포 방법
├── VERIFICATION.md        # 검증 결과와 범위
└── data/guestbook.db       # 첫 실행 시 생성, Git 제외
```

HTML/CSS를 서버에서 반환합니다. 추가 템플릿 라이브러리 없이 Python 내장 `string.Template`과 `html.escape`를 사용합니다. HTML 폼은 내장 `urllib.parse`로 읽으므로 `python-multipart`도 필요하지 않습니다.

## 데이터베이스

Python 내장 `sqlite3`를 사용합니다. 테이블은 `entries` 하나이며 외래 키와 관계 테이블은 없습니다.

| 열 | 타입 | 의미 |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | 글 번호 |
| `name` | TEXT NOT NULL | 이름, 최대 20자 |
| `message` | TEXT NOT NULL | 내용, 최대 500자 |
| `created_at` | TEXT NOT NULL | UTC 기준 ISO 8601 작성 시각 |

`AUTOINCREMENT`를 사용하지 않아 `sqlite_sequence` 보조 테이블도 생기지 않습니다. 등록할 때마다 트랜잭션을 커밋하고 연결을 닫습니다. SQL에는 `?` 매개변수 바인딩을 사용합니다. 서버가 재시작되어도 DB 파일이 유지되는 환경에서는 글이 남습니다.

기본 경로는 이 앱의 `data/guestbook.db`입니다. 환경 변수로 다른 경로를 지정할 수 있습니다. 상대 경로는 앱 폴더 기준입니다.

```powershell
$env:GUESTBOOK_DB_PATH = 'C:\AI4\DAY1-DAY8\data\guestbook.db'
.\run.cmd
```

최대 1,000개까지만 등록됩니다. 한도에 도달하면 새 글을 거절하며 기존 글은 보존합니다. 현재 기능은 **작성·목록·개별 조회**입니다. 회원가입, 수정, 삭제, 첨부파일은 포함하지 않습니다.

## API 실습

| 요청 | 동작 | 성공 응답 |
|---|---|---|
| `GET /` | HTML 방명록 | 200 |
| `POST /entries` | HTML 폼 등록 | 303 → 목록 |
| `GET /api/entries?page=1` | 10개씩 목록 조회 | 200 |
| `POST /api/entries` | JSON으로 글 작성 | 201 |
| `GET /api/entries/{id}` | 한 건 조회 | 200 |
| `GET /health` | 서버·DB 확인 | 200 |

`/docs`에서 `POST /api/entries` → **Try it out** → 다음 JSON → **Execute** 순서로 실습할 수 있습니다.

```json
{"name": "방문자", "message": "오늘도 반가워요!"}
```

입력 오류는 422, 없는 글은 404, 다른 사이트의 브라우저 등록 요청은 403, 1,000개 한도 도달은 409입니다. HTML 폼 등록 후에는 GET으로 이동하므로 새로고침으로 같은 글이 다시 등록되지 않습니다. 등록 버튼을 여러 번 누르거나 같은 API를 여러 번 호출하면 각각의 글로 저장됩니다.

## 검사

현재 AI4의 기존 Python으로 실행합니다.

```powershell
cd C:\AI4\DAY1-DAY8
..\DAY7\sync_async_shop\.runtime\python\python.exe test_app.py
..\DAY7\sync_async_shop\.runtime\python\python.exe verify_http.py
```

다른 PC에서는 개발용 의존성을 설치하고 실행합니다. `unittest`는 Python 내장 모듈입니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe test_app.py
.\.venv\Scripts\python.exe verify_http.py
```

검사는 별도 임시 DB를 사용합니다. `data/guestbook.db`에 검사 글을 넣지 않습니다. 상세 결과는 [VERIFICATION.md](VERIFICATION.md), 학습 연결은 [STUDY_NOTES.md](STUDY_NOTES.md), 무료 배포 방법은 [DEPLOY.md](DEPLOY.md)를 확인하세요.
