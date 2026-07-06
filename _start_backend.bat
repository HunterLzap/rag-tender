@echo off
title RAG-Tender Backend
cd /d "%~dp0backend"
echo [backend] Working directory: %CD%
echo [backend] Starting http://127.0.0.1:8000 ...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

pause
