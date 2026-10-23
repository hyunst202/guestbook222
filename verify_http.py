"""실제 Uvicorn 서버의 등록·새로고침·프로세스 재시작을 검사합니다."""

from contextlib import closing
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


BASE_DIR = Path(__file__).resolve().parent


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def wait_for_server(process, base_url):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("검증 서버가 종료되었습니다. verification/server.log를 확인하세요.")
        try:
            with urlopen(base_url + "/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError("서버가 시작되었는지 확인할 수 없습니다.")


def stop_server(process):
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    verification_dir = BASE_DIR / "verification"
    verification_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="http-", dir=verification_dir) as temp_dir:
        environment = os.environ.copy()
        environment["GUESTBOOK_DB_PATH"] = str(Path(temp_dir) / "smoke.db")
        # 사용하지 않는 로컬 포트를 운영체제에서 배정받습니다.
        with closing(socket.socket()) as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        command = [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", str(BASE_DIR),
                   "--host", "127.0.0.1", "--port", str(port), "--workers", "1"]
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (verification_dir / "server.log").open("w", encoding="utf-8") as log:
            def start():
                return subprocess.Popen(command, cwd=BASE_DIR, env=environment, stdout=log,
                                        stderr=log, creationflags=creationflags)

            process = start()
            try:
                wait_for_server(process, base_url)
                with urlopen(base_url + "/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                    assert response.status == 200 and 'lang="ko"' in html
                    assert "<script" not in html.lower()
                with urlopen(base_url + "/static/style.css", timeout=5) as response:
                    assert response.status == 200

                form = urlencode({"name": "실제 HTTP 검사", "message": "서버를 다시 시작해도 남는 한마디"}).encode()
                request = Request(base_url + "/entries", data=form,
                                  headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": base_url})
                try:
                    build_opener(NoRedirect).open(request, timeout=5)
                    raise AssertionError("POST는 303 응답으로 목록으로 이동해야 합니다.")
                except HTTPError as response:
                    assert response.code == 303
                    assert response.headers["Location"] == "/?saved=1#messages"
                    response.close()
                for _ in range(2):
                    with urlopen(base_url + "/?saved=1", timeout=5) as response:
                        assert "안부가 잘 도착했어요" in response.read().decode("utf-8")
                with urlopen(base_url + "/api/entries", timeout=5) as response:
                    before = json.load(response)
                    assert before["total"] == 1

                stop_server(process)
                process = start()
                wait_for_server(process, base_url)
                with urlopen(base_url + "/api/entries", timeout=5) as response:
                    assert json.load(response) == before
                print("PASS: real HTTP home, CSS, form POST 303, refresh, API, process restart, SQLite persistence")
                print("Browser visual inspection: not performed (no connected browser).")
            finally:
                if process.poll() is None:
                    stop_server(process)


if __name__ == "__main__":
    main()
