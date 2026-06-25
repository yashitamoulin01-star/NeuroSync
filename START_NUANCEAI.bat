@echo off
title NuanceAI Launcher
color 0B

echo.
echo  =====================================================
echo   NuanceAI  ^|  NeuroSync Platform  ^|  Hackathon Demo
echo  =====================================================
echo.

:: Kill anything stale on our ports
echo  Clearing stale processes...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":3000 "') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: Clear Next.js cache to avoid corrupted module errors
echo  Clearing Next.js cache...
if exist "D:\MBD\frontend\.next" rd /s /q "D:\MBD\frontend\.next"

echo.
echo  [1/2] Starting FastAPI Backend (port 8000)...
start "NuanceAI Backend" cmd /k "cd /d D:\MBD && D:\MBD\.venv\Scripts\activate.bat && python -m uvicorn backend.main:app --port 8000 --host 127.0.0.1"

timeout /t 3 /nobreak >nul

echo  [2/2] Starting Next.js Frontend (port 3000)...
start "NuanceAI Frontend" cmd /k "cd /d D:\MBD\frontend && npm run dev"

echo.
echo  Waiting for servers to start (20 seconds)...
echo  Both console windows are running in the background.
echo.

timeout /t 20 /nobreak

echo  Opening browser...
start http://localhost:3000

echo.
echo  =====================================================
echo   App:    http://localhost:3000
echo   API:    http://localhost:8000/docs
echo   Demo:   http://localhost:3000/session/demo/results
echo  =====================================================
echo.
echo  TIP: Close the "NuanceAI Backend" and "NuanceAI Frontend"
echo  windows to stop the servers.
echo.
pause
