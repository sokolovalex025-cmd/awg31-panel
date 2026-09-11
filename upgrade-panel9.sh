#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
SRC=$(cd "$(dirname "$0")" && pwd)
BASE=/opt/awg31-panel
[ -f "$SRC/app.py" ] || { echo 'app.py не найден.'; exit 1; }
[ -f "$SRC/app9.py" ] || { echo 'app9.py не найден.'; exit 1; }
mkdir -p "$BASE/backups"
TS=$(date +%Y%m%d-%H%M%S)
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-9-$TS.py"
[ -f "$BASE/app9.py" ] && cp -a "$BASE/app9.py" "$BASE/backups/app9-before-9-$TS.py"
cp "$SRC/app.py" "$BASE/app.py"
cp "$SRC/app9.py" "$BASE/app9.py"
for mod in naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py mobile_nav.py background.svg; do
  [ -f "$SRC/$mod" ] && cp "$SRC/$mod" "$BASE/$mod"
done
chmod 600 "$BASE/app.py" "$BASE/app9.py" 2>/dev/null || true
PY="$BASE/venv/bin/python"
[ -x "$PY" ] || { echo "Python venv не найден: $PY"; exit 1; }
for f in app.py app9.py naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py mobile_nav.py; do
  [ -f "$BASE/$f" ] && "$PY" -m py_compile "$BASE/$f"
done

# AWG 3.1 Strong Mobile: keep the production UDP port at 1234.
# Preserve all keys, peers and custom options; normalize only the known interface settings.
CONF=/etc/amnezia/amneziawg/awg0.conf
[ -f "$CONF" ] || CONF=/etc/wireguard/awg0.conf
if [ -f "$CONF" ]; then
  cp -a "$CONF" "$BASE/backups/awg0-before-panel9-$TS.conf"
  "$PY" - "$CONF" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text(errors='replace')
updates={'ListenPort':'1234','MTU':'1280','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','RandomTrailers':'on','DisableCookies':'on'}
lines=text.splitlines(); out=[]; seen=set(); in_iface=False
for line in lines:
    st=line.strip()
    if st.startswith('['): in_iface=(st=='[Interface]')
    if in_iface and '=' in st and not st.startswith('#'):
        k=st.split('=',1)[0].strip()
        if k in updates:
            out.append(f'{k} = {updates[k]}'); seen.add(k); continue
    out.append(line)
idx=next((i for i,x in enumerate(out) if x.strip()=='[Peer]'),len(out))
missing=[f'{k} = {v}' for k,v in updates.items() if k not in seen]
out[idx:idx]=missing
p.write_text('\n'.join(out).rstrip()+'\n'); p.chmod(0o600)
PY
  if systemctl is-active --quiet awg-quick@awg0; then
    systemctl restart awg-quick@awg0
    sleep 2
    systemctl is-active --quiet awg-quick@awg0 || { systemctl status awg-quick@awg0 --no-pager -l || true; journalctl -u awg-quick@awg0 -n 50 --no-pager || true; exit 1; }
  fi
fi

SECRET_FILE=/etc/awg31-panel/panel-secret
mkdir -p /etc/awg31-panel
chmod 700 /etc/awg31-panel
if [ ! -s "$SECRET_FILE" ]; then
  umask 077
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32 > "$SECRET_FILE"; else "$PY" -c 'import secrets; print(secrets.token_hex(32))' > "$SECRET_FILE"; fi
fi
chmod 600 "$SECRET_FILE"
SECRET=$(cat "$SECRET_FILE")

if [ -f /etc/systemd/system/awgpanel.service ]; then
  sed -i "s#^ExecStart=.*#ExecStart=$BASE/venv/bin/python $BASE/app9.py#" /etc/systemd/system/awgpanel.service
  if grep -q '^Environment=AWGPANEL_SECRET=' /etc/systemd/system/awgpanel.service; then
    sed -i "s#^Environment=AWGPANEL_SECRET=.*#Environment=AWGPANEL_SECRET=$SECRET#" /etc/systemd/system/awgpanel.service
  else
    sed -i "/^\[Service\]/a Environment=AWGPANEL_SECRET=$SECRET" /etc/systemd/system/awgpanel.service
  fi
else
  cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 9.3 Mobile Strong + AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
ExecStart=$BASE/venv/bin/python $BASE/app9.py
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
fi
chmod 600 /etc/systemd/system/awgpanel.service
systemctl daemon-reload
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:8080/about >/dev/null 2>&1 || true
printf '\nAWG Panel 9.3 установлен и отвечает на HTTP.\n'
printf 'AWG port: 1234/UDP\n'
