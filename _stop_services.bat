@echo off
title RAG-Tender Stop Services
setlocal

echo ========================================
echo   RAG-Tender Assistant stop services
echo ========================================
echo.

echo [1/3] Stopping ports 8000 and 5173...
for %%p in (8000 5173) do (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%p " ^| findstr "LISTENING"') do (
        echo     Stop PID %%a on port %%p
        taskkill /PID %%a /T /F >nul 2>&1
    )
)

echo [2/3] Stopping leftover project dev processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $roots=@('RAG-Tender-Assistant-open-source','RAG-Tender Assistant'); Get-CimInstance Win32_Process | Where-Object { $cmd=$_.CommandLine; $cmd -and (($cmd -match 'vite.*--port 5173') -or ($cmd -match 'npm.*run dev.*--port 5173') -or ($cmd -match '\\run\.py\b') -or ($cmd -match 'node_modules.*vite') -or ($cmd -match 'node_modules.*esbuild')) -and ($roots | Where-Object { $cmd -like ('*' + $_ + '*') }) } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }"

echo [3/3] Verifying ports...
set "ANY_LEFT=0"
for %%p in (8000 5173) do (
    netstat -ano | findstr ":%%p " | findstr "LISTENING" >nul 2>&1
    if errorlevel 1 (
        echo     [OK] Port %%p is free
    ) else (
        echo     [FAIL] Port %%p is still in use
        set "ANY_LEFT=1"
    )
)

echo.
if "%ANY_LEFT%"=="0" (
    echo All services stopped.
) else (
    echo Some services are still running. Check Task Manager if needed.
)
if /i not "%~1"=="nopause" pause
