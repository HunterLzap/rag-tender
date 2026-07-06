@echo off
title RAG-Tender Frontend
set "PATH=%PATH%;C:\Program Files\nodejs"
cd /d "%~dp0frontend"
echo [frontend] Working directory: %CD%
if not exist "node_modules" (
    echo [frontend] node_modules not found. Running npm install first...
    call npm install
    if errorlevel 1 (
        echo [frontend] npm install failed. Check the error above.
        pause
        exit /b 1
    )
)
echo [frontend] Starting http://localhost:5173 ...
echo.
call npm run dev -- --host 127.0.0.1 --port 5173
pause
