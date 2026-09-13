#!/bin/sh
# NOVA Keenetic VPS Route Updater
# Requires KeeneticOS + Entware/Opkg with ndmc and wget/curl.
# Usage: keenetic-route-updater.sh [feed_url] [policy_name] [interface]
set -eu

FEED_URL="${1:-${NOVA_FEED_URL:-}}"
POLICY="${2:-${NOVA_POLICY:-NOVA-Keenetic}}"
IFACE="${3:-${NOVA_IFACE:-awg-keenetic}}"
STATE="${NOVA_ROUTE_STATE:-/opt/etc/nova-routes.state}"
LOCK="${NOVA_ROUTE_LOCK:-/opt/var/run/nova-routes.lock}"

[ -n "$FEED_URL" ] || { echo "Usage: $0 FEED_URL [POLICY] [INTERFACE]" >&2; exit 2; }
command -v ndmc >/dev/null 2>&1 || { echo "ndmc not found. Install/enable Entware integration first." >&2; exit 1; }

if command -v curl >/dev/null 2>&1; then
    FETCH="curl -fsSL --max-time 20"
elif command -v wget >/dev/null 2>&1; then
    FETCH="wget -qO- --timeout=20"
else
    echo "curl or wget is required." >&2
    exit 1
fi

mkdir -p "$(dirname "$STATE")" "$(dirname "$LOCK")"
if ! (set -C; : > "$LOCK") 2>/dev/null; then
    echo "Another NOVA route update is already running."
    exit 0
fi
trap 'rm -f "$LOCK"' EXIT INT TERM

TMP="${STATE}.new"
OLD="${STATE}.old"
trap 'rm -f "$TMP" "$OLD"' EXIT INT TERM

# Feed is intentionally plain text: one IPv4 CIDR per line. Ignore comments/blank lines.
$FETCH "$FEED_URL" > "$TMP"

VALID="${TMP}.valid"
awk '
    /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
    { gsub(/[[:space:]]/, "", $0); print }
' "$TMP" | while IFS= read -r route; do
    case "$route" in
        */*)
            ip="${route%/*}"; prefix="${route#*/}"
            oldIFS="$IFS"; IFS=.; set -- $ip; IFS="$oldIFS"
            [ "$#" -eq 4 ] || continue
            case "$prefix" in *[!0-9]*|'') continue;; esac
            [ "$prefix" -ge 0 ] 2>/dev/null && [ "$prefix" -le 32 ] 2>/dev/null || continue
            good=1
            for oct in "$@"; do
                case "$oct" in *[!0-9]*|'') good=0;; esac
                [ "$oct" -ge 0 ] 2>/dev/null && [ "$oct" -le 255 ] 2>/dev/null || good=0
            done
            [ "$good" -eq 1 ] && echo "$route"
            ;;
    esac
done | sort -u > "$VALID"

[ -s "$VALID" ] || { echo "Feed contains no valid IPv4 routes; refusing to change routes." >&2; exit 1; }

# State contains only routes previously managed by this updater. We never delete
# routes that were not created by NOVA.
touch "$STATE"
cp "$STATE" "$OLD"

# Remove routes that disappeared from the VPS feed.
while IFS= read -r route; do
    [ -n "$route" ] || continue
    if ! grep -Fxq "$route" "$VALID"; then
        network="${route%/*}"; prefix="${route#*/}"
        # Keenetic CLI accepts prefix notation for policy-specific routes.
        ndmc -c "no ip policy $POLICY route $network/$prefix $IFACE" >/dev/null 2>&1 || true
    fi
done < "$OLD"

# Add current routes. Re-adding existing routes is harmless, but skip known state
# to reduce CLI traffic.
while IFS= read -r route; do
    [ -n "$route" ] || continue
    if ! grep -Fxq "$route" "$OLD"; then
        network="${route%/*}"; prefix="${route#*/}"
        if ! ndmc -c "ip policy $POLICY route $network/$prefix $IFACE auto" >/dev/null 2>&1; then
            echo "Failed to add route $route to policy $POLICY via $IFACE" >&2
            exit 1
        fi
    fi
done < "$VALID"

mv "$VALID" "$STATE"
chmod 600 "$STATE" 2>/dev/null || true
ndmc -c 'system configuration save' >/dev/null 2>&1 || true

echo "NOVA routes updated: $(wc -l < "$STATE" | tr -d ' ') routes; policy=$POLICY interface=$IFACE"
