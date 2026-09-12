#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/awg31-panel
APP="$BASE/app.py"
CONF=/etc/amnezia/amneziawg/awg0.conf
ENV=/etc/awg31-panel/network.env
BACKUP="$APP.bak-full-tunnel-$(date +%Y%m%d-%H%M%S)"

[[ -f "$APP" ]] || { echo "ERROR: $APP not found"; exit 1; }
cp -a "$APP" "$BACKUP"

# Detect the public interface and tunnel address. Do not hard-code eth0/ens3.
PUBLIC_IF="$(ip route show default | awk 'NR==1 {print $5}')"
[[ -n "$PUBLIC_IF" ]] || { echo "ERROR: cannot detect default network interface"; exit 2; }
TUNNEL_IP="$(awk -F= '/^[[:space:]]*Address[[:space:]]*=/{gsub(/[[:space:]]/,"",$2); print $2; exit}' "$CONF" 2>/dev/null || true)"
TUNNEL_IP="${TUNNEL_IP%%/*}"
[[ -n "$TUNNEL_IP" ]] || TUNNEL_IP=10.66.66.1

# Use the tunnel gateway as DNS. systemd-resolved/dnsmasq is not assumed to be present;
# the panel can still generate a client DNS value and the installer enables forwarding/NAT.
cat > "$ENV" <<EOF
# NOVA VPN network settings
VPN_PUBLIC_INTERFACE=$PUBLIC_IF
VPN_DNS=$TUNNEL_IP
VPN_TUNNEL_ADDRESS=$TUNNEL_IP
VPN_FULL_TUNNEL=1
VPN_DISABLE_IPV6_LEAK=1
EOF
chmod 600 "$ENV"

# Kernel forwarding and IPv6 leak protection. IPv6 is disabled for forwarding rather than
# silently routed outside the tunnel. Existing native IPv6 on the host is left untouched.
cat >/etc/sysctl.d/99-nova-vpn.conf <<EOF
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=0
net.ipv6.conf.default.forwarding=0
EOF
sysctl --system >/dev/null

# NAT for AWG clients. Avoid duplicate rules.
if command -v iptables >/dev/null 2>&1; then
  iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$PUBLIC_IF" -j MASQUERADE 2>/dev/null || \
    iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$PUBLIC_IF" -j MASQUERADE
  iptables -C FORWARD -i awg0 -o "$PUBLIC_IF" -j ACCEPT 2>/dev/null || \
    iptables -A FORWARD -i awg0 -o "$PUBLIC_IF" -j ACCEPT
  iptables -C FORWARD -i "$PUBLIC_IF" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || \
    iptables -A FORWARD -i "$PUBLIC_IF" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
fi

# Make iptables rules persistent when netfilter-persistent is available.
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save || true
fi

# Patch the client config template in app.py. The existing generator uses a Python f-string;
# this replacement targets the exact AllowedIPs/DNS lines without rewriting the rest of the panel.
python3 - "$APP" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
orig=s
# Full IPv4 tunnel and VPN-side DNS. Existing MTU/AWG 3.1 parameters are untouched.
s=re.sub(r"DNS\\s*=\\s*[^\\n]+", "DNS = 10.66.66.1", s)
s=re.sub(r"AllowedIPs\\s*=\\s*[^\\n]+", "AllowedIPs = 0.0.0.0/0", s)
if s==orig:
    print('WARNING: no DNS/AllowedIPs template strings found; app.py was only backed up.')
else:
    p.write_text(s)
    print('Updated client DNS/AllowedIPs template.')
PY

# Compile check before restarting anything.
python3 -m py_compile "$APP"

systemctl restart awg-quick@awg0 2>/dev/null || true
systemctl restart awgpanel.service 2>/dev/null || true

cat <<EOF

NOVA full-tunnel configuration applied.
Public interface: $PUBLIC_IF
VPN DNS:          $TUNNEL_IP
IPv4 AllowedIPs:  0.0.0.0/0
IPv6 forwarding:  disabled to prevent IPv6 bypass
Backup:           $BACKUP

IMPORTANT: the VPS must provide a DNS service reachable at $TUNNEL_IP:53/udp+tcp.
If no DNS service is listening there, clients will have no DNS resolution. The next NOVA
step should install/configure a local DNS resolver (for example dnsmasq/unbound) on awg0.
EOF
