#!/usr/bin/env bash
set -u
ok=0; total=0
check(){ total=$((total+1)); if "$@" >/dev/null 2>&1; then echo "[OK] $1"; ok=$((ok+1)); else echo "[ERROR] $1"; fi; }
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
echo '=== AWG Panel 8.1 diagnostics ==='
check systemctl is-active --quiet awg-quick@awg0
check ip link show awg0
check awg show awg0
check systemctl is-active --quiet awgpanel
check curl -fsS --max-time 5 http://127.0.0.1:8080/login
if [ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo 0)" = 1 ]; then echo '[OK] IPv4 forwarding'; ok=$((ok+1)); else echo '[ERROR] IPv4 forwarding'; fi; total=$((total+1))
if [ -f /etc/amnezia/amneziawg/awg0.conf ]; then echo '[OK] AWG config exists'; ok=$((ok+1)); else echo '[ERROR] AWG config exists'; fi; total=$((total+1))
if [ -f /etc/amnezia/amneziawg/awg0.conf ] && [ "$(stat -c '%a' /etc/amnezia/amneziawg/awg0.conf)" = 600 ]; then echo '[OK] Config permissions 600'; ok=$((ok+1)); else echo '[WARN] Config permissions'; fi; total=$((total+1))
if [ -f /opt/awg31-panel/app.py ] && [ -x /opt/awg31-panel/venv/bin/python ]; then
  if /opt/awg31-panel/venv/bin/python -m py_compile /opt/awg31-panel/app.py /opt/awg31-panel/naiveproxy_panel.py /opt/awg31-panel/telegram_bot.py /opt/awg31-panel/system_panel.py /opt/awg31-panel/advanced_panel.py; then echo '[OK] Python modules'; ok=$((ok+1)); else echo '[ERROR] Python modules'; fi
else echo '[ERROR] Panel Python environment'; fi
total=$((total+1))
if command -v iptables >/dev/null 2>&1 || command -v nft >/dev/null 2>&1; then echo '[OK] Firewall/NAT tools'; ok=$((ok+1)); else echo '[ERROR] Firewall/NAT tools'; fi; total=$((total+1))
if [ -f /opt/awg31-panel/background.svg ]; then echo '[OK] Panel background'; ok=$((ok+1)); else echo '[ERROR] Panel background'; fi; total=$((total+1))
if [ -s /etc/awg31-panel/telegram.env ]; then check systemctl is-active --quiet awgpanel-telegram; else echo '[SKIP] Telegram Bot not configured'; fi

echo "Result: $ok/$total OK"
