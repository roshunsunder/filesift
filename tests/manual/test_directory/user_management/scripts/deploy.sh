#!/bin/bash

# Deployment script for production environment
set -e

echo "Starting deployment..."

# Configuration
APP_NAME="user-management-app"
DEPLOY_DIR="/var/www/${APP_NAME}"
BACKUP_DIR="/var/backups/${APP_NAME}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
echo "Creating backup..."
mkdir -p "${BACKUP_DIR}"
if [ -d "${DEPLOY_DIR}" ]; then
    tar -czf "${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz" -C "${DEPLOY_DIR}" .
    echo "Backup created: ${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz"
fi

# Pull latest changes
echo "Pulling latest changes..."
cd "${DEPLOY_DIR}"
git pull origin main

# Backend deployment
echo "Deploying backend..."
cd backend
pip install -r requirements.txt
python -m pytest

# Run database migrations
echo "Running database migrations..."
psql $DATABASE_URL -f ../database/migrations/001_create_users_table.sql || true
psql $DATABASE_URL -f ../database/migrations/002_create_posts_table.sql || true

# Frontend deployment
echo "Deploying frontend..."
cd ../frontend
npm install
npm run build

# Restart services
echo "Restarting services..."
sudo systemctl restart ${APP_NAME}-backend
sudo systemctl restart nginx

# Health check
echo "Performing health check..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "Deployment successful!"
    echo "Application is healthy and running."
else
    echo "Deployment failed! Health check returned: $HTTP_STATUS"
    echo "Rolling back..."
    tar -xzf "${BACKUP_DIR}/backup_${TIMESTAMP}.tar.gz" -C "${DEPLOY_DIR}"
    sudo systemctl restart ${APP_NAME}-backend
    sudo systemctl restart nginx
    exit 1
fi

# Cleanup old backups (keep last 5)
echo "Cleaning up old backups..."
cd "${BACKUP_DIR}"
ls -t | tail -n +6 | xargs -r rm

echo "Deployment completed successfully at $(date)"
