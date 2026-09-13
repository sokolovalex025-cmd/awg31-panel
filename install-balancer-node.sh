#!/usr/bin/env bash
set -euo pipefail
TOKEN="${1:-}"
[ -n "$TOKEN" ] || { echo "Usage: sudo ./install-balancer-node.sh <BALANCER_TOKEN>"; exit 1; }
BASE=/opt/awg31-panel
mkdir -p "$BASE"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/balancer-node.py -o "$BASE/balancer-node.py"
  curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/balancer-node.service -o /etc/systemd/system/nova-awg-balancer-node.service
else
  echo 'curl is required'; exit 1
fi
chmod 700 "$BASE/balancer-node.py"
mkdir -p /etc/awg31-panel
printf 'BALANCER_TOKEN=%s\n' "$TOKEN" > /etc/awg31-panel/balancer-node.env
chmod 600 /etc/awg31-panel/balancer-node.env
python3 - <<'PY'
from pathlib import Path
p=Path('/etc/systemd/system/nova-awg-balancer-node.service')
s=p.read_text()
s=s.replace('Environment=BALANCER_NODE_PORT=9090','EnvironmentFile=/etc/awg31-panel/balancer-node.env\nEnvironment=BALANCER_NODE_PORT=9090')
p.write_text(s)
PY
systemctl daemon-reload
systemctl enable --now nova-awg-balancer-node.service
systemctl --no-pager --full status nova-awg-balancer-node.service || true
echo 'NOVA balancer node is listening on TCP 9090. Restrict this port to the panel IP.'
