"""기존 Day8의 TestClient와 Python 내장 unittest로 실제 요청을 검증합니다."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient
import main


class GuestbookTests(unittest.TestCase):
    def setUp(self):
        # 앱의 실제 data/ 대신 매 검사마다 별도 임시 DB를 사용합니다.
        self.temp = tempfile.TemporaryDirectory(prefix="guestbook-test-")
        self.database = Path(self.temp.name) / "guestbook.db"
        self.db_patch = patch.object(main, "DB_PATH", self.database)
        self.db_patch.start()
        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.db_patch.stop()
        self.temp.cleanup()

    def create(self, name="방문자", message="안녕하세요!"):
        return self.client.post("/api/entries", json={"name": name, "message": message})

    def test_empty_page_and_local_css_without_javascript(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("첫 번째 안부를 기다리고 있어요.", response.text)
        self.assertNotIn("<script", response.text.lower())
        self.assertIn("form-action 'self'", response.headers["content-security-policy"])
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)

    def test_api_create_trim_and_response_contract(self):
        response = self.create("  방문자  ", "  첫째 줄\n둘째 줄  ")
        self.assertEqual(response.status_code, 201)
        entry = response.json()
        self.assertEqual(set(entry), {"id", "name", "message", "created_at"})
        self.assertEqual(entry["name"], "방문자")
        self.assertEqual(entry["message"], "첫째 줄\n둘째 줄")
        self.assertEqual(datetime.fromisoformat(entry["created_at"]).utcoffset(), timedelta(0))
        self.assertEqual(self.client.get(f'/api/entries/{entry["id"]}').json(), entry)

    def test_form_redirect_and_refresh_do_not_duplicate(self):
        response = self.client.post("/entries", data={"name": "손님", "message": "반가워요"}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/?saved=1#messages")
        for _ in range(2):
            response = self.client.get(response.headers.get("location", "/?saved=1"))
            self.assertEqual(response.status_code, 200)
            self.assertIn("안부가 잘 도착했어요", response.text)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 1)

    def test_invalid_api_values_are_not_stored(self):
        for payload in [
            {"name": "   ", "message": "안녕"},
            {"name": "손님", "message": "\n \t"},
            {"name": "가" * 21, "message": "안녕"},
            {"name": "손님", "message": "가" * 501},
            {"name": "두\n줄", "message": "안녕"},
            {"name": "손님", "message": "안녕\x00"},
            {"name": 123, "message": "안녕"},
            {"name": "손님", "message": "안녕", "id": 9},
            {"name": "손님"},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/entries", json=payload).status_code, 422)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 0)

    def test_maximum_lengths_are_accepted(self):
        self.assertEqual(self.create("가" * 20, "나" * 500).status_code, 201)
        response = self.client.post("/entries", data={"name": "가" * 20, "message": "나" * 500})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 2)

    def test_invalid_form_keeps_escaped_input_and_saves_nothing(self):
        response = self.client.post("/entries", data={"name": '<b>손님</b>', "message": "  "})
        self.assertEqual(response.status_code, 422)
        self.assertIn('role="alert"', response.text)
        self.assertIn("&lt;b&gt;손님&lt;/b&gt;", response.text)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 0)

    def test_html_injection_is_displayed_as_plain_text(self):
        self.create('<b>손님</b>', '</textarea><script>alert("x")</script>')
        html = self.client.get("/").text
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>손님</b>", html)

    def test_sql_characters_are_saved_as_text(self):
        message = "'); DROP TABLE entries; --"
        self.assertEqual(self.create(message=message).status_code, 201)
        self.assertEqual(self.create(message="다음 글").status_code, 201)
        entries = self.client.get("/api/entries").json()["entries"]
        self.assertEqual(entries[1]["message"], message)

    def test_pagination_is_latest_first_without_missing_entries(self):
        for index in range(12):
            self.assertEqual(self.create(message=f"글 {index}").status_code, 201)
        first = self.client.get("/api/entries").json()
        second = self.client.get("/api/entries?page=2").json()
        self.assertEqual((first["total"], first["total_pages"], len(first["entries"])), (12, 2, 10))
        self.assertEqual([entry["id"] for entry in first["entries"]], list(range(12, 2, -1)))
        self.assertEqual([entry["id"] for entry in second["entries"]], [2, 1])
        self.assertIn('href="/?page=2#messages"', self.client.get("/").text)
        self.assertEqual(self.client.get("/api/entries?page=99").json()["page"], 2)

    def test_query_and_path_errors(self):
        for path in ["/?page=0", "/api/entries?page=-1", "/api/entries?page=abc", "/api/entries?page=101", "/api/entries/0"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 422)
        self.assertEqual(self.client.get("/api/entries/999").status_code, 404)

    def test_database_survives_app_restart(self):
        entry = self.create(message="재시작 뒤에도 남는 글").json()
        with TestClient(main.app) as restarted:
            self.assertEqual(restarted.get(f'/api/entries/{entry["id"]}').json(), entry)

    def test_one_table_without_relations(self):
        with closing(sqlite3.connect(self.database)) as connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            self.assertEqual(tables, [("entries",)])
            self.assertEqual(connection.execute("PRAGMA foreign_key_list(entries)").fetchall(), [])

    def test_entry_limit_rejects_new_writes_and_keeps_old_data(self):
        with patch.object(main, "ENTRY_LIMIT", 1):
            self.assertEqual(self.create().status_code, 201)
            self.assertEqual(self.create().status_code, 409)
            response = self.client.post("/entries", data={"name": "손님", "message": "넘친 글"})
            self.assertEqual(response.status_code, 409)
            self.assertIn("방명록이 가득", response.text)
            self.assertEqual(self.client.get("/api/entries").json()["total"], 1)

    def test_simultaneous_writes_cannot_exceed_capacity(self):
        entry = main.EntryCreate(name="손님", message="동시 등록")

        def try_save(_):
            try:
                main.save_entry(entry)
                return 201
            except main.HTTPException as exc:
                return exc.status_code

        with patch.object(main, "ENTRY_LIMIT", 3), ThreadPoolExecutor(max_workers=6) as pool:
            codes = list(pool.map(try_save, range(8)))
        self.assertEqual(codes.count(201), 3)
        self.assertEqual(codes.count(409), 5)

    def test_cross_site_browser_writes_are_rejected(self):
        for headers in [{"Origin": "https://other.example"}, {"Sec-Fetch-Site": "cross-site"}, {"Origin": "null"}, {"Origin": "http://[invalid"}]:
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post("/entries", data={"name": "손님", "message": "안녕"}, headers=headers).status_code, 403)
                self.assertEqual(self.client.post("/api/entries", json={"name": "손님", "message": "안녕"}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 0)
        self.assertEqual(self.client.post("/entries", data={"name": "손님", "message": "안녕"}, headers={"Origin": "http://testserver"}).status_code, 200)

    def test_malformed_duplicate_and_oversized_forms_are_rejected(self):
        headers = {"content-type": "application/x-www-form-urlencoded"}
        for body in [b"name=a&name=b", b"name=a&message=b&extra=c", b"name=\xff&message=b", b"name=%FF&message=b", b"invalid"]:
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/entries", content=body, headers=headers).status_code, 400)
        self.assertEqual(self.client.post("/entries", content="x" * 8193, headers=headers).status_code, 413)
        self.assertEqual(self.client.post("/entries", json={"name": "손님", "message": "안녕"}).status_code, 415)
        self.assertEqual(self.client.get("/api/entries").json()["total"], 0)

    def test_health_and_openapi_are_available(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        self.assertIn("EntryCreate", schema["components"]["schemas"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
