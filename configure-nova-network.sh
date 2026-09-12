#!/usr/bin/env bash
set -euo pipefail

ENV=/etc/awg31-panel/network.env
CONF=/etc/amnezia/amneziawg/awg0.conf

[[ -f "$CONF" ]] || { echo "ERROR: $CONF not found"; exit 1; }

IFACE="$(ip route show default | awk 'NR==1{print $5}')"
[[ -n "$IFACE" ]] || { echo "ERROR: default interface not found"; exit 2; }

# Detect tunnel subnet from Address= or fall back to the panel's known subnet.
SUBNET="$(awk -F= '/^[[:space:]]*Address[[:space:]]*=/{gsub(/[[:space:]]/,"",$2); print $2; exit}' "$CONF" | cut -d/ -f1)"
SUBNET="${SUBNET:-10.66.66.1}"
PREFIX="$(echo "$SUBNET" | awk -F. '{print $1"."$2"."$3}')"
CLIENT_NET="${PREFIX}.0/24"
DNS_IP="$SUBNET"

install -d -m 700 /etc/awg31-panel
cat > "$ENV" <<EOF
VPN_PUBLIC_INTERFACE=$IFACE
VPN_CLIENT_NETWORK=$CLIENT_NET
VPN_DNS=$DNS_IP
VPN_FULL_TUNNEL=1
VPN_DISABLE_IPV6_LEAK=1
EOF
chmod 600 "$ENV"

# Enable IPv4 forwarding. Disable IPv6 forwarding so client IPv6 cannot escape outside AWG.
cat >/etc/sysctl.d/99-nova-vpn.conf <<EOF
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=0
net.ipv6.conf.default.forwarding=0
EOF
sysctl --system >/dev/null

# NAT + forwarding for VPN clients. Rules are idempotent.
iptables -t nat -C POSTROUTING -s "$CLIENT_NET" -o "$IFACE" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "$CLIENT_NET" -o "$IFACE" -j MASQUERADE
iptables -C FORWARD -i awg0 -o "$IFACE" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i awg0 -o "$IFACE" -j ACCEPT
iptables -C FORWARD -i "$IFACE" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$IFACE" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

if command -v netfilter-persistent >/dev/null 2>&1; then netfilter-persistent save || true; fi

# Install a small local DNS forwarder if none is listening on the tunnel address.
if ! ss -lunpt 2>/dev/null | grep -qE '(:53[[:space:]]|:53$)'; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq dnsmasq
fi

DNSCONF=/etc/dnsmasq.d/nova-awg.conf
cat > "$DNSCONF" <<EOF
# NOVA DNS for AWG clients
listen-address=$DNS_IP
bind-interfaces
no-resolv
server=1.1.1.1
server=8.8.8.8
cache-size=1000
EOF
systemctl restart dnsmasq

# Store the chosen DNS only in local server config; never put credentials here.
chmod 600 "$DNSCONF"

# Add a DNS comment/marker to make the server setting visible to diagnostics.
if ! grep -q '^# NOVA_DNS=' "$CONF"; then
  sed -i "1i# NOVA_DNS=$DNS_IP" "$CONF"
fi

# Reload AWG without touching the 3.1 obfuscation values.
if systemctl is-active --quiet awg-quick@awg0; then
  awg-quick strip awg0 >/tmp/nova-awg.strip
  awg syncconf awg0 /tmp/nova-awg.strip
fi

cat <<EOF

NOVA network setup complete.
Interface:  $IFACE
Client net: $CLIENT_NET
VPN DNS:    $DNS_IP
Full IPv4:  0.0.0.0/0
IPv6:       forwarding disabled (no IPv6 egress outside AWG)
DNS:        dnsmasq -> 1.1.1.1 / 8.8.8.8

NOTE: 1.1.1.1 and 8.8.8.8 are upstream resolvers only; clients query the VPN DNS address.
EOF
