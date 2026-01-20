@echo off
REM BMAD Wyckoff Development Server Startup Script
REM Starts PostgreSQL, Redis, Backend API, and Frontend dev server

setlocal enabledelayedexpansion

echo ========================================
echo   BMAD Wyckoff Development Environment
echo ========================================

REM Get the directory where the script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not running. Please start Docker first.
    pause
    exit /b 1
)

REM Start infrastructure services
echo.
echo Starting infrastructure services (PostgreSQL, Redis)...
docker-compose up -d postgres redis

REM Wait for services to be ready
echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check postgres readiness (simplified check)
echo Waiting for PostgreSQL...
:wait_postgres
docker-compose exec -T postgres pg_isready -U bmad -d bmad_wyckoff >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_postgres
)
echo PostgreSQL is ready!

REM Check redis readiness
echo Waiting for Redis...
:wait_redis
docker-compose exec -T redis redis-cli ping >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_redis
)
echo Redis is ready!

echo.
echo ========================================
echo   Starting Backend and Frontend
echo ========================================
echo.
echo Starting Backend API on http://localhost:8000
echo Starting Frontend on http://localhost:5173
echo.
echo Press Ctrl+C in each window to stop.
echo ========================================
echo.

REM Start Backend in a new window
start "BMAD Backend" cmd /k "cd /d %SCRIPT_DIR%backend && poetry run uvicorn src.api.main:app --reload --port 8000"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start Frontend in a new window
start "BMAD Frontend" cmd /k "cd /d %SCRIPT_DIR%frontend && npm run dev"

echo.
echo ========================================
echo   All services started!
echo ========================================
echo   Frontend:   http://localhost:5173
echo   Backend:    http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo   PostgreSQL: localhost:5432
echo   Redis:      localhost:6379
echo ========================================
echo.
echo Close this window or press any key to continue...
echo (Backend and Frontend will keep running in their windows)
pause >nul
