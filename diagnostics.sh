#!/usr/bin/env bash
set -u
ok=0; total=0
pass(){ echo "[OK] $1"; ok=$((ok+1)); total=$((total+1)); }
fail(){ echo "[ERROR] $1"; total=$((total+1)); }
warn(){ echo "[WARN] $1"; total=$((total+1)); }
run(){ local label="$1"; shift; if "$@" >/dev/null 2>&1; then pass "$label"; else fail "$label"; fi; }
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
CONF=/etc/amnezia/amneziawg/awg0.conf
BASE=/opt/awg31-panel
echo '=== AWG Panel 8.1 / AmneziaWG 3.1 diagnostics ==='

echo '--- versions ---'
command -v awg >/dev/null 2>&1 && awg --version || echo 'awg: missing'
command -v awg-quick >/dev/null 2>&1 && awg-quick --version 2>/dev/null || true
printf 'kernel module: '; cat /sys/module/amneziawg/version 2>/dev/null || echo 'not loaded'

run 'AWG service active' systemctl is-active --quiet awg-quick@awg0
run 'awg0 interface exists' ip link show awg0
run 'AWG UAPI responds' awg show awg0
run 'Panel service active' systemctl is-active --quiet awgpanel
run 'Panel HTTP /login' curl -fsS --max-time 5 http://127.0.0.1:8080/login

if [ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo 0)" = 1 ]; then pass 'IPv4 forwarding enabled'; else fail 'IPv4 forwarding enabled'; fi

if [ -s "$CONF" ]; then
  pass 'AWG config exists'
  if [ "$(stat -c '%a' "$CONF" 2>/dev/null)" = 600 ]; then pass 'Config permissions 600'; else warn 'Config permissions are not 600'; fi
  if awg-quick strip awg0 >/dev/null 2>&1; then pass 'awg-quick config validation'; else fail 'awg-quick config validation'; fi
  python3 - "$CONF" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]); d={}
for line in p.read_text(errors='replace').splitlines():
    s=line.strip()
    if '=' in s and not s.startswith('#'):
        k,v=s.split('=',1); d[k.strip()]=v.strip()
required={'ListenPort':'443','MTU':'1280','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','RandomTrailers':'on','DisableCookies':'on'}
errors=[f'{k}={d.get(k)!r}, expected {v!r}' for k,v in required.items() if d.get(k)!=v]
if d.get('HeaderProtectionKey') and all(int(d.get(k,'0'))>=12 for k in ('S1','S2','S3','S4')):
    print('[OK] HeaderProtectionKey + S1-S4 compatibility');
else:
    print('[WARN] HeaderProtectionKey/S1-S4 compatibility not confirmed')
if errors:
    print('[ERROR] profile mismatch: '+'; '.join(errors)); sys.exit(1)
print('[OK] canonical mobile profile')
PY
  rc=$?; if [ $rc -eq 0 ]; then ok=$((ok+2)); total=$((total+2)); else total=$((total+2)); fi
else
  fail 'AWG config exists'
fi

if iptables -S >/dev/null 2>&1; then
  pass 'iptables available'
  if iptables -C INPUT -p udp --dport 443 -j ACCEPT >/dev/null 2>&1; then pass 'UDP 443 INPUT rule'; else warn 'UDP 443 INPUT rule not found (external firewall may still allow it)'; fi
  if iptables -t nat -S POSTROUTING 2>/dev/null | grep -q '10\.66\.66\.0/24.*MASQUERADE'; then pass 'IPv4 NAT masquerade'; else warn 'IPv4 NAT masquerade not found'; fi
else
  warn 'iptables unavailable; check nftables/cloud firewall separately'
fi

if [ -f "$BASE/app.py" ] && [ -x "$BASE/venv/bin/python" ]; then
  if "$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py" "$BASE/advanced_panel.py"; then pass 'Python modules compile'; else fail 'Python modules compile'; fi
else fail 'Panel Python environment'; fi

[ -f "$BASE/background.svg" ] && pass 'Panel background' || fail 'Panel background'
if [ -s /etc/awg31-panel/telegram.env ]; then run 'Telegram bot active' systemctl is-active --quiet awgpanel-telegram; else echo '[SKIP] Telegram Bot not configured'; fi

echo '--- runtime ---'
ip -br link show awg0 2>/dev/null || true
awg show awg0 2>/dev/null || true
ss -lunp 2>/dev/null | grep -E ':(443|51820)\b' || echo 'UDP 443 listener not shown by ss'

echo "Result: $ok/$total OK"
[ "$ok" -eq "$total" ] && exit 0 || exit 1
