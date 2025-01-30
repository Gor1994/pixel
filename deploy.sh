#!/bin/bash

# Exit on error
set -e

# Hardcoded VPS details
VPS_IP="195.133.146.186"
USER="root"
PASSWORD="dZ5YG8iBRu"

# Remote directories
REMOTE_JS_DIR="/var/www/rbiz.pro/frontend/static/js/"
REMOTE_CSS_DIR="/var/www/rbiz.pro/frontend/static/css/"
REMOTE_HTML_DIR="/var/www/rbiz.pro/frontend"
REMOTE_APP_DIR="/var/www/rbiz.pro/backend/app"

# Local build directory
BUILD_DIR="./build"
APP_FILES=("./backend/app.py" "./backend/telegram_bot.py" "./backend/.env") # Files to be deployed to the backend

# Ensure dependencies are installed and build the project
echo "Building the frontend..."
npm install
npm run build

# Clean remote frontend directories
echo "Cleaning remote frontend directories..."
sshpass -p "$PASSWORD" ssh $USER@$VPS_IP "rm -rf $REMOTE_JS_DIR* $REMOTE_CSS_DIR*"

# Upload frontend files
echo "Uploading frontend files to VPS..."

# Upload JS files
sshpass -p "$PASSWORD" scp -r $BUILD_DIR/static/js/* $USER@$VPS_IP:$REMOTE_JS_DIR

# Upload CSS files
sshpass -p "$PASSWORD" scp -r $BUILD_DIR/static/css/* $USER@$VPS_IP:$REMOTE_CSS_DIR

# Upload HTML files
sshpass -p "$PASSWORD" scp -r $BUILD_DIR/*.html $USER@$VPS_IP:$REMOTE_HTML_DIR

# Deploy backend files
echo "Deploying backend files to VPS..."
sshpass -p "$PASSWORD" ssh $USER@$VPS_IP "mkdir -p $REMOTE_APP_DIR"

# Upload app.py and telegram_bot.py
for FILE in "${APP_FILES[@]}"; do
    sshpass -p "$PASSWORD" scp $FILE $USER@$VPS_IP:$REMOTE_APP_DIR
done

# Restart backend services if necessary (optional)
# echo "Restarting backend services..."
# sshpass -p "$PASSWORD" ssh $USER@$VPS_IP "systemctl restart your-backend-service"

echo "Deployment completed successfully."
