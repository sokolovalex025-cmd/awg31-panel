#!/usr/bin/env bash
set -euo pipefail
BASE=/opt/awg31-panel
RAW='https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main'
cd "$BASE"
cp -a app.py "app.py.bak-cluster-$(date +%Y%m%d-%H%M%S)"
cp -a app9.py "app9.py.bak-cluster-$(date +%Y%m%d-%H%M%S)"
install -d -m 755 "$BASE/balancer"
for f in balancer.py balancer_provision.py balancer-node.py balancer-node.service provision-balancer-node.sh; do
  case "$f" in
    balancer-node.service) curl -fsSL "$RAW/$f" -o /etc/systemd/system/nova-awg-balancer-node.service ;;
    *) curl -fsSL "$RAW/$f" -o "$BASE/$f" ;;
  esac
done
install -d -m 700 /etc/awg31-panel
if [ ! -s /etc/awg31-panel/balancer.env ]; then
  python3 - <<'PY' > /etc/awg31-panel/balancer.env
import secrets
print('BALANCER_TOKEN='+secrets.token_urlsafe(32))
PY
  chmod 600 /etc/awg31-panel/balancer.env
fi
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/awg31-panel/app.py'); s=p.read_text()
old="('☷','Логи','/logs')])"
new="('☷','Логи','/logs'),('⚖','Балансировка','/balancer')])"
if old in s and "'/balancer'" not in s:s=s.replace(old,new,1)
p.write_text(s)
PY
systemctl daemon-reload
systemctl restart awgpanel.service
sleep 2
systemctl --no-pager --full status awgpanel.service
printf '\nCluster module check:\n'
/opt/awg31-panel/venv/bin/python - <<'PY'
import sys
sys.path.insert(0,'/opt/awg31-panel')
import app
import balancer
import balancer_provision
print('OK: modules loaded, routes:', [r.rule for r in app.app.url_map.iter_rules() if 'balancer' in r.rule])
PY
printf '\nOpen: http://SERVER-IP:8080/balancer\n'
