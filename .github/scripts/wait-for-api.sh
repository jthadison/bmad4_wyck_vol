#!/bin/bash
# Robust API health check with exponential backoff
# Usage: wait-for-api.sh [max_attempts] [base_url] [health_endpoint]

MAX_ATTEMPTS=${1:-30}
BASE_URL=${2:-"http://localhost:8000"}
HEALTH_ENDPOINT=${3:-"/api/health"}

echo "🔍 Waiting for API at ${BASE_URL}${HEALTH_ENDPOINT}"

for i in $(seq 1 $MAX_ATTEMPTS); do
  if curl -sf "${BASE_URL}${HEALTH_ENDPOINT}" > /dev/null 2>&1; then
    echo "✅ API ready after $i attempts"
    exit 0
  fi

  # Exponential backoff: 2s for first 5 attempts, then 5s
  SLEEP_TIME=$((i < 5 ? 2 : 5))
  echo "⏳ Attempt $i/$MAX_ATTEMPTS - waiting ${SLEEP_TIME}s..."
  sleep $SLEEP_TIME
done

echo "❌ API failed to start after $MAX_ATTEMPTS attempts"
exit 1
