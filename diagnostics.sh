#!/usr/bin/env bash
set -u
ok=0; total=0
check(){ total=$((total+1)); if "$@" >/dev/null 2>&1; then echo "[OK] $1"; ok=$((ok+1)); else echo "[ERROR] $1"; fi; }
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
echo '=== AWG Panel 7.1 diagnostics ==='
check systemctl is-active --quiet awg-quick@awg0
check ip link show awg0
check awg show awg0
check systemctl is-active --quiet awgpanel
if [ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo 0)" = 1 ]; then echo '[OK] IPv4 forwarding'; ok=$((ok+1)); else echo '[ERROR] IPv4 forwarding'; fi; total=$((total+1))
if [ -f /etc/amnezia/amneziawg/awg0.conf ]; then echo '[OK] AWG config exists'; ok=$((ok+1)); else echo '[ERROR] AWG config exists'; fi; total=$((total+1))
if [ -f /etc/amnezia/amneziawg/awg0.conf ] && [ "$(stat -c '%a' /etc/amnezia/amneziawg/awg0.conf)" = 600 ]; then echo '[OK] Config permissions 600'; ok=$((ok+1)); else echo '[WARN] Config permissions'; fi; total=$((total+1))
if command -v iptables >/dev/null 2>&1 || command -v nft >/dev/null 2>&1; then echo '[OK] Firewall/NAT tools'; ok=$((ok+1)); else echo '[ERROR] Firewall/NAT tools'; fi; total=$((total+1))
echo "Result: $ok/$total OK"
