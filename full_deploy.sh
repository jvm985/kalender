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

# Zorg dat we op master zitten
git checkout -b master || git checkout master

git add .
git commit -m "Full deploy: Web app, Docker, and Nginx config"
git push origin master --force

echo "--- Stap 2: Deployment naar server ($SERVER) ---"
ssh $SERVER << EOF
    # Project directory aanmaken
    mkdir -p ~/apps/kalender
    cd ~/apps/kalender

    # Code ophalen
    if [ ! -d .git ]; then
        git clone $REPO .
    fi
    
    git fetch origin
    git reset --hard origin/master

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

    # Let's Encrypt SSL aanvragen (indien nog niet aanwezig)
    if [ ! -d "/etc/letsencrypt/live/kalender.irishof.cloud" ]; then
        echo "--- Aanvragen van SSL certificaat via Let's Encrypt ---"
        sudo apt-get update && sudo apt-get install -y certbot python3-certbot-nginx
        sudo certbot --nginx -d kalender.irishof.cloud --non-interactive --agree-tos -m jvm985@gmail.com --redirect
    fi

    echo "Deployment voltooid op $SERVER"
    echo "App draait op https://kalender.irishof.cloud"
EOF
