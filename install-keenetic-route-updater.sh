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

if [ "${PANEL_URL%/}" = "" ]; then exit 2; fi
FEED_URL="${PANEL_URL%/}/keenetic/routes/feed?service=all"

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

SRC="${PANEL_URL%/}/keenetic/routes/updater.sh"
if command -v curl >/dev/null 2>&1; then
    curl -fsSL --max-time 30 "$SRC" -o "$SCRIPT"
elif command -v wget >/dev/null 2>&1; then
    wget -qO "$SCRIPT" "$SRC"
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

# Prefer Entware cron. If it is not running yet, create a self-contained
# scheduler using the configured interval and the normal Entware rc.d hook.
INIT="/opt/etc/init.d/S99nova-routes"
cat > "$INIT" <<EOF
#!/bin/sh
# NOVA automatic VPS route updater
ENABLED=yes
. /opt/etc/init.d/rc.func

case "\$1" in
  start)
    start-stop-daemon --start --background --make-pidfile --pidfile /opt/var/run/nova-routes.pid --exec /bin/sh -- -c 'while :; do /opt/etc/nova-route-updater/nova-route-cron.sh; sleep '"$INTERVAL"'; done'
    ;;
  stop)
    if [ -f /opt/var/run/nova-routes.pid ]; then
      kill "$(cat /opt/var/run/nova-routes.pid)" 2>/dev/null || true
      rm -f /opt/var/run/nova-routes.pid
    fi
    ;;
  restart)
    "\$0" stop
    "\$0" start
    ;;
  status)
    if [ -f /opt/var/run/nova-routes.pid ] && kill -0 "$(cat /opt/var/run/nova-routes.pid)" 2>/dev/null; then echo running; else echo stopped; fi
    ;;
esac
EOF
chmod 700 "$INIT"

# Run once immediately so errors are visible during installation.
"$CRON"
"$INIT" stop >/dev/null 2>&1 || true
"$INIT" start

echo "NOVA automatic routes installed."
echo "Feed: $FEED_URL"
echo "Policy: $POLICY"
echo "Interface: $IFACE"
echo "Interval: ${INTERVAL}s"
echo "State: /opt/etc/nova-routes.state"
echo "Log: /opt/var/log/nova-route-updater.log"
