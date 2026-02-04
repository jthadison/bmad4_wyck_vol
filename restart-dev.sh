#!/bin/bash
# BMAD Wyckoff Development Server Restart Script
# Stops all services (if running) and restarts them

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  BMAD Wyckoff Service Restart         ${NC}"
echo -e "${CYAN}========================================${NC}"

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    # Kill background processes
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Cleanup complete.${NC}"
}

trap cleanup EXIT

# ==========================================
# STOP PHASE
# ==========================================
echo -e "\n${YELLOW}[STOP] Stopping all services...${NC}"

# Stop any running uvicorn processes (backend)
echo -e "${YELLOW}  Stopping backend processes...${NC}"
pkill -f "uvicorn.*src.api.main" 2>/dev/null && echo -e "${GREEN}  ✓ Backend stopped${NC}" || echo -e "${CYAN}  - Backend was not running${NC}"

# Stop any running vite processes (frontend)
echo -e "${YELLOW}  Stopping frontend processes...${NC}"
pkill -f "vite" 2>/dev/null && echo -e "${GREEN}  ✓ Frontend stopped${NC}" || echo -e "${CYAN}  - Frontend was not running${NC}"

# Stop Docker containers
echo -e "${YELLOW}  Stopping Docker containers...${NC}"
if docker-compose ps -q 2>/dev/null | grep -q .; then
    docker-compose down
    echo -e "${GREEN}  ✓ Docker containers stopped${NC}"
else
    echo -e "${CYAN}  - Docker containers were not running${NC}"
fi

# Small delay to ensure ports are released
sleep 2

# ==========================================
# START PHASE
# ==========================================
echo -e "\n${YELLOW}[START] Starting all services...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Start infrastructure services
echo -e "${YELLOW}  Starting infrastructure (PostgreSQL, Redis)...${NC}"
docker-compose up -d postgres redis

# Wait for services to be healthy
echo -e "${YELLOW}  Waiting for services to be ready...${NC}"
sleep 3

# Check if postgres is ready
until docker-compose exec -T postgres pg_isready -U bmad -d bmad_wyckoff > /dev/null 2>&1; do
    echo "  Waiting for PostgreSQL..."
    sleep 2
done
echo -e "${GREEN}  ✓ PostgreSQL is ready${NC}"

# Check if redis is ready
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "  Waiting for Redis..."
    sleep 2
done
echo -e "${GREEN}  ✓ Redis is ready${NC}"

# Start Backend (using run.py for proper asyncio event loop on all platforms)
echo -e "${YELLOW}  Starting Backend API server...${NC}"
cd backend
# IMPORTANT: Use run.py to ensure correct event loop policy (required for psycopg3 on Windows)
poetry run python run.py --reload &
BACKEND_PID=$!
cd ..
sleep 3
echo -e "${GREEN}  ✓ Backend API started (PID: $BACKEND_PID)${NC}"

# Start Frontend
echo -e "${YELLOW}  Starting Frontend dev server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
sleep 2
echo -e "${GREEN}  ✓ Frontend started (PID: $FRONTEND_PID)${NC}"

# ==========================================
# SUMMARY
# ==========================================
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  All services restarted successfully! ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Frontend:   ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend:    ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:   ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  PostgreSQL: localhost:5432"
echo -e "  Redis:      localhost:6379"
echo -e "${GREEN}========================================${NC}"
echo -e "\nPress Ctrl+C to stop all services.\n"

# Wait for any process to exit
wait
