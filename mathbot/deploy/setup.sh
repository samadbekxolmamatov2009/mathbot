#!/usr/bin/env bash
# Oracle Cloud VM (Ubuntu) ichida bir marta ishga tushiriladi.
# SSH orqali VM'ga kirgach: bash setup.sh
set -euo pipefail

echo "== Tizim paketlari =="
sudo apt update
sudo apt install -y python3-venv python3-pip ufw

echo "== Caddy o'rnatish (avtomatik HTTPS uchun) =="
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy

echo "== VM ichidagi firewall (ufw) =="
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo "== Python virtualenv va kutubxonalar =="
cd /home/ubuntu/mathbot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cat <<'EOF'

Loyiha kutubxonalari o'rnatildi. Endi qo'lda quyidagilarni bajaring:

1) deploy/mathbot.service faylidagi CHANGE_ME qiymatlarni (BOT_TOKEN,
   WEBAPP_URL, TEST_WEBAPP_URL) to'ldiring, so'ng:
     sudo cp deploy/mathbot.service /etc/systemd/system/mathbot.service
     sudo systemctl daemon-reload
     sudo systemctl enable --now mathbot

2) deploy/Caddyfile faylidagi CHANGE_ME.sslip.io ni haqiqiy VM IP
   manzilingiz bilan almashtiring (masalan 12.34.56.78.sslip.io), so'ng:
     sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
     sudo systemctl restart caddy

3) Holatni tekshirish:
     sudo systemctl status mathbot
     sudo systemctl status caddy
     journalctl -u mathbot -f
EOF
