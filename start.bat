@echo off
title RAG-Tender Assistant
setlocal
set "ROOT=%~dp0"

echo ========================================
echo   RAG-Tender Assistant startup
echo ========================================
echo.

echo [0/4] Stopping old local services...
call "%ROOT%_stop_services.bat" nopause

echo.
echo [1/4] Starting backend: http://127.0.0.1:8000
start "RAG-Tender Backend" "%ROOT%_start_backend.bat"

echo [2/4] Starting frontend: http://localhost:5173
start "RAG-Tender Frontend" "%ROOT%_start_frontend.bat"

echo [3/4] Waiting for ports 8000 and 5173...
set /a tries=0
:wait_loop
set /a tries+=1
set "BACKEND_READY=0"
set "FRONTEND_READY=0"
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set "BACKEND_READY=1"
netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 set "FRONTEND_READY=1"
if "%BACKEND_READY%"=="1" if "%FRONTEND_READY%"=="1" goto ready
if %tries% geq 60 goto not_ready
timeout /t 2 /nobreak >nul
goto wait_loop

:ready
echo [4/4] Services are ready.
start http://localhost:5173
goto done

:not_ready
echo [WARN] Services did not become ready within 120 seconds.
echo        Check the backend/frontend windows for errors.
echo        If this is the first run, frontend dependency installation may still be running.

goto done

:done
echo.
echo ========================================
echo   Frontend: http://localhost:5173
echo   API docs: http://127.0.0.1:8000/docs
echo ========================================
echo.
echo Keep the backend/frontend windows open while using the app.
echo Run _stop_services.bat to stop both services.
pause >nul
