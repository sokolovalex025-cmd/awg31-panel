#!/usr/bin/env bash
set -euo pipefail

ENV=/etc/awg31-panel/network.env
CONF=/etc/amnezia/amneziawg/awg0.conf
DNSCONF=/etc/dnsmasq.d/nova-awg.conf

[[ $EUID -eq 0 ]] || { echo "ERROR: run as root"; exit 1; }
[[ -f "$CONF" ]] || { echo "ERROR: $CONF not found"; exit 1; }

IFACE="$(ip route show default | awk 'NR==1{print $5}')"
[[ -n "$IFACE" ]] || { echo "ERROR: default interface not found"; exit 2; }

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

cat >/etc/sysctl.d/99-nova-vpn.conf <<EOF
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=0
net.ipv6.conf.default.forwarding=0
EOF
sysctl --system >/dev/null

iptables -t nat -C POSTROUTING -s "$CLIENT_NET" -o "$IFACE" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s "$CLIENT_NET" -o "$IFACE" -j MASQUERADE
iptables -C FORWARD -i awg0 -o "$IFACE" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i awg0 -o "$IFACE" -j ACCEPT
iptables -C FORWARD -i "$IFACE" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$IFACE" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

if command -v netfilter-persistent >/dev/null 2>&1; then netfilter-persistent save || true; fi

# Always ensure dnsmasq is installed. Do not rely on port 53 detection: another
# resolver (for example systemd-resolved) may listen on a different address.
if ! command -v dnsmasq >/dev/null 2>&1; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq dnsmasq
fi

# The directory may be missing on minimal Ubuntu images. Create it BEFORE the
# redirection below; this is the exact failure fixed by this version.
install -d -m 755 /etc/dnsmasq.d

cat > "$DNSCONF" <<EOF
# NOVA DNS for AWG clients
listen-address=$DNS_IP
bind-interfaces
no-resolv
server=1.1.1.1
server=8.8.8.8
cache-size=1000
EOF
chmod 644 "$DNSCONF"

# Validate configuration before restarting the resolver.
dnsmasq --test

if ! systemctl restart dnsmasq; then
  echo "ERROR: dnsmasq failed to start. Diagnostics:"
  systemctl --no-pager --full status dnsmasq || true
  journalctl -u dnsmasq -n 40 --no-pager || true
  exit 3
fi

if ! ss -lunpt 2>/dev/null | grep -qE "${DNS_IP//./\\.}:53([[:space:]]|$)"; then
  echo "WARNING: dnsmasq restarted, but $DNS_IP:53 was not found in socket list."
fi

if ! grep -q '^# NOVA_DNS=' "$CONF"; then
  sed -i "1i# NOVA_DNS=$DNS_IP" "$CONF"
fi

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
IPv6:       forwarding disabled
DNS:        local dnsmasq -> 1.1.1.1 / 8.8.8.8

Clients should use $DNS_IP as DNS. Public resolvers above are upstream only.
EOF
