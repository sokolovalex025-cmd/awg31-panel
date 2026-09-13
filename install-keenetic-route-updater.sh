#!/bin/sh
# Install NOVA automatic VPS route synchronization on KeeneticOS + Entware.
set -eu

PANEL_URL="${1:-${NOVA_PANEL_URL:-}}"
POLICY="${2:-${NOVA_POLICY:-NOVA-Keenetic}}"
IFACE="${3:-${NOVA_IFACE:-awg-keenetic}}"
INTERVAL="${4:-${NOVA_INTERVAL:-3600}}"
BASE="/opt/etc/nova-route-updater"
SCRIPT="$BASE/keenetic-route-updater.sh"
CONFIG="$BASE/nova-route-updater.conf"
CRON="$BASE/nova-route-cron.sh"

[ -n "$PANEL_URL" ] || { echo "Usage: $0 PANEL_URL [POLICY] [INTERFACE] [INTERVAL_SECONDS]" >&2; exit 2; }
case "$INTERVAL" in *[!0-9]*|'') echo "Interval must be seconds." >&2; exit 2;; esac
[ "$INTERVAL" -ge 300 ] 2>/dev/null || { echo "Minimum interval is 300 seconds." >&2; exit 2; }

FEED_URL="${PANEL_URL%/}/keenetic/routes/feed?service=all"
UPDATER_URL="https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/keenetic-route-updater.sh"

if ! command -v ndmc >/dev/null 2>&1; then
    echo "ndmc is required. This installer is intended for KeeneticOS with Entware/Opkg." >&2
    exit 1
fi

if ! command -v wget >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    echo "Installing wget from Entware..."
    if command -v opkg >/dev/null 2>&1; then
        opkg update >/dev/null 2>&1 || true
        opkg install wget-ssl >/dev/null 2>&1 || opkg install wget >/dev/null 2>&1 || true
    fi
fi

if ! command -v wget >/dev/null 2>&1 && ! command -v curl >/dev/null 2>&1; then
    echo "Could not find wget or curl. Install one with Entware and rerun." >&2
    exit 1
fi

mkdir -p "$BASE"

if command -v curl >/dev/null 2>&1; then
    curl -fsSL --max-time 30 "$UPDATER_URL" -o "$SCRIPT"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$SCRIPT" "$UPDATER_URL"
fi
chmod 700 "$SCRIPT"

cat > "$CONFIG" <<EOF
NOVA_FEED_URL='$FEED_URL'
NOVA_POLICY='$POLICY'
NOVA_IFACE='$IFACE'
NOVA_INTERVAL='$INTERVAL'
EOF
chmod 600 "$CONFIG"

cat > "$CRON" <<'EOF'
#!/bin/sh
set -eu
. /opt/etc/nova-route-updater/nova-route-updater.conf
/opt/etc/nova-route-updater/keenetic-route-updater.sh "$NOVA_FEED_URL" "$NOVA_POLICY" "$NOVA_IFACE" >> /opt/var/log/nova-route-updater.log 2>&1 || true
EOF
chmod 700 "$CRON"

INIT="/opt/etc/init.d/S99nova-routes"
cat > "$INIT" <<EOF
#!/bin/sh
# NOVA automatic VPS route updater
PID=/opt/var/run/nova-routes.pid
case "\$1" in
  start)
    if [ -f "\$PID" ] && kill -0 "\$(cat "\$PID")" 2>/dev/null; then exit 0; fi
    start-stop-daemon --start --background --make-pidfile --pidfile "\$PID" --exec /bin/sh -- -c 'while :; do /opt/etc/nova-route-updater/nova-route-cron.sh; sleep $INTERVAL; done'
    ;;
  stop)
    if [ -f "\$PID" ]; then kill "\$(cat "\$PID")" 2>/dev/null || true; rm -f "\$PID"; fi
    ;;
  restart)
    "\$0" stop
    "\$0" start
    ;;
  status)
    if [ -f "\$PID" ] && kill -0 "\$(cat "\$PID")" 2>/dev/null; then echo running; else echo stopped; fi
    ;;
esac
EOF
chmod 700 "$INIT"

# Run once immediately so feed/policy/interface errors are visible.
"$CRON"
"$INIT" stop >/dev/null 2>&1 || true
"$INIT" start

printf '%s\n' "NOVA automatic routes installed." "Feed: $FEED_URL" "Policy: $POLICY" "Interface: $IFACE" "Interval: ${INTERVAL}s" "State: /opt/etc/nova-routes.state" "Log: /opt/var/log/nova-route-updater.log"
