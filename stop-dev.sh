#!/bin/bash
# BMAD Wyckoff Development Server Stop Script
# Stops all running services

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================${NC}"
echo -e "${CYAN}  BMAD Wyckoff Service Stop            ${NC}"
echo -e "${CYAN}========================================${NC}"

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${YELLOW}Stopping all services...${NC}"

# Stop any running uvicorn processes (backend)
echo -e "${YELLOW}  Stopping backend processes...${NC}"
pkill -f "uvicorn src.api.main:app" 2>/dev/null && echo -e "${GREEN}  ✓ Backend stopped${NC}" || echo -e "${CYAN}  - Backend was not running${NC}"

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

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  All services stopped.                ${NC}"
echo -e "${GREEN}========================================${NC}"
