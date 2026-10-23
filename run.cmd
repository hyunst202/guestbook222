@echo off
setlocal
set "GUESTBOOK_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%GUESTBOOK_PYTHON%" set "GUESTBOOK_PYTHON=%~dp0..\DAY7\sync_async_shop\.runtime\python\python.exe"
if not exist "%GUESTBOOK_PYTHON%" (
    echo Python was not found. Please follow the setup steps in README.md.
    exit /b 1
)
set "GUESTBOOK_PORT=8008"
if not "%~1"=="" set "GUESTBOOK_PORT=%~1"
echo Guestbook: http://127.0.0.1:%GUESTBOOK_PORT%  [Ctrl+C to stop]
"%GUESTBOOK_PYTHON%" -m uvicorn main:app --app-dir "%~dp0." --host 127.0.0.1 --port "%GUESTBOOK_PORT%" --workers 1
exit /b %errorlevel%
