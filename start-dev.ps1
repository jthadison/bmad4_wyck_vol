# BMAD Wyckoff Development Server Startup Script
# Starts PostgreSQL, Redis, Backend API, and Frontend dev server

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Green
Write-Host "  BMAD Wyckoff Development Environment " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Get the directory where the script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "Error: Docker is not running. Please start Docker first." -ForegroundColor Red
    exit 1
}

# Start infrastructure services
Write-Host "`nStarting infrastructure services (PostgreSQL, Redis)..." -ForegroundColor Yellow
docker-compose up -d postgres redis

# Wait for services to be ready
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check postgres readiness
Write-Host "Waiting for PostgreSQL..." -ForegroundColor Yellow
do {
    $result = docker-compose exec -T postgres pg_isready -U bmad -d bmad_wyckoff 2>&1
    if ($LASTEXITCODE -ne 0) {
        Start-Sleep -Seconds 2
    }
} while ($LASTEXITCODE -ne 0)
Write-Host "PostgreSQL is ready!" -ForegroundColor Green

# Check redis readiness
Write-Host "Waiting for Redis..." -ForegroundColor Yellow
do {
    $result = docker-compose exec -T redis redis-cli ping 2>&1
    if ($LASTEXITCODE -ne 0) {
        Start-Sleep -Seconds 2
    }
} while ($LASTEXITCODE -ne 0)
Write-Host "Redis is ready!" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Starting Backend and Frontend" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Start Backend in a new window
Write-Host "`nStarting Backend API on http://localhost:8000" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir\backend'; poetry run uvicorn src.api.main:app --reload --port 8000"

# Wait a moment for backend to start
Start-Sleep -Seconds 3

# Start Frontend in a new window
Write-Host "Starting Frontend on http://localhost:5173" -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$ScriptDir\frontend'; npm run dev"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Frontend:   " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Cyan
Write-Host "  Backend:    " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:   " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  PostgreSQL: localhost:5432"
Write-Host "  Redis:      localhost:6379"
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nBackend and Frontend are running in separate windows."
Write-Host "Close those windows to stop the services."
