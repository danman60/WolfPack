#!/usr/bin/env bash
# WolfPack Intel Service — One-shot VPS setup
# Usage: cd /path/to/WolfPack && bash intel/setup-vps.sh
#
# Prerequisites: Ubuntu/Debian droplet with root or sudo access
# Tested on: Ubuntu 22.04 / 24.04

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INTEL_DIR="$REPO_DIR/intel"
SERVICE_USER="wolfpack"
DOMAIN=""  # Set below or via arg

# ── Parse args ──
if [ "${1:-}" != "" ]; then
    DOMAIN="$1"
fi

echo "========================================="
echo "  WolfPack Intel — VPS Setup"
echo "========================================="
echo "Repo:   $REPO_DIR"
echo "Intel:  $INTEL_DIR"
echo ""

# ── 1. System deps ──
echo "[1/7] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx ufw > /dev/null 2>&1 || {
    # If python3.11 not available, try default python3
    sudo apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx ufw > /dev/null 2>&1
}
echo "  Done."

# ── 2. Create service user ──
echo "[2/7] Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    sudo useradd -r -m -s /bin/bash "$SERVICE_USER"
    echo "  Created user: $SERVICE_USER"
else
    echo "  User $SERVICE_USER already exists."
fi

# ── 3. Python venv + deps ──
echo "[3/7] Setting up Python environment..."
cd "$INTEL_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
echo "  Installed $(pip list --format=columns | wc -l) packages."

# ── 4. .env file ──
echo "[4/7] Checking .env..."
if [ ! -f "$INTEL_DIR/.env" ]; then
    cp "$INTEL_DIR/.env.example" "$INTEL_DIR/.env"
    echo ""
    echo "  *** IMPORTANT: Edit $INTEL_DIR/.env with your API keys ***"
    echo "  Required: SUPABASE_URL, SUPABASE_KEY"
    echo "  Optional: ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, HYPERLIQUID_WALLET"
    echo ""
else
    echo "  .env already exists."
fi

# ── 5. Systemd service ──
echo "[5/7] Creating systemd service..."
sudo tee /etc/systemd/system/wolfpack-intel.service > /dev/null <<UNIT
[Unit]
Description=WolfPack Intel Service
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INTEL_DIR
Environment=PATH=$INTEL_DIR/.venv/bin:/usr/bin
EnvironmentFile=$INTEL_DIR/.env
ExecStart=$INTEL_DIR/.venv/bin/uvicorn wolfpack.api:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# Give service user read access
sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INTEL_DIR/.venv"
sudo chmod 600 "$INTEL_DIR/.env"
sudo chown "$SERVICE_USER" "$INTEL_DIR/.env"

sudo systemctl daemon-reload
sudo systemctl enable wolfpack-intel
echo "  Service created and enabled."

# ── 6. Nginx reverse proxy ──
echo "[6/7] Configuring nginx..."
NGINX_CONF="/etc/nginx/sites-available/wolfpack-intel"

if [ -n "$DOMAIN" ]; then
    SERVER_NAME="$DOMAIN"
else
    SERVER_NAME="_"
    echo "  No domain provided. Using IP-based config."
    echo "  To add a domain later: bash intel/setup-vps.sh yourdomain.com"
fi

sudo tee "$NGINX_CONF" > /dev/null <<NGINX
server {
    listen 80;
    server_name $SERVER_NAME;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }
}
NGINX

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/wolfpack-intel
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
echo "  Nginx configured."

# ── 7. Firewall ──
echo "[7/7] Configuring firewall..."
sudo ufw allow OpenSSH > /dev/null 2>&1
sudo ufw allow 'Nginx Full' > /dev/null 2>&1
sudo ufw --force enable > /dev/null 2>&1
echo "  Firewall: SSH + HTTP/HTTPS allowed."

# ── SSL (if domain provided) ──
if [ -n "$DOMAIN" ]; then
    echo ""
    echo "[SSL] Requesting Let's Encrypt certificate..."
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email || {
        echo "  SSL failed — run manually: sudo certbot --nginx -d $DOMAIN"
    }
fi

# ── Start ──
echo ""
echo "========================================="
echo "  Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env:    nano $INTEL_DIR/.env"
echo "  2. Start:        sudo systemctl start wolfpack-intel"
echo "  3. Check:        sudo systemctl status wolfpack-intel"
echo "  4. Logs:         sudo journalctl -u wolfpack-intel -f"
echo ""
if [ -n "$DOMAIN" ]; then
    echo "  Service URL:  https://$DOMAIN"
    echo "  Health check: curl https://$DOMAIN/health"
else
    DROPLET_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_DROPLET_IP")
    echo "  Service URL:  http://$DROPLET_IP"
    echo "  Health check: curl http://$DROPLET_IP/health"
fi
echo ""
echo "  Set INTEL_SERVICE_URL in Vercel to the URL above."
echo ""
