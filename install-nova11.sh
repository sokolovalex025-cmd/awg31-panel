#!/usr/bin/env bash
set -Eeuo pipefail

# Clean-server installer for NOVA 11.
# Installs the panel only; it never overwrites an existing AWG interface/config.
# Run the AmneziaWG 3.1 installer first on a fresh VPS.

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
BASE="/opt/awg31-panel"
SERVICE="/etc/systemd/system/awgpanel.service"

if ! command -v awg >/dev/null 2>&1; then
  echo 'AmneziaWG tool "awg" was not found.'
  echo 'Install AmneziaWG 3.1 first, then run this installer again.'
  exit 2
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip curl qrencode

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" reset --hard origin/main
else
  rm -rf "$REPO_DIR"
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi

python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --upgrade pip
"$REPO_DIR/venv/bin/pip" install Flask qrcode[pil]

mkdir -p "$BASE/backups"
for f in app.py nova11.py panel_bootstrap.py keenetic.py balancer.py balancer_provision.py keenetic-routing-guide.txt background.svg; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
chmod 755 "$BASE/nova11.py" "$BASE/panel_bootstrap.py"

# The bootstrap creates the SQLite schema and default settings on first start.
# Do not touch /etc/amnezia/amneziawg/awg0.conf or /etc/wireguard/awg0.conf here.
SECRET_DIR=/etc/awg31-panel
SECRET_FILE="$SECRET_DIR/panel-secret"
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"
if [ ! -s "$SECRET_FILE" ]; then
  umask 077
  "$REPO_DIR/venv/bin/python" -c 'import secrets;print(secrets.token_hex(32))' > "$SECRET_FILE"
fi
chmod 600 "$SECRET_FILE"
SECRET=$(cat "$SECRET_FILE")

cat > "$SERVICE" <<EOF
[Unit]
Description=NOVA 11 Network Control Center - AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
ExecStart=$REPO_DIR/venv/bin/python $BASE/panel_bootstrap.py
Restart=on-failure
RestartSec=2
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
EOF

"$REPO_DIR/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/keenetic.py" "$BASE/balancer.py"

systemctl daemon-reload
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null

printf '\nNOVA 11 installed successfully.\n'
printf 'Service: awgpanel\n'
printf 'ExecStart: %s\n' "$REPO_DIR/venv/bin/python $BASE/panel_bootstrap.py"
printf 'Web: http://SERVER:8080\n'
printf 'AWG interface/config: preserved\n'
printf 'Keenetic: native NOVA menu + /keenetic\n'
printf 'Health: /api/nova/health\n'
