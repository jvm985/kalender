#!/bin/bash
set -e

# Suppress monitor auto-restart while we deploy.
MONITOR_LOCK=/var/lock/monitor_apps.suppress
touch "$MONITOR_LOCK"
trap 'rm -f "$MONITOR_LOCK"' EXIT INT TERM
echo "🚀 Deploying joachim..."
git pull origin main 2>/dev/null || true
sudo docker compose up -d --build
sudo docker image prune -f
echo "✅ Deployment finished!"
