#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx
cat >/etc/nginx/sites-available/awg31-panel <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 20m;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
ln -sfn /etc/nginx/sites-available/awg31-panel /etc/nginx/sites-enabled/awg31-panel
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx
systemctl is-active --quiet nginx
printf '\nNginx reverse proxy installed.\n'
printf 'NOVA upstream: http://127.0.0.1:8080\n'
printf 'Public HTTP: port 80\n'
printf 'Config: /etc/nginx/sites-available/awg31-panel\n'
