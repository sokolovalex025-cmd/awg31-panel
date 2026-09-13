#!/usr/bin/env bash
set -Eeuo pipefail

# Isolated AmneziaWG 2.0 userspace server for KeeneticOS 5.1+.
# It does NOT modify /etc/amnezia/amneziawg/awg0.conf or the NOVA AWG 3.1 service.

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }

BASE=/opt/keenetic-awg2
CONTAINER=keenetic-awg2
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

if ss -lunH 2>/dev/null | awk '{print $5}' | grep -Eq ":${PORT}$"; then
  echo "UDP port $PORT is already in use. Set KEENETIC_AWG2_PORT to another free port."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker.io
  systemctl enable --now docker
fi

mkdir -p "$BASE/config" "$BASE/clients"
chmod 700 "$BASE" "$BASE/config" "$BASE/clients"

# Build a pinned, isolated AWG 2.0 userspace image from the official Amnezia base.
cat >"$BASE/Dockerfile" <<'EOF'
FROM amneziavpn/amneziawg-go:latest
RUN apk add --no-cache bash curl dumb-init iptables
RUN mkdir -p /opt/amnezia/awg
COPY start.sh /opt/amnezia/start.sh
RUN chmod 0755 /opt/amnezia/start.sh
ENTRYPOINT ["dumb-init", "/opt/amnezia/start.sh"]
EOF

cat >"$BASE/start.sh" <<'EOF'
#!/bin/bash
set -e
awg-quick down /opt/amnezia/awg/awg0.conf >/dev/null 2>&1 || true
awg-quick up /opt/amnezia/awg/awg0.conf
iptables -A INPUT -i awg0 -j ACCEPT
iptables -A FORWARD -i awg0 -j ACCEPT
iptables -A OUTPUT -o awg0 -j ACCEPT
iptables -A FORWARD -i awg0 -o eth0 -s 10.77.0.0/24 -j ACCEPT
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -t nat -A POSTROUTING -s 10.77.0.0/24 -o eth0 -j MASQUERADE
tail -f /dev/null
EOF
chmod 0755 "$BASE/start.sh"

docker build --pull -t "$CONTAINER:awg2" "$BASE"

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

# AWG 2.0 format: S3/S4 + I1 are required/recognized by KeeneticOS 5.1+.
cat >"$BASE/config/awg0.conf" <<EOF
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
I1 = <r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.77.0.0/24 -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.77.0.0/24 -o eth0 -j MASQUERADE

[Peer]
PublicKey = $CLIENT_PUBLIC_KEY
PresharedKey = $PSK
AllowedIPs = $CLIENT_IP/32
EOF
chmod 600 "$BASE/config/awg0.conf"

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
I1 = <r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>

[Peer]
PublicKey = $SERVER_PUBLIC_KEY
PresharedKey = $PSK
Endpoint = $PUBLIC_IP:$PORT
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
chmod 600 "$BASE/clients/keenetic-awg2.conf"

# Enable IPv4 forwarding on the host. Container NAT remains isolated from awg0.
sysctl -w net.ipv4.ip_forward=1 >/dev/null
printf '%s\n' 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-keenetic-awg2.conf

# Host firewall: only the dedicated UDP port is opened.
iptables -C INPUT -p udp --dport "$PORT" -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport "$PORT" -j ACCEPT

# Do not create a second container over an existing one.
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null
fi

docker run -d \
  --name "$CONTAINER" \
  --restart always \
  --privileged \
  --cap-add=NET_ADMIN \
  -p "$PORT:$PORT/udp" \
  -v "$BASE/config:/opt/amnezia/awg" \
  "$CONTAINER:awg2"

sleep 3
if ! docker exec "$CONTAINER" awg show awg0 >/dev/null 2>&1; then
  echo 'AWG 2.0 container failed to start.'
  docker logs "$CONTAINER" 2>&1 | tail -80 || true
  exit 1
fi

cat >"$BASE/README.txt" <<EOF
NOVA Keenetic AWG 2.0 bridge
============================
Container: $CONTAINER
UDP port: $PORT
Server subnet: $SUBNET
Client config: $BASE/clients/keenetic-awg2.conf

This is a separate userspace AWG 2.0 endpoint. The existing NOVA AWG 3.1 awg0 interface is not modified.
KeeneticOS 5.1+ can import the generated .conf. For selective routing, use the NOVA Keenetic route generator and select this VPN interface.
EOF

cat >/etc/systemd/system/keenetic-awg2.service <<EOF
[Unit]
Description=NOVA isolated AmneziaWG 2.0 bridge for Keenetic
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker start $CONTAINER
ExecStop=/usr/bin/docker stop -t 10 $CONTAINER
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable keenetic-awg2.service >/dev/null

printf '\nKeenetic AWG 2.0 bridge installed.\n'
printf 'Config: %s\n' "$BASE/clients/keenetic-awg2.conf"
printf 'Endpoint: %s:%s/udp\n' "$PUBLIC_IP" "$PORT"
printf 'Container: %s\n' "$CONTAINER"
printf 'Existing AWG 3.1: untouched\n'
