# AI4 학습 자료와 구현의 연결

## 살펴본 자료

기존 학습 파일을 앱에서 직접 import하지 않고, 배운 문법과 구조를 이 폴더에 독립적으로 적용했습니다. 실습 파일에는 실행 중 입력을 받거나 미완성 문법을 포함한 것도 있기 때문입니다.

| 자료 | 확인한 학습 요소 | 방명록에 적용한 위치 |
|---|---|---|
| `Day1/python_basics_practice.py` | 변수, 함수, 조건문, 반복문, f-string, 입력 예외 처리 | 글 카드 반복 생성, 빈 목록 처리, 오류 문구, 글 번호 표시 |
| `Day2/오후/main.py`, `Day2/오후/Day2-4.py` | 함수 반환값, 사전, 리스트 순회·필터링 | 목록 응답 사전, DB 행을 사전 리스트로 변환 |
| `DAY3/오전/day3-1.py`, `DAY3/오후/day3-3_fixed.py` | 클래스, 타입 힌트, 입력 정리, 조건 검사, 예외 | 요청·응답 모델, 앞뒤 공백 정리, 이름·내용 길이 검증 |
| `DAY4/day4-1.py` | 리스트 컴프리헨션 형태의 실습 | 조회 결과 변환에 리스트 컴프리헨션 사용 |
| Day5 | 현재 AI4에 해당 폴더가 없음 | 확인 가능한 자료를 기준으로 구현 |
| `DAY6/ch08_project/models.py`, `store.py`, `app.py` | BaseModel, Field, ConfigDict, field_validator, 요청과 응답 분리, 저장소 함수 분리 | `EntryCreate`, `EntryOut`, `EntryPage`, `save_entry`, `list_entries` |
| `DAY7/sync_async_shop/app.py`, `README.md` | FastAPI, StaticFiles, asyncio와 스레드 작업 분리 | CSS 제공, 비동기 폼 읽기와 `asyncio.to_thread`로 SQLite 작업 분리 |
| `Day8/lesson_01_swagger`~`lesson_08_final_verification` | Swagger, Query/Path, 요청 검증, 상태 코드, 응답 모델, 상태 시나리오 테스트 | `/docs`, 페이지 번호 검증, 201/303/403/404/409/422, TestClient 검사 |

`DAY4/day4-1.py`의 실습 코드는 미완성이므로 실행 가능한 결과물로 취급하지 않았습니다. 방명록에는 임의 난수를 생성하는 기능이 필요하지 않아 해당 기능을 추가하지 않았습니다.

## 요구사항에 맞춰 선택한 방식

- 서버 패키지는 기존 AI4의 FastAPI·Pydantic·Uvicorn을 그대로 사용합니다.
- 화면은 HTML/CSS 한 페이지입니다. 화면에 직접 작성한 JavaScript는 없습니다.
- HTML 치환과 출력 이스케이프는 Python 표준 라이브러리입니다.
- DB는 요구사항에서 지정한 Python 내장 SQLite이며 테이블 하나입니다.
- 목록은 SQL의 기본 정렬·LIMIT·OFFSET으로 나눕니다. 별도의 추천·검색·암호화 알고리즘은 추가하지 않았습니다.
- 저장 시에는 SQL 매개변수 바인딩과 트랜잭션을 사용합니다.
- 테스트는 Python 내장 unittest와 기존 Day8의 HTTPX/TestClient를 사용합니다.
- 새 외부 라이브러리나 외부 API가 필요하지 않아 추가 설치와 API 키 발급을 진행하지 않았습니다.

## 요청이 처리되는 순서

1. 브라우저가 `GET /`를 요청합니다.
2. SQLite에서 글 개수와 최신 글 10개를 읽습니다.
3. 사용자가 쓴 내용에 `html.escape`를 적용하고 HTML에 채워 반환합니다.
4. 사용자가 일반 HTML 폼으로 `POST /entries`를 보냅니다.
5. 폼의 크기·형식과 Pydantic 모델을 검증합니다.
6. 이름·내용·UTC 시각을 `entries` 테이블에 넣고 커밋합니다.
7. 303 응답으로 목록으로 이동합니다. 표시 시각은 한국 시간으로 바꿉니다.

FastAPI의 일반 `def` 경로는 스레드 풀에서 실행됩니다. `async def`인 HTML 폼 경로에서는 요청 본문을 읽은 다음 `asyncio.to_thread`로 검증·DB·HTML 작업을 맡깁니다. SQLite 연결은 사용하는 스레드 안에서 생성하고 닫습니다.
