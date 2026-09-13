#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
DOMAIN="${1:-}"
EMAIL="${2:-}"
if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "Usage: bash nova-https-install.sh PANEL_DOMAIN EMAIL"
  echo "Example: bash nova-https-install.sh panel.example.com admin@example.com"
  exit 2
fi
command -v nginx >/dev/null 2>&1 || { echo 'Nginx is not installed. Run install-nova11.sh first.'; exit 3; }
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y certbot python3-certbot-nginx
if ! getent ahostsv4 "$DOMAIN" >/dev/null 2>&1; then
  echo "DNS for $DOMAIN does not resolve yet. Point an A record to this VPS and retry."
  exit 4
fi
cp -a /etc/nginx/sites-available/awg31-panel "/etc/nginx/sites-available/awg31-panel.bak.$(date +%Y%m%d%H%M%S)"
sed -i "s/server_name _;/server_name $DOMAIN;/" /etc/nginx/sites-available/awg31-panel
nginx -t
systemctl reload nginx
certbot --nginx --non-interactive --agree-tos --redirect --hsts --staple-ocsp -m "$EMAIL" -d "$DOMAIN"
nginx -t
systemctl reload nginx
systemctl enable certbot.timer >/dev/null 2>&1 || true
printf '\nHTTPS enabled successfully.\n'
printf 'Panel: https://%s/\n' "$DOMAIN"
printf 'Certificate renewal: certbot timer\n'
printf 'AWG UDP 1234: unchanged\n'
