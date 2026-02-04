# BMAD Wyckoff Development Server Restart Script (PowerShell)
# Stops all services (if running) and restarts them

$ErrorActionPreference = "Continue"

# Colors
function Write-Color($message, $color) {
    Write-Host $message -ForegroundColor $color
}

Write-Color "========================================" Cyan
Write-Color "  BMAD Wyckoff Service Restart         " Cyan
Write-Color "========================================" Cyan

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Store PIDs for cleanup
$script:BackendJob = $null
$script:FrontendJob = $null

# Cleanup function
function Stop-AllServices {
    Write-Color "`nShutting down services..." Yellow

    if ($script:BackendJob) {
        Stop-Job -Job $script:BackendJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:BackendJob -Force -ErrorAction SilentlyContinue
    }
    if ($script:FrontendJob) {
        Stop-Job -Job $script:FrontendJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:FrontendJob -Force -ErrorAction SilentlyContinue
    }

    Write-Color "Cleanup complete." Green
}

# Register cleanup on exit
Register-EngineEvent PowerShell.Exiting -Action { Stop-AllServices } | Out-Null

# ==========================================
# STOP PHASE
# ==========================================
Write-Color "`n[STOP] Stopping all services..." Yellow

# Stop any running uvicorn processes (backend)
Write-Color "  Stopping backend processes..." Yellow
$uvicornProcs = Get-Process -Name "python", "uvicorn" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*src.api.main*" }
if ($uvicornProcs) {
    $uvicornProcs | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Color "  ✓ Backend stopped" Green
} else {
    # Try to find by port
    $port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($port8000) {
        $port8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        Write-Color "  ✓ Backend stopped (by port)" Green
    } else {
        Write-Color "  - Backend was not running" Cyan
    }
}

# Stop any running vite/node processes (frontend)
Write-Color "  Stopping frontend processes..." Yellow
$port5173 = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
if ($port5173) {
    $port5173 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Color "  ✓ Frontend stopped" Green
} else {
    Write-Color "  - Frontend was not running" Cyan
}

# Stop Docker containers
Write-Color "  Stopping Docker containers..." Yellow
$containers = docker-compose ps -q 2>$null
if ($containers) {
    docker-compose down --remove-orphans
    Write-Color "  ✓ Docker containers stopped" Green
} else {
    Write-Color "  - Docker containers were not running" Cyan
}

# Small delay to ensure ports are released
Start-Sleep -Seconds 2

# ==========================================
# START PHASE
# ==========================================
Write-Color "`n[START] Starting all services..." Yellow

# Check if Docker is running
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Color "Error: Docker is not running. Please start Docker first." Red
    exit 1
}

# Start infrastructure services
Write-Color "  Starting infrastructure (PostgreSQL, Redis)..." Yellow
docker-compose up -d --force-recreate postgres redis

# Wait for services to be healthy
Write-Color "  Waiting for services to be ready..." Yellow
Start-Sleep -Seconds 3

# Check if postgres is ready
$maxRetries = 30
$retry = 0
while ($retry -lt $maxRetries) {
    $pgReady = docker-compose exec -T postgres pg_isready -U bmad -d bmad_wyckoff 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "  Waiting for PostgreSQL..."
    Start-Sleep -Seconds 2
    $retry++
}
Write-Color "  ✓ PostgreSQL is ready" Green

# Check if redis is ready
$retry = 0
while ($retry -lt $maxRetries) {
    $redisReady = docker-compose exec -T redis redis-cli ping 2>$null
    if ($redisReady -eq "PONG") { break }
    Write-Host "  Waiting for Redis..."
    Start-Sleep -Seconds 2
    $retry++
}
Write-Color "  ✓ Redis is ready" Green

# Start Backend (using run.py for Windows asyncio compatibility)
Write-Color "  Starting Backend API server..." Yellow
$script:BackendJob = Start-Job -ScriptBlock {
    Set-Location $using:ScriptDir\backend
    # IMPORTANT: Use run.py to set WindowsSelectorEventLoopPolicy before uvicorn starts
    # This is required for psycopg3 to work correctly on Windows
    poetry run python run.py --reload
}
Start-Sleep -Seconds 3
Write-Color "  ✓ Backend API started (Job: $($script:BackendJob.Id))" Green

# Start Frontend
Write-Color "  Starting Frontend dev server..." Yellow
$script:FrontendJob = Start-Job -ScriptBlock {
    Set-Location $using:ScriptDir\frontend
    npm run dev
}
Start-Sleep -Seconds 2
Write-Color "  ✓ Frontend started (Job: $($script:FrontendJob.Id))" Green

# ==========================================
# SUMMARY
# ==========================================
Write-Color "`n========================================" Green
Write-Color "  All services restarted successfully! " Green
Write-Color "========================================" Green
Write-Host "  Frontend:   " -NoNewline; Write-Color "http://localhost:5173" Green
Write-Host "  Backend:    " -NoNewline; Write-Color "http://localhost:8000" Green
Write-Host "  API Docs:   " -NoNewline; Write-Color "http://localhost:8000/docs" Green
Write-Host "  PostgreSQL: localhost:5432"
Write-Host "  Redis:      localhost:6379"
Write-Color "========================================" Green
Write-Host "`nPress Ctrl+C to stop all services.`n"

# Monitor jobs and show output
try {
    while ($true) {
        # Check if jobs are still running
        if ($script:BackendJob.State -eq "Failed") {
            Write-Color "Backend job failed!" Red
            Receive-Job -Job $script:BackendJob
        }
        if ($script:FrontendJob.State -eq "Failed") {
            Write-Color "Frontend job failed!" Red
            Receive-Job -Job $script:FrontendJob
        }

        Start-Sleep -Seconds 5
    }
} finally {
    Stop-AllServices
}
