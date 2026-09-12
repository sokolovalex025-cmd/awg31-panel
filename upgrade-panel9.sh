#!/usr/bin/env bash
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
SRC=$(cd "$(dirname "$0")" && pwd)
BASE=/opt/awg31-panel
PY="$BASE/venv/bin/python"
BACKUP="$BASE/backups"
TS=$(date +%Y%m%d-%H%M%S)
CONF=/etc/amnezia/amneziawg/awg0.conf
[ -f "$CONF" ] || CONF=/etc/wireguard/awg0.conf
SERVICE=/etc/systemd/system/awgpanel.service

[ -f "$SRC/app.py" ] || { echo 'app.py не найден.'; exit 1; }
[ -f "$SRC/app9.py" ] || { echo 'app9.py не найден.'; exit 1; }
[ -x "$PY" ] || { echo "Python venv не найден: $PY"; exit 1; }

mkdir -p "$BACKUP"

# Backup only files that are actually part of the stable NOVA core.
for f in app.py app9.py; do
  [ -f "$BASE/$f" ] && cp -a "$BASE/$f" "$BACKUP/$f-before-nova-$TS"
done
[ -f "$CONF" ] && cp -a "$CONF" "$BACKUP/awg0-before-nova-$TS.conf"
[ -f "$SERVICE" ] && cp -a "$SERVICE" "$BACKUP/awgpanel-before-nova-$TS.service"

rollback() {
  echo
  echo '!!! NOVA update failed — rolling back.'
  for f in app.py app9.py; do
    [ -f "$BACKUP/$f-before-nova-$TS" ] && cp -a "$BACKUP/$f-before-nova-$TS" "$BASE/$f"
  done
  [ -f "$BACKUP/awgpanel-before-nova-$TS.service" ] && cp -a "$BACKUP/awgpanel-before-nova-$TS.service" "$SERVICE"
  [ -f "$BACKUP/awg0-before-nova-$TS.conf" ] && cp -a "$BACKUP/awg0-before-nova-$TS.conf" "$CONF"
  systemctl daemon-reload || true
  systemctl restart awg-quick@awg0 || true
  systemctl restart awgpanel || true
  echo 'Rollback completed.'
}
trap rollback ERR

# Stage new application files first and compile before touching services.
install -m 600 "$SRC/app.py" "$BASE/app.py.new"
install -m 755 "$SRC/app9.py" "$BASE/app9.py.new"
"$PY" -m py_compile "$BASE/app.py.new" "$BASE/app9.py.new"
"$PY" - "$BASE/app.py.new" <<'PY'
import importlib.util, sys
p=sys.argv[1]
spec=importlib.util.spec_from_file_location('nova_app_check',p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert hasattr(m,'app'), 'Flask app object missing'
print('NOVA import check: OK')
PY

mv -f "$BASE/app.py.new" "$BASE/app.py"
mv -f "$BASE/app9.py.new" "$BASE/app9.py"
chmod 600 "$BASE/app.py"
chmod 755 "$BASE/app9.py"

# Keep the core service free from legacy optional-module registration conflicts.
# Optional legacy modules are intentionally NOT copied or auto-imported here.

# Preserve the working AWG configuration but normalize only NOVA 3.1 transport parameters.
if [ -f "$CONF" ]; then
  "$PY" - "$CONF" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
text=p.read_text(errors='replace')
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
out[idx:idx]=[f'{k} = {v}' for k,v in updates.items() if k not in seen]
p.write_text('\n'.join(out).rstrip()+'\n'); p.chmod(0o600)
PY
  if systemctl is-active --quiet awg-quick@awg0; then
    systemctl restart awg-quick@awg0
    sleep 2
    systemctl is-active --quiet awg-quick@awg0
  fi
fi

SECRET_FILE=/etc/awg31-panel/panel-secret
mkdir -p /etc/awg31-panel
chmod 700 /etc/awg31-panel
if [ ! -s "$SECRET_FILE" ]; then
  umask 077
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32 > "$SECRET_FILE"; else "$PY" -c 'import secrets;print(secrets.token_hex(32))' > "$SECRET_FILE"; fi
fi
chmod 600 "$SECRET_FILE"
SECRET=$(cat "$SECRET_FILE")

if [ -f "$SERVICE" ]; then
  sed -i "s#^Description=.*#Description=NOVA Network Control Center - AmneziaWG 3.1#" "$SERVICE"
  sed -i "s#^ExecStart=.*#ExecStart=$BASE/venv/bin/python $BASE/app9.py#" "$SERVICE"
  if grep -q '^Environment=AWGPANEL_SECRET=' "$SERVICE"; then
    sed -i "s#^Environment=AWGPANEL_SECRET=.*#Environment=AWGPANEL_SECRET=$SECRET#" "$SERVICE"
  else
    sed -i "/^\[Service\]/a Environment=AWGPANEL_SECRET=$SECRET" "$SERVICE"
  fi
else
  cat >"$SERVICE" <<EOF
[Unit]
Description=NOVA Network Control Center - AmneziaWG 3.1
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
chmod 644 "$SERVICE"

systemctl daemon-reload
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null

# The updater succeeds only if both services are healthy and no legacy conflict appeared.
if systemctl is-enabled --quiet awgpanel-telegram.service 2>/dev/null || [ -s /etc/awg31-panel/telegram.env ]; then
  systemctl daemon-reload
  systemctl restart awgpanel-telegram.service || true
fi

trap - ERR
printf '\nNOVA Network Control Center обновлён успешно.\n'
printf 'AmneziaWG 3.1: 1234/UDP\n'
printf 'Panel: active\n'
printf 'HTTP: 200\n'
printf 'Backup: %s\n' "$BACKUP"
