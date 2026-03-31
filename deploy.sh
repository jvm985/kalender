#!/bin/bash
# Snel script voor routine updates

APP_NAME="kalender-app"
APP_PORT=5050

echo "--- 🔄 Code ophalen ---"
git fetch origin
git reset --hard origin/master

echo "--- 🏗️ Docker image bouwen ---"
sudo docker build -t $APP_NAME .

echo "--- 🚀 Container herstarten ---"
sudo docker stop $APP_NAME || true
sudo docker rm $APP_NAME || true

sudo docker run -d \
    --name $APP_NAME \
    --restart always \
    -p $APP_PORT:5000 \
    -v kalender_data:/data \
    -e GOOGLE_CLIENT_SECRET="$GOOGLE_CLIENT_SECRET" \
    $APP_NAME

echo "✅ Update voltooid!"
