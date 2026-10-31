@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

set "PYTHONPATH=%ROOT_DIR%backend"
set "DATABASE_URL_APP=sqlite:///%ROOT_DIR%backend\sealtrail.db"
set "DATABASE_URL_OWNER=sqlite:///%ROOT_DIR%backend\sealtrail.db"

if "%~1"=="" (
    backend\.venv\Scripts\python.exe backend\scripts\tamper_demo.py --help
    goto :eof
)

backend\.venv\Scripts\python.exe backend\scripts\tamper_demo.py %*

