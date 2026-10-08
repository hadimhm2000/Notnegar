#!/usr/bin/env bash
# Install Notnegar without Docker on Ubuntu 22.04 / 24.04 or Debian 12.  Run as root:
#   sudo bash deploy/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX=/opt/notnegar

apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip ffmpeg lilypond fontconfig \
  fonts-noto-core fonts-dejavu-core curl nginx
apt-get install -y --no-install-recommends fonts-vazirmatn || true

id notnegar >/dev/null 2>&1 || useradd --system --home "$PREFIX" --shell /usr/sbin/nologin notnegar
mkdir -p "$PREFIX/data" "$PREFIX/models"
rsync -a --delete --exclude data --exclude .env "$REPO_DIR/" "$PREFIX/" 2>/dev/null || cp -r "$REPO_DIR/." "$PREFIX/"
[ -f "$PREFIX/server/.env" ] || cp "$PREFIX/server/.env.example" "$PREFIX/server/.env"

python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/pip" install --upgrade pip
"$PREFIX/venv/bin/pip" install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cpu
"$PREFIX/venv/bin/pip" install -r "$PREFIX/server/requirements.txt" -r "$PREFIX/server/requirements-ml.txt"
"$PREFIX/venv/bin/pip" install "basic-pitch==0.4.0" "numpy<2" || echo "basic-pitch skipped (optional)"
TORCH_HOME="$PREFIX/models" "$PREFIX/venv/bin/python" "$PREFIX/server/scripts/download_models.py" || true

chown -R notnegar:notnegar "$PREFIX"
cp "$PREFIX/server/deploy/notnegar.service" /etc/systemd/system/notnegar.service
systemctl daemon-reload
systemctl enable --now notnegar

if [ ! -f /etc/nginx/sites-available/notnegar ]; then
  cp "$PREFIX/server/deploy/nginx.conf" /etc/nginx/sites-available/notnegar
  ln -sf /etc/nginx/sites-available/notnegar /etc/nginx/sites-enabled/notnegar
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
fi

sleep 3
curl -fs http://127.0.0.1:8000/api/health && echo && echo "Notnegar is running."
