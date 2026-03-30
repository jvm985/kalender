#!/bin/bash

# Configuratie
REPO="git@github.com:jvm985/kalender.git"
SERVER="kalender.irishof.cloud"
APP_NAME="kalender-app"
APP_PORT=5050

echo "--- Stap 1: Git push naar GitHub ---"
if [ ! -d .git ]; then
    git init
    git remote add origin $REPO
fi

git add .
git commit -m "Full deploy: Web app, Docker, and Nginx config"
git push origin main || git push origin master

echo "--- Stap 2: Deployment naar server ($SERVER) ---"
ssh $SERVER << EOF
    # Project directory aanmaken
    mkdir -p ~/apps/kalender
    cd ~/apps/kalender

    # Code ophalen
    if [ ! -d .git ]; then
        git clone $REPO .
    else
        git pull origin main || git pull origin master
    fi

    # Docker image bouwen en container herstarten
    sudo docker build -t $APP_NAME .
    sudo docker stop $APP_NAME || true
    sudo docker rm $APP_NAME || true
    
    # Run container op poort 5050
    sudo docker run -d \
        --name $APP_NAME \
        --restart always \
        -p $APP_PORT:5000 \
        $APP_NAME

    # Nginx configuratie instellen
    sudo cp kalender.irishof.cloud.conf /etc/nginx/sites-available/kalender.irishof.cloud
    sudo ln -sf /etc/nginx/sites-available/kalender.irishof.cloud /etc/nginx/sites-enabled/kalender.irishof.cloud
    
    # Nginx testen en herladen
    sudo nginx -t && sudo systemctl reload nginx

    echo "Deployment voltooid op $SERVER"
    echo "App draait op http://kalender.irishof.cloud"
EOF
