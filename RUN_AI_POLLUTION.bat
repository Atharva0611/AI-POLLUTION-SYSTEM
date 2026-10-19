@echo off
title AI Pollution Environmental Intelligence System
cd /d "C:\final year project\AI-POLLUTION-SYSTEM"

echo ============================================================
echo        AI POLLUTION ENVIRONMENTAL INTELLIGENCE
echo ============================================================
echo.
echo Starting system...
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m backend.run_final_agent

echo.
echo ============================================================
echo System stopped.
echo ============================================================
pause
