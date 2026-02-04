#!/bin/bash
# BMAD Wyckoff Development Server Startup Script
# Starts PostgreSQL, Redis, Backend API, and Frontend dev server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  BMAD Wyckoff Development Environment ${NC}"
echo -e "${GREEN}========================================${NC}"

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

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Start infrastructure services
echo -e "\n${YELLOW}Starting infrastructure services (PostgreSQL, Redis)...${NC}"
docker-compose up -d postgres redis

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 5

# Check if postgres is ready
until docker-compose exec -T postgres pg_isready -U bmad -d bmad_wyckoff > /dev/null 2>&1; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done
echo -e "${GREEN}PostgreSQL is ready!${NC}"

# Check if redis is ready
until docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; do
    echo "Waiting for Redis..."
    sleep 2
done
echo -e "${GREEN}Redis is ready!${NC}"

# Start Backend (using run.py for proper asyncio event loop on all platforms)
echo -e "\n${YELLOW}Starting Backend API server...${NC}"
cd backend
# IMPORTANT: Use run.py to ensure correct event loop policy (required for psycopg3 on Windows)
poetry run python run.py --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3
echo -e "${GREEN}Backend API starting on http://localhost:8000${NC}"
echo -e "${GREEN}API Docs available at http://localhost:8000/docs${NC}"

# Start Frontend
echo -e "\n${YELLOW}Starting Frontend dev server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  All services started!                 ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Frontend:  ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend:   ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:  ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  PostgreSQL: localhost:5432"
echo -e "  Redis:      localhost:6379"
echo -e "${GREEN}========================================${NC}"
echo -e "\nPress Ctrl+C to stop all services.\n"

# Wait for any process to exit
wait
