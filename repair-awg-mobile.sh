#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }

CONF=/etc/amnezia/amneziawg/awg0.conf
BACKUP_DIR=/opt/awg31-panel/backups
mkdir -p "$BACKUP_DIR"

command -v awg >/dev/null 2>&1 || { echo 'ОШИБКА: awg не найден'; exit 1; }
command -v awg-quick >/dev/null 2>&1 || { echo 'ОШИБКА: awg-quick не найден'; exit 1; }
[ -s "$CONF" ] || { echo "ОШИБКА: $CONF не найден"; exit 1; }

TS=$(date +%Y%m%d-%H%M%S)
cp -a "$CONF" "$BACKUP_DIR/awg0-before-mobile-$TS.conf"

# AWG 3.1 accepts boolean values as on/off or 0/1, not true/false.
# Keep the same S1-S4 profile on server and clients.
python3 - "$CONF" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
lines=p.read_text(errors='replace').splitlines()
updates={
    'ListenPort':'443',
    'MTU':'1280',
    'Jc':'4',
    'Jmin':'40',
    'Jmax':'120',
    'S1':'16',
    'S2':'24',
    'S3':'16',
    'S4':'32',
    'H1':'1',
    'H2':'2',
    'H3':'3',
    'H4':'4',
    'RandomTrailers':'on',
    'DisableCookies':'on',
}
seen=set();out=[]
for line in lines:
    stripped=line.strip()
    if '=' in stripped and not stripped.startswith('#'):
        k=stripped.split('=',1)[0].strip()
        if k in updates:
            out.append(f'{k} = {updates[k]}')
            seen.add(k)
            continue
        if k in ('HeaderProtectionKey','ContentPaddingAddition','RekeyAfterTime','RekeyTimeout','RejectAfterTime','KeepaliveTimeout','MaxHandshakeAttempts'):
            out.append(line)
            seen.add(k)
            continue
    out.append(line)
insert=[]
for k,v in updates.items():
    if k not in seen: insert.append(f'{k} = {v}')
if insert:
    try: idx=next(i for i,x in enumerate(out) if x.strip()=='[Peer]')
    except StopIteration: idx=len(out)
    out[idx:idx]=insert
p.write_text('\n'.join(out).rstrip()+'\n')
PY
chmod 600 "$CONF"

if ! awg-quick strip awg0 >/dev/null 2>&1; then
  echo 'ОШИБКА: AWG 3.1 не принимает конфигурацию.'
  awg-quick strip awg0 || true
  echo "Резервная копия: $BACKUP_DIR/awg0-before-mobile-$TS.conf"
  exit 1
fi

sysctl -w net.ipv4.ip_forward=1 >/dev/null
cat >/etc/sysctl.d/99-awg31-panel.conf <<EOF
net.ipv4.ip_forward=1
EOF
sysctl --system >/dev/null 2>&1 || true

WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
if [ -n "${WAN_IF:-}" ]; then
  iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport 443 -j ACCEPT
  iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE
fi

systemctl daemon-reload
systemctl restart awg-quick@awg0.service
sleep 2
if ! systemctl is-active --quiet awg-quick@awg0.service; then
  echo 'ОШИБКА: awg0 не запустился после mobile-профиля.'
  systemctl status awg-quick@awg0.service --no-pager -l || true
  journalctl -u awg-quick@awg0.service -n 80 --no-pager || true
  exit 1
fi

systemctl restart awgpanel 2>/dev/null || true

echo '=== AWG MOBILE PROFILE READY ==='
awg --version
systemctl is-active awg-quick@awg0.service
awg show awg0
ip -br link show awg0
printf 'ListenPort: '; awk -F= '/^[[:space:]]*ListenPort[[:space:]]*=/{gsub(/[[:space:]]/,"",$2);print $2;exit}' "$CONF"
printf 'MTU: '; awk -F= '/^[[:space:]]*MTU[[:space:]]*=/{gsub(/[[:space:]]/,"",$2);print $2;exit}' "$CONF"
printf 'S1-S4: '; awk -F= '/^[[:space:]]*S[1-4][[:space:]]*=/{gsub(/[[:space:]]/,"",$2);printf "%s ",$2} END{print ""}' "$CONF"
echo "Client profiles will inherit the same S1-S4/obfuscation values from the server."
echo "Backup: $BACKUP_DIR/awg0-before-mobile-$TS.conf"
