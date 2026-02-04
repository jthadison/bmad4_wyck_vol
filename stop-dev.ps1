# BMAD Wyckoff Development Server Stop Script (PowerShell)
# Stops all running services

$ErrorActionPreference = "Continue"

# Colors
function Write-Color($message, $color) {
    Write-Host $message -ForegroundColor $color
}

Write-Color "========================================" Cyan
Write-Color "  BMAD Wyckoff Service Stop            " Cyan
Write-Color "========================================" Cyan

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Color "`nStopping all services..." Yellow

# Stop any running uvicorn processes (backend)
Write-Color "  Stopping backend processes..." Yellow
$port8000 = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($port8000) {
    $port8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Write-Color "  ✓ Backend stopped" Green
} else {
    Write-Color "  - Backend was not running" Cyan
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
    docker-compose down
    Write-Color "  ✓ Docker containers stopped" Green
} else {
    Write-Color "  - Docker containers were not running" Cyan
}

Write-Color "`n========================================" Green
Write-Color "  All services stopped.                " Green
Write-Color "========================================" Green
