#!/bin/bash
# Setup Let's Encrypt SSL certificates
# Requires: certbot installed on host
# Usage: ./scripts/setup-letsencrypt.sh yourdomain.com
set -e

DOMAIN=${1:?"Usage: $0 yourdomain.com"}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_DIR/ssl"

certbot certonly --standalone \
  -d "$DOMAIN" \
  --non-interactive \
  --agree-tos \
  --email "admin@$DOMAIN"

# Copy certs to project ssl directory
mkdir -p "$SSL_DIR"
cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$SSL_DIR/"
cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$SSL_DIR/"

echo "Certificates copied to $SSL_DIR/"
echo "Add certbot renewal to crontab:"
echo "0 0 1 * * certbot renew --deploy-hook 'docker compose -f docker-compose.prod.yml restart frontend'"
