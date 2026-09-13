#!/usr/bin/env bash
set -Eeuo pipefail

# NOVA network fix: keep awg0 untouched, provide internet NAT for AWG clients.
# Detect the real WAN interface from the default route instead of hard-coding ens3.
WAN_IF="$(ip -4 route show default 2>/dev/null | awk 'NR==1 {print $5}')"
[ -n "$WAN_IF" ] || { echo "NOVA: default WAN interface not found" >&2; exit 1; }

iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE 2>/dev/null || \
  iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE

iptables -C FORWARD -i awg0 -o "$WAN_IF" -s 10.66.66.0/24 -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -i awg0 -o "$WAN_IF" -s 10.66.66.0/24 -j ACCEPT

iptables -C FORWARD -i "$WAN_IF" -o awg0 -d 10.66.66.0/24 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
  iptables -A FORWARD -i "$WAN_IF" -o awg0 -d 10.66.66.0/24 -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

sysctl -w net.ipv4.ip_forward=1 >/dev/null
mkdir -p /etc/sysctl.d
printf 'net.ipv4.ip_forward=1\n' > /etc/sysctl.d/99-awg31-forward.conf

# The panel previously defaulted clients to its own address as DNS, but no DNS
# daemon listens on 10.66.66.1. Migrate only that old default; preserve custom DNS.
DB=/opt/awg31-panel/panel.db
if [ -f "$DB" ]; then
  /usr/bin/python3 - "$DB" <<'PY'
import sqlite3, sys
p=sys.argv[1]
con=sqlite3.connect(p)
con.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")
row=con.execute("SELECT v FROM settings WHERE k='dns'").fetchone()
if row is None:
    con.execute("INSERT INTO settings(k,v) VALUES('dns','1.1.1.1,8.8.8.8')")
elif (row[0] or '').strip() in ('', '10.66.66.1'):
    con.execute("UPDATE settings SET v='1.1.1.1,8.8.8.8' WHERE k='dns'")
con.commit(); con.close()
PY
fi

echo "NOVA network OK: awg0 -> $WAN_IF NAT, IPv4 forwarding enabled, client DNS=1.1.1.1,8.8.8.8"
