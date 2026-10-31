@echo off
setlocal enabledelayedexpansion

title SealTrail - Digital Evidence Chain-of-Custody

echo =====================================================================
echo  SealTrail - "Prove it hasn't changed."
echo  Starting local development servers...
echo =====================================================================
echo.

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

:: Set local fallback database and python path if running on host without Docker
if not exist "backend\sealtrail.db" (
    echo [!] sealtrail.db not found in backend folder.
)

set "PYTHONPATH=%ROOT_DIR%backend"
set "DATABASE_URL_APP=sqlite:///%ROOT_DIR%backend\sealtrail.db"
set "DATABASE_URL_OWNER=sqlite:///%ROOT_DIR%backend\sealtrail.db"

:: 1. Launch FastAPI Backend
echo [*] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "SealTrail Backend (FastAPI)" cmd /k "cd /d %ROOT_DIR% && set PYTHONPATH=%ROOT_DIR%backend && set DATABASE_URL_APP=sqlite:///%ROOT_DIR%backend\sealtrail.db && set DATABASE_URL_OWNER=sqlite:///%ROOT_DIR%backend\sealtrail.db && backend\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000"

:: Brief wait for backend startup
timeout /t 3 /nobreak > nul

:: 2. Launch React Frontend (Vite)
echo [*] Launching React Frontend on http://localhost:5173 ...
start "SealTrail Frontend (Vite)" cmd /k "cd /d %ROOT_DIR%frontend && npm run dev"

:: Brief wait for frontend startup
timeout /t 3 /nobreak > nul

:: 3. Automatically open default browser to SealTrail
echo [*] Opening browser to http://localhost:5173 ...
start http://localhost:5173

echo.
echo =====================================================================
echo  SealTrail is now running!
echo  - Frontend Web UI:  http://localhost:5173
echo  - Backend API:      http://127.0.0.1:8000
echo  - API Docs:         http://127.0.0.1:8000/docs
echo.
echo  Demo Accounts (Password: Demo#Seal2026!):
echo  - Supervisor:   supervisor1@sealtrail.local
echo  - Investigator: investigator1@sealtrail.local
echo  - Custodian:    custodian1@sealtrail.local
echo  - Auditor:      auditor1@sealtrail.local
echo.
echo  Press any key or close this window when done.
echo =====================================================================
pause

