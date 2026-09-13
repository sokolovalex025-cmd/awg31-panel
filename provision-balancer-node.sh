#!/usr/bin/env bash
set -euo pipefail
TOKEN="${1:?BALANCER_TOKEN is required}"
BASE_URL="${NOVA_BASE_URL:-https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main}"
install -d -m 755 /opt/awg31-panel
curl -fsSL "$BASE_URL/balancer-node.py" -o /opt/awg31-panel/balancer-node.py
curl -fsSL "$BASE_URL/balancer-node.service" -o /etc/systemd/system/nova-awg-balancer-node.service
install -d -m 700 /etc/awg31-panel
printf 'BALANCER_TOKEN=%s\n' "$TOKEN" > /etc/awg31-panel/balancer-node.env
chmod 600 /etc/awg31-panel/balancer-node.env
systemctl daemon-reload
systemctl enable --now nova-awg-balancer-node.service
sleep 1
curl -fsS --max-time 3 http://127.0.0.1:9090/health
printf '\nNOVA balancer node installed.\n'
