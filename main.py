"""Day1~Day8에서 배운 Python과 FastAPI로 만드는 작은 방명록."""

import asyncio
from contextlib import asynccontextmanager, closing
from datetime import datetime, timedelta, timezone
from html import escape
import os
from pathlib import Path
import sqlite3
from string import Template
from typing import Annotated
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("GUESTBOOK_DB_PATH", str(BASE_DIR / "data" / "guestbook.db")))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

PAGE_SIZE = 10
ENTRY_LIMIT = 1000
MAX_FORM_BYTES = 8192
KST = timezone(timedelta(hours=9))
PAGE_TEMPLATE = Template((BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8"))


class EntryCreate(BaseModel):
    """Day6의 Field/공백 정리와 Day8의 요청 검증을 활용합니다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=20, description="이름 또는 별명")
    message: str = Field(min_length=1, max_length=500, description="남기고 싶은 한마디")

    @field_validator("name", "message")
    @classmethod
    def reject_null_character(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("사용할 수 없는 문자가 포함되어 있습니다.")
        return value

    @field_validator("name")
    @classmethod
    def name_is_one_line(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("이름은 한 줄로 입력해 주세요.")
        return value


class EntryOut(BaseModel):
    id: int
    name: str
    message: str
    created_at: datetime


class EntryPage(BaseModel):
    entries: list[EntryOut]
    total: int
    page: int
    page_size: int
    total_pages: int


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # AUTOINCREMENT나 관계 테이블 없이 entries 테이블 하나만 만듭니다.
    with closing(connect_db()) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 20),
                message TEXT NOT NULL CHECK(length(trim(message)) BETWEEN 1 AND 500),
                created_at TEXT NOT NULL
            )
            """
        )


def list_entries(page: int = 1) -> dict:
    with closing(connect_db()) as connection:
        # 개수와 목록이 같은 시점의 데이터를 보도록 읽기 트랜잭션을 씁니다.
        connection.execute("BEGIN")
        total = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = min(page, total_pages)
        rows = connection.execute(
            "SELECT id, name, message, created_at FROM entries ORDER BY id DESC LIMIT ? OFFSET ?",
            (PAGE_SIZE, (page - 1) * PAGE_SIZE),
        ).fetchall()
    return {
        "entries": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "total_pages": total_pages,
    }


def save_entry(entry: EntryCreate) -> dict:
    with closing(connect_db()) as connection, connection:
        # 동시에 등록해도 개수 제한을 넘지 않도록 쓰기 순서를 정합니다.
        connection.execute("BEGIN IMMEDIATE")
        total = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        if total >= ENTRY_LIMIT:
            raise HTTPException(409, "방명록이 가득 찼습니다. 지금은 새로운 글을 남길 수 없어요.")
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = connection.execute(
            "INSERT INTO entries (name, message, created_at) VALUES (?, ?, ?)",
            (entry.name, entry.message, created_at),
        )
        return {"id": cursor.lastrowid, **entry.model_dump(), "created_at": created_at}


def check_origin(request: Request) -> None:
    """다른 사이트의 브라우저 폼에서 몰래 글을 등록하는 요청을 거절합니다."""
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "방명록 페이지에서 직접 작성해 주세요.")
    origin = request.headers.get("origin")
    if origin:
        try:
            source = urlsplit(origin)
        except ValueError:
            raise HTTPException(403, "방명록 페이지에서 직접 작성해 주세요.") from None
        if source.scheme not in {"http", "https"} or source.netloc.lower() != request.url.netloc.lower():
            raise HTTPException(403, "방명록 페이지에서 직접 작성해 주세요.")


def render_page(
    page: int = 1, *, name: str = "", message: str = "", error: str = "", saved: bool = False,
    status_code: int = 200,
) -> HTMLResponse:
    result = list_entries(page)
    cards = []
    for entry in result["entries"]:
        timestamp = datetime.fromisoformat(entry["created_at"]).astimezone(KST)
        cards.append(
            '<article class="entry">'
            '<div class="entry-top"><div class="visitor">'
            f'<span class="avatar" aria-hidden="true">{escape(entry["name"][0])}</span>'
            f'<h3>{escape(entry["name"])}</h3></div>'
            f'<span class="entry-number">#{entry["id"]:03d}</span></div>'
            f'<p class="entry-message">{escape(entry["message"])}</p>'
            f'<time datetime="{escape(entry["created_at"])}">{timestamp:%Y.%m.%d · %H:%M}</time>'
            '</article>'
        )

    if not cards:
        cards.append(
            '<div class="empty-state"><span class="empty-mark" aria-hidden="true">✳</span>'
            '<h3>첫 번째 안부를 기다리고 있어요.</h3>'
            '<p>오늘의 기분, 짧은 인사, 마음에 남은 문장.<br>어떤 이야기든 좋아요.</p></div>'
        )

    pagination = ""
    if result["total_pages"] > 1:
        previous = (
            f'<a href="/?page={result["page"] - 1}#messages">← 이전</a>'
            if result["page"] > 1 else '<span class="page-disabled">← 이전</span>'
        )
        following = (
            f'<a href="/?page={result["page"] + 1}#messages">다음 →</a>'
            if result["page"] < result["total_pages"] else '<span class="page-disabled">다음 →</span>'
        )
        pagination = (
            f'<nav class="pagination" aria-label="방명록 페이지">{previous}'
            f'<span>{result["page"]} / {result["total_pages"]}</span>{following}</nav>'
        )

    notice = ""
    if error:
        notice = f'<div class="notice notice-error" role="alert">{escape(error)}</div>'
    elif saved:
        notice = '<div class="notice notice-success" role="status">안부가 잘 도착했어요. 남겨 주셔서 고맙습니다.</div>'
    elif result["total"] >= ENTRY_LIMIT:
        notice = '<div class="notice notice-error" role="status">방명록이 가득 찼습니다. 지금은 새로운 글을 남길 수 없어요.</div>'

    content = PAGE_TEMPLATE.substitute(
        total=result["total"], cards="".join(cards), pagination=pagination, notice=notice,
        name=escape(name), message=escape(message), year=datetime.now(KST).year,
        disabled="disabled" if result["total"] >= ENTRY_LIMIT else "",
    )
    return HTMLResponse(content, status_code=status_code, headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    })


def process_form(form: dict[str, str]) -> HTMLResponse | RedirectResponse:
    try:
        entry = EntryCreate.model_validate(form)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field = "이름" if first_error["loc"][0] == "name" else "내용"
        limit = 20 if field == "이름" else 500
        error = f"{field}은(는) 앞뒤 공백을 제외하고 1~{limit}자로 입력해 주세요."
        if first_error["type"] == "extra_forbidden":
            error = "이름과 내용만 입력해 주세요."
        elif first_error["type"] == "value_error":
            error = str(first_error["ctx"]["error"])
        return render_page(name=form.get("name", ""), message=form.get("message", ""), error=error, status_code=422)

    try:
        save_entry(entry)
    except HTTPException as exc:
        return render_page(name=entry.name, message=entry.message, error=exc.detail, status_code=exc.status_code)
    # POST 후 GET으로 이동하므로 새로고침으로 글이 다시 등록되지 않습니다.
    return RedirectResponse("/?saved=1#messages", status_code=303)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="작은 방명록 API", version="1.0.0",
    description="Day1~Day8의 Python·FastAPI·Pydantic을 활용한 방명록입니다.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(page: Annotated[int, Query(ge=1, le=100)] = 1, saved: bool = False):
    return render_page(page, saved=saved)


@app.post("/entries", include_in_schema=False)
async def submit_entry(request: Request):
    check_origin(request)
    media_type = request.headers.get("content-type", "").partition(";")[0].lower()
    if media_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "HTML 방명록 양식으로 작성해 주세요.")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_FORM_BYTES:
            raise HTTPException(413, "작성한 내용이 너무 큽니다.")
        body.extend(chunk)
    try:
        values = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True,
                          max_num_fields=2, encoding="utf-8", errors="strict")
        if any(len(items) != 1 for items in values.values()):
            raise ValueError("Duplicate field")
    except (UnicodeError, ValueError):
        raise HTTPException(400, "양식이 올바르지 않습니다. 이름과 내용을 다시 입력해 주세요.") from None
    # Day7의 asyncio: DB 작업이 비동기 요청 처리를 막지 않도록 분리합니다.
    return await asyncio.to_thread(process_form, {key: items[0] for key, items in values.items()})


@app.get("/api/entries", response_model=EntryPage, summary="방명록 목록 조회")
def read_entries(page: Annotated[int, Query(ge=1, le=100)] = 1):
    return list_entries(page)


@app.post("/api/entries", response_model=EntryOut, status_code=201, summary="방명록 작성",
          responses={403: {"description": "다른 사이트에서 보낸 요청"}, 409: {"description": "등록 한도 도달"}})
def create_entry(entry: EntryCreate, request: Request):
    check_origin(request)
    return save_entry(entry)


@app.get("/api/entries/{entry_id}", response_model=EntryOut, summary="방명록 한 건 조회",
         responses={404: {"description": "방명록 없음"}})
def read_entry(entry_id: Annotated[int, PathParam(ge=1)]):
    with closing(connect_db()) as connection:
        row = connection.execute(
            "SELECT id, name, message, created_at FROM entries WHERE id = ?", (entry_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "방명록을 찾을 수 없습니다.")
    return dict(row)


@app.get("/health", summary="서버와 DB 상태 확인")
def health():
    with closing(connect_db()) as connection:
        connection.execute("SELECT id FROM entries LIMIT 1").fetchone()
    return {"status": "ok"}
