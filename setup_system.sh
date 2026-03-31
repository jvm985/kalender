#!/bin/bash
# Script voor EENMALIGE setup van Nginx en SSL (Let's Encrypt) op de server

SERVER="kalender.irishof.cloud"

ssh $SERVER << EOF
    cd ~/apps/kalender

    # Nginx configuratie instellen
    echo "--- 🛠️ Nginx instellen ---"
    sudo cp kalender.irishof.cloud.conf /etc/nginx/sites-available/kalender.irishof.cloud
    sudo ln -sf /etc/nginx/sites-available/kalender.irishof.cloud /etc/nginx/sites-enabled/kalender.irishof.cloud
    
    # Nginx testen en herladen
    sudo nginx -t && sudo systemctl reload nginx

    # Let's Encrypt SSL aanvragen (indien nog niet aanwezig)
    if [ ! -d "/etc/letsencrypt/live/$SERVER" ]; then
        echo "--- 🔐 Aanvragen van SSL certificaat ---"
        sudo apt-get update && sudo apt-get install -y certbot python3-certbot-nginx
        sudo certbot --nginx -d $SERVER --non-interactive --agree-tos -m jvm985@gmail.com --redirect
    fi

    echo "✅ Systeem setup voltooid!"
EOF
