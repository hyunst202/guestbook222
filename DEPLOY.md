# 무료 배포 방법

확인일: 2026-10-23. 서비스 공식 요금표와 문서를 기준으로 정리했습니다. 이 문서는 배포 안내이며 외부 계정 생성·업로드·공개 배포는 수행하지 않았습니다.

## 후보 비교

| 서비스 | 공식 확인 내용 | 이 앱과의 적합성 |
|---|---|---|
| **alwaysdata Free** | 개인 용도 월 0유로, SSD 1GB, RAM 256MB, CPU ¼, 기본 `alwaysdata.net` 주소 | ASGI 실행과 계정 파일 저장을 지원하므로 SQLite 방명록의 첫 번째 후보로 판단 |
| Render Free Web Service | 무료 Python 서버 제공. 유휴 15분 후 정지. 재배포·재시작·정지 시 로컬 파일 삭제 | SQLite 글이 사라질 수 있어 일회성 시연용으로만 적합 |
| PythonAnywhere ASGI | FastAPI 배포 안내가 있으나 ASGI는 실험 기능이고 장기 요금 미확정 | 무료 ASGI 사용 가능 여부를 계정에서 확인한 뒤 선택할 후보 |

근거: [alwaysdata 요금표](https://www.alwaysdata.com/en/offers/), [alwaysdata Python·ASGI 설정](https://help.alwaysdata.com/en/docs/web-hosting/languages/python/configuration/), [Render 무료 서비스 제약](https://render.com/docs/free), [PythonAnywhere ASGI 안내](https://help.pythonanywhere.com/pages/ASGICommandLine/).

요금표와 ASGI 지원을 바탕으로 alwaysdata를 추천했습니다. 해당 서비스 계정에서 이 앱의 실행·재시작·데이터 유지까지 검증한 것은 아닙니다. 가입 화면에 표시되는 Free 플랜 조건을 최종 확인하세요.

## alwaysdata에 배포

### 1. 계정과 Python 준비

1. [alwaysdata](https://www.alwaysdata.com/en/offers/)에서 **Free**를 선택합니다. Plus의 무료 체험과 구분하세요.
2. 관리 화면의 **Environment → Python**에서 Python 3.13을 선택합니다.
3. SFTP 또는 SSH 접속 정보를 확인합니다. 아래 `ACCOUNT`는 실제 계정명으로 바꿉니다.

### 2. 앱 파일 업로드

서버의 `/home/ACCOUNT/guestbook/`에 다음 파일을 올립니다.

이 폴더의 `guestbook-deploy.zip`에는 필요한 앱 파일과 이 배포 안내를 담았습니다. 서버의 `guestbook` 폴더에 압축을 풀거나, 아래 파일만 SFTP로 올려도 됩니다.

```text
/home/ACCOUNT/guestbook/
├── main.py
├── requirements.txt
├── templates/index.html
└── static/style.css
```

검사 코드, Windows 실행 파일, `.runtime`, `.venv`, 기존 학습 폴더는 업로드하지 않아도 됩니다. SQLite 파일은 처음 실행할 때 생성됩니다.

### 3. 서버에서 설치

SSH의 Bash에서 실행합니다. alwaysdata 공식 문서는 시스템 Python 실행 명령으로 `python`을 사용하도록 안내합니다.

```bash
cd /home/ACCOUNT/guestbook
python -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
```

이 설치는 배포할 때 사용자가 수행하는 단계입니다. 개발 중에는 AI4에 이미 있는 패키지를 사용했습니다.

### 4. Web → Sites에서 사이트 설정

[공식 User program 설정](https://help.alwaysdata.com/en/docs/web-hosting/sites/http-servers/user-program/)에 따라 **Web → Sites → Add a site**에서 입력합니다.

| 항목 | 값 |
|---|---|
| Name | 작은 방명록 |
| Addresses | `ACCOUNT.alwaysdata.net` |
| Type | **User program** |
| Working directory | `/home/ACCOUNT/guestbook` |
| Command | 아래 명령 |
| Environment | `GUESTBOOK_DB_PATH=/home/ACCOUNT/guestbook-data/guestbook.db` |

```bash
/home/ACCOUNT/guestbook/.venv/bin/python -m uvicorn main:app --host :: --port $PORT --workers 1
```

`$PORT`는 서비스가 제공하는 환경 변수이므로 숫자로 임의 변경하지 않습니다. `--host ::`는 공식 ASGI 문서가 요구하는 IPv6 대기를 위한 설정입니다. 자동 재시작 감시용 `--reload`는 사용하지 않습니다. HTTPS 강제 사용 옵션을 켭니다.

### 5. 배포 확인

1. `https://ACCOUNT.alwaysdata.net/health`에서 `{"status":"ok"}`를 확인합니다.
2. 첫 화면에서 테스트 글 한 개를 작성합니다.
3. 관리 화면에서 사이트를 재시작합니다.
4. 작성한 글이 남아 있는지 확인합니다.
5. `/docs`에서 API 응답도 확인합니다.

DB는 코드 폴더 바깥의 `guestbook-data`에 두므로 앱 코드만 다시 업로드해도 데이터를 덮어쓰지 않습니다. 사이트 오류는 관리 화면 로그와 `/home/ACCOUNT/admin/logs/sites/`에서 확인할 수 있습니다.

## 코드 업데이트와 데이터 보관

수정한 `main.py`, `templates`, `static`만 덮어쓴 뒤 사이트를 재시작합니다. 의존성이 바뀌면 설치 명령도 다시 실행합니다. `guestbook-data` 폴더는 유지합니다.

운영 중 DB를 복사할 때는 단순 파일 복사 대신 SQLite 백업 기능을 사용할 수 있습니다. 아래는 서버 계정의 Bash에서 실행하는 선택 사항입니다.

```bash
cd /home/ACCOUNT
python - <<'PY'
from contextlib import closing
import sqlite3

with closing(sqlite3.connect("guestbook-data/guestbook.db")) as source:
    with closing(sqlite3.connect("guestbook-data/guestbook-backup.db")) as target:
        source.backup(target)
PY
```

백업 파일도 계정 저장 공간을 사용합니다. 오래된 백업 정리는 사용자가 보관 여부를 확인한 뒤 진행하세요.

## 무료 범위에 맞춘 앱 구성

- 웹 서버 프로세스 1개, SQLite 테이블 1개.
- 최대 1,000개, 이름 20자, 내용 500자, 목록은 페이지당 10개.
- 이미지·파일 업로드, 외부 AI/API, 별도 DB 서버, 예약 작업, 자동 확장 없음.
- HTML/CSS는 앱에서 제공하며 외부 폰트·CDN을 사용하지 않음. `/docs`는 FastAPI 기본 문서 화면 사용.

이 제한은 앱 데이터가 무한정 늘어나는 것을 막습니다. 실제 호스팅 메모리·로그·패키지·계정 전체 파일 사용량은 배포 후 관리 화면에서 확인해야 합니다. 무료 플랜의 한도를 초과하면 유료 업그레이드를 자동으로 진행하지 말고 서비스 설정과 사용량을 먼저 확인하세요.

## Render로 일회성 시연하기

별도 영구 저장소 없이 시연할 때만 사용합니다.

1. 이 코드를 자신의 GitHub 저장소에 업로드합니다.
2. Render에서 **New → Web Service**로 저장소를 연결합니다.
3. **Root Directory**: `DAY1-DAY8`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
6. **Instance Type**: `Free`

무료 웹 서비스에는 영구 디스크를 붙일 수 없습니다. 유휴 정지를 포함한 재시작 때 SQLite 데이터가 사라집니다. DB를 외부 서비스로 바꾸면 `Codex.md`의 내장 DB 조건과 달라지므로 이 구현에서는 바꾸지 않았습니다. [공식 제약 확인](https://render.com/docs/free)
