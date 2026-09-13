#!/usr/bin/env bash
set -Eeuo pipefail

# Keenetic-compatible AWG 2.0 profile using the already installed, matching
# AmneziaWG kernel/userspace on the VPS. The existing NOVA awg0 (AWG 3.1)
# interface is never modified.

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }

BASE=/opt/keenetic-awg2
IFACE=awg-keenetic
PORT="${KEENETIC_AWG2_PORT:-51820}"
SUBNET="10.77.0.0/24"
SERVER_IP="10.77.0.1"
CLIENT_IP="10.77.0.2"
MTU="1280"
WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
[ -n "${WAN_IF:-}" ] || WAN_IF=eth0

case "$PORT" in
  ''|*[!0-9]*) echo 'Invalid KEENETIC_AWG2_PORT'; exit 1;;
esac
[ "$PORT" -ge 1 ] && [ "$PORT" -le 65535 ] || { echo 'Port must be 1..65535.'; exit 1; }

command -v awg >/dev/null 2>&1 || { echo 'Matching AmneziaWG tools are not installed.'; exit 1; }
command -v awg-quick >/dev/null 2>&1 || { echo 'awg-quick is not installed.'; exit 1; }

HOST_AWG_VERSION=$(awg --version 2>/dev/null | head -1 || true)
MODULE_VERSION=$(modinfo -F version amneziawg 2>/dev/null || true)
case "$HOST_AWG_VERSION" in
  *3.1*) ;;
  *) echo "Unsupported host AWG tools: ${HOST_AWG_VERSION:-unknown}"; exit 1;;
esac
case "$MODULE_VERSION" in
  3.1*) ;;
  *) echo "Unsupported amneziawg kernel module: ${MODULE_VERSION:-unknown}"; exit 1;;
esac

if ss -lunH 2>/dev/null | awk '{print $5}' | grep -Eq ":${PORT}$"; then
  echo "UDP port $PORT is already in use. Set KEENETIC_AWG2_PORT to another free port."
  exit 1
fi

mkdir -p "$BASE/config" "$BASE/clients"
chmod 700 "$BASE" "$BASE/config" "$BASE/clients"

# Stop/remove the broken Docker bridge from previous versions. Do not touch NOVA awg0.
if command -v docker >/dev/null 2>&1 && docker ps -a --format '{{.Names}}' | grep -qx keenetic-awg2; then
  docker rm -f keenetic-awg2 >/dev/null 2>&1 || true
fi

# Bring down only our dedicated interface if an older installation exists.
awg-quick down "$BASE/config/${IFACE}.conf" >/dev/null 2>&1 || true
ip link del "$IFACE" >/dev/null 2>&1 || true

if [ -f "$BASE/config/server_private.key" ]; then
  SERVER_PRIVATE_KEY=$(cat "$BASE/config/server_private.key")
else
  SERVER_PRIVATE_KEY=$(awg genkey)
  printf '%s\n' "$SERVER_PRIVATE_KEY" >"$BASE/config/server_private.key"
  chmod 600 "$BASE/config/server_private.key"
fi
SERVER_PUBLIC_KEY=$(printf '%s' "$SERVER_PRIVATE_KEY" | awg pubkey)

if [ -f "$BASE/config/client_private.key" ]; then
  CLIENT_PRIVATE_KEY=$(cat "$BASE/config/client_private.key")
else
  CLIENT_PRIVATE_KEY=$(awg genkey)
  printf '%s\n' "$CLIENT_PRIVATE_KEY" >"$BASE/config/client_private.key"
  chmod 600 "$BASE/config/client_private.key"
fi
CLIENT_PUBLIC_KEY=$(printf '%s' "$CLIENT_PRIVATE_KEY" | awg pubkey)

if [ -f "$BASE/config/psk.key" ]; then
  PSK=$(cat "$BASE/config/psk.key")
else
  PSK=$(awg genpsk)
  printf '%s\n' "$PSK" >"$BASE/config/psk.key"
  chmod 600 "$BASE/config/psk.key"
fi

# KeeneticOS 5.1+ expects the AWG 1.5/2.0-style fields. I1-I5 are omitted.
# The VPS uses the matching AWG 3.1 tools/kernel, but this profile only uses
# the AWG 2.0-compatible J/S/H parameter set.
cat >"$BASE/config/${IFACE}.conf" <<EOF
[Interface]
PrivateKey = $SERVER_PRIVATE_KEY
Address = $SERVER_IP/24
ListenPort = $PORT
MTU = $MTU
Jc = 3
Jmin = 10
Jmax = 30
S1 = 10
S2 = 10
S3 = 10
S4 = 10
H1 = 1
H2 = 2
H3 = 3
H4 = 4
PostUp = iptables -A FORWARD -i %i -s $SUBNET -j ACCEPT; iptables -A FORWARD -o %i -d $SUBNET -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT; iptables -t nat -A POSTROUTING -s $SUBNET -o $WAN_IF -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -s $SUBNET -j ACCEPT; iptables -D FORWARD -o %i -d $SUBNET -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT; iptables -t nat -D POSTROUTING -s $SUBNET -o $WAN_IF -j MASQUERADE

[Peer]
PublicKey = $CLIENT_PUBLIC_KEY
PresharedKey = $PSK
AllowedIPs = $CLIENT_IP/32
EOF
chmod 600 "$BASE/config/${IFACE}.conf"

PUBLIC_IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
[ -n "${PUBLIC_IP:-}" ] || PUBLIC_IP="SERVER_IP"

cat >"$BASE/clients/keenetic-awg2.conf" <<EOF
[Interface]
PrivateKey = $CLIENT_PRIVATE_KEY
Address = $CLIENT_IP/32
DNS = 1.1.1.1
MTU = $MTU
Jc = 3
Jmin = 10
Jmax = 30
S1 = 10
S2 = 10
S3 = 10
S4 = 10
H1 = 1
H2 = 2
H3 = 3
H4 = 4

[Peer]
PublicKey = $SERVER_PUBLIC_KEY
PresharedKey = $PSK
Endpoint = $PUBLIC_IP:$PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
chmod 600 "$BASE/clients/keenetic-awg2.conf"

sysctl -w net.ipv4.ip_forward=1 >/dev/null
printf '%s\n' 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-keenetic-awg2.conf
iptables -C INPUT -p udp --dport "$PORT" -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport "$PORT" -j ACCEPT

# Validate the exact server config with the same AWG userspace/kernel pair.
ip link add "$IFACE" type amneziawg
awg setconf "$IFACE" "$BASE/config/${IFACE}.conf"
ip address add "$SERVER_IP/24" dev "$IFACE"
ip link set mtu "$MTU" up dev "$IFACE"

# NAT/FORWARD rules are installed explicitly because this interface is not
# managed by the broken Docker userspace bridge anymore.
iptables -C FORWARD -i "$IFACE" -s "$SUBNET" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$IFACE" -s "$SUBNET" -j ACCEPT
iptables -C FORWARD -o "$IFACE" -d "$SUBNET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || iptables -A FORWARD -o "$IFACE" -d "$SUBNET" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -C POSTROUTING -s "$SUBNET" -o "$WAN_IF" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "$SUBNET" -o "$WAN_IF" -j MASQUERADE

# Replace the old systemd unit with a robust service that owns only this interface.
cat >"/etc/systemd/system/keenetic-awg2.service" <<EOF
[Unit]
Description=NOVA Keenetic-compatible AWG 2.0 bridge
After=network-online.target
Wants=network-online.target
Before=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/awg-quick up $BASE/config/${IFACE}.conf
ExecStop=/usr/bin/awg-quick down $BASE/config/${IFACE}.conf
ExecStartPost=/usr/bin/iptables -C INPUT -p udp --dport $PORT -j ACCEPT
ExecStartPost=/bin/sh -c '/usr/bin/iptables -C FORWARD -i $IFACE -s $SUBNET -j ACCEPT || /usr/bin/iptables -A FORWARD -i $IFACE -s $SUBNET -j ACCEPT'
ExecStartPost=/bin/sh -c '/usr/bin/iptables -t nat -C POSTROUTING -s $SUBNET -o $WAN_IF -j MASQUERADE || /usr/bin/iptables -t nat -A POSTROUTING -s $SUBNET -o $WAN_IF -j MASQUERADE'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable keenetic-awg2.service >/dev/null
systemctl restart keenetic-awg2.service

# Final checks.
ip link show "$IFACE" >/dev/null
awg show "$IFACE" >/dev/null

cat >"$BASE/README.txt" <<EOF
NOVA Keenetic AWG 2.0-compatible bridge
=======================================
Interface: $IFACE
UDP port: $PORT
Server subnet: $SUBNET
Client config: $BASE/clients/keenetic-awg2.conf

The bridge uses the VPS's matching AmneziaWG 3.1 userspace/kernel pair with
only the AWG 2.0-compatible Jc/Jmin/Jmax/S1-S4/H1-H4 profile. No I1-I5 fields
are used. The existing NOVA AWG 3.1 awg0 interface remains untouched.

KeeneticOS 5.1+ can use the generated config where supported. For selective
routing, use the NOVA Keenetic route generator and route through this tunnel.
EOF

printf '\nKeenetic AWG 2.0-compatible bridge installed.\n'
printf 'Interface: %s\n' "$IFACE"
printf 'Config: %s\n' "$BASE/clients/keenetic-awg2.conf"
printf 'Endpoint: %s:%s/udp\n' "$PUBLIC_IP" "$PORT"
printf 'Host AWG: %s\n' "$HOST_AWG_VERSION"
printf 'AWG kernel: %s\n' "$MODULE_VERSION"
printf 'Existing AWG 3.1 awg0: untouched\n'
printf '\nCheck: awg show %s\n' "$IFACE"
