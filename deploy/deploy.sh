#!/bin/bash
# Deploy to OVH VPS. Run from local machine.
# Usage: ./deploy/deploy.sh user@your-vps-ip

set -euo pipefail

REMOTE=${1:-"ubuntu@your-vps-ip"}
REMOTE_DIR="/home/ubuntu/polymarket-btc-bot"

echo "Deploying to $REMOTE:$REMOTE_DIR"

rsync -avz --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.env' --exclude='logs/' \
    . "$REMOTE:$REMOTE_DIR"

ssh "$REMOTE" << 'EOF'
cd /home/ubuntu/polymarket-btc-bot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip uv
.venv/bin/uv pip install -e .
sudo cp deploy/systemd/pm-logger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pm-logger
echo "Deploy complete. Run: sudo systemctl start pm-logger"
EOF
