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
    
    # Gebruik het snelle deploy script
    chmod +x deploy.sh
    ./deploy.sh

    echo "Deployment voltooid op $SERVER"
    echo "App draait op https://kalender.irishof.cloud"
EOF
