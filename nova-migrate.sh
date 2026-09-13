#!/usr/bin/env bash
set -Eeuo pipefail

BASE=/opt/awg31-panel
STAMP=$(date +%Y%m%d-%H%M%S)
OUT_DIR=${OUT_DIR:-/root/nova-migrations}
BUNDLE=${BUNDLE:-$OUT_DIR/nova-migration-$STAMP.tar.gz.enc}
TMP=$(mktemp -d)
cleanup(){ rm -rf "$TMP"; }
trap cleanup EXIT

need_root(){ [ "$(id -u)" -eq 0 ] || { echo 'Run as root.' >&2; exit 1; }; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || { echo "Missing command: $1" >&2; exit 2; }; }

collect(){
  mkdir -p "$TMP/files/etc/awg31-panel" "$TMP/files/etc/systemd/system" "$TMP/files/etc/nginx/sites-available" "$TMP/files/etc/amnezia/amneziawg" "$TMP/files/etc/wireguard" "$TMP/files/opt/awg31-panel"
  cp -a "$BASE/panel.db" "$TMP/files/opt/awg31-panel/" 2>/dev/null || true
  cp -a "$BASE"/*.py "$TMP/files/opt/awg31-panel/" 2>/dev/null || true
  cp -a "$BASE"/*.svg "$TMP/files/opt/awg31-panel/" 2>/dev/null || true
  cp -a "$BASE"/*.sh "$TMP/files/opt/awg31-panel/" 2>/dev/null || true
  cp -a /etc/awg31-panel/panel-secret "$TMP/files/etc/awg31-panel/" 2>/dev/null || true
  cp -a /etc/awg31-panel/telegram.env "$TMP/files/etc/awg31-panel/" 2>/dev/null || true
  cp -a /etc/amnezia/amneziawg/awg0.conf "$TMP/files/etc/amnezia/amneziawg/" 2>/dev/null || true
  cp -a /etc/wireguard/awg0.conf "$TMP/files/etc/wireguard/" 2>/dev/null || true
  for f in awgpanel.service awgpanel-telegram.service awg31-network.service; do
    cp -a "/etc/systemd/system/$f" "$TMP/files/etc/systemd/system/" 2>/dev/null || true
  done
  cp -a /etc/nginx/sites-available/awg31-panel "$TMP/files/etc/nginx/sites-available/" 2>/dev/null || true
  if command -v awg >/dev/null 2>&1; then awg show awg0 > "$TMP/awg0-show.txt" 2>&1 || true; fi
  ip -brief addr > "$TMP/ip-brief.txt" 2>&1 || true
  ip route > "$TMP/ip-route.txt" 2>&1 || true
  systemctl --no-pager --plain status awg-quick@awg0.service > "$TMP/awg0-service.txt" 2>&1 || true
  cat > "$TMP/MIGRATION-INFO.txt" <<EOF
NOVA MAX migration bundle
Created: $(date -Is)
Source hostname: $(hostname)
Source IPv4: $(curl -4fsS --max-time 3 https://api.ipify.org 2>/dev/null || echo unknown)

This bundle is encrypted and contains server-side configuration and client keys.
Import it only on a VPS you control.

IMPORTANT: the destination must have AmneziaWG installed before import.
The import intentionally does not copy OS package state or arbitrary files.
EOF
}

export_bundle(){
  need_root; need_cmd tar; need_cmd openssl; need_cmd gzip
  mkdir -p "$OUT_DIR"
  collect
  tar -C "$TMP" -czf "$TMP/payload.tar.gz" .
  umask 077
  echo 'Create a strong password for this migration bundle.'
  openssl enc -aes-256-cbc -pbkdf2 -salt -iter 200000 -in "$TMP/payload.tar.gz" -out "$BUNDLE"
  chmod 600 "$BUNDLE"
  sha256sum "$BUNDLE" > "$BUNDLE.sha256"
  echo
  echo "Migration bundle: $BUNDLE"
  echo "Checksum:         $BUNDLE.sha256"
  echo
  echo 'Copy BOTH files to the destination VPS.'
}

restore_file(){
  local src="$1" rel="$2" dst="$3"
  if [ -f "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  fi
}

validate(){
  need_root
  need_cmd systemctl
  need_cmd awg
  echo '=== NOVA migration preflight ==='
  command -v python3 >/dev/null && python3 --version
  awg --version 2>&1 | head -n 1 || true
  if [ -f /etc/amnezia/amneziawg/awg0.conf ]; then CONF=/etc/amnezia/amneziawg/awg0.conf; elif [ -f /etc/wireguard/awg0.conf ]; then CONF=/etc/wireguard/awg0.conf; else echo 'ERROR: awg0.conf not found'; return 1; fi
  echo "Config: $CONF"
  grep -E '^(ListenPort|MTU|PrivateKey|Jc|Jmin|Jmax|S1|S2|S3|S4|H1|H2|H3|H4|I1|I2|I3|I4|I5|RandomizedPacketHeader|RandomTrailers|DisableCookies)' "$CONF" | sed 's/^PrivateKey=.*/PrivateKey=<redacted>/' || true
  echo
  if systemctl is-active --quiet awg-quick@awg0.service; then echo 'AWG0: ACTIVE'; else echo 'AWG0: INACTIVE'; fi
  if [ -f "$BASE/panel.db" ]; then echo 'panel.db: PRESENT'; else echo 'panel.db: MISSING'; fi
  echo 'Preflight complete.'
}

import_bundle(){
  need_root; need_cmd tar; need_cmd openssl; need_cmd gzip
  [ $# -eq 1 ] || { echo "Usage: $0 import BUNDLE.tar.gz.enc" >&2; exit 2; }
  local bundle="$1"
  [ -f "$bundle" ] || { echo "Bundle not found: $bundle" >&2; exit 2; }
  mkdir -p /root/nova-migrations
  if [ -f "$bundle.sha256" ]; then (cd "$(dirname "$bundle")" && sha256sum -c "$(basename "$bundle.sha256")"); fi
  echo 'Enter the migration bundle password.'
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in "$bundle" -out "$TMP/payload.tar.gz"
  tar -C "$TMP" -xzf "$TMP/payload.tar.gz"
  [ -f "$TMP/files/opt/awg31-panel/panel.db" ] || { echo 'Invalid bundle: panel.db missing.' >&2; exit 3; }

  TS=$(date +%Y%m%d-%H%M%S); SAVE=/root/nova-migrations/pre-import-$TS; mkdir -p "$SAVE"
  for p in /opt/awg31-panel/panel.db /etc/awg31-panel/panel-secret /etc/awg31-panel/telegram.env /etc/amnezia/amneziawg/awg0.conf /etc/wireguard/awg0.conf /etc/nginx/sites-available/awg31-panel; do
    [ -e "$p" ] && cp -a "$p" "$SAVE/" || true
  done

  systemctl stop awgpanel-telegram.service 2>/dev/null || true
  systemctl stop awgpanel.service 2>/dev/null || true
  systemctl stop awg-quick@awg0.service 2>/dev/null || true

  mkdir -p "$BASE" /etc/awg31-panel
  cp -a "$TMP/files/opt/awg31-panel/." "$BASE/"
  restore_file "$TMP/files/etc/awg31-panel/panel-secret" panel-secret /etc/awg31-panel/panel-secret
  restore_file "$TMP/files/etc/awg31-panel/telegram.env" telegram.env /etc/awg31-panel/telegram.env
  if [ -f "$TMP/files/etc/amnezia/amneziawg/awg0.conf" ]; then
    mkdir -p /etc/amnezia/amneziawg; cp -a "$TMP/files/etc/amnezia/amneziawg/awg0.conf" /etc/amnezia/amneziawg/awg0.conf
  elif [ -f "$TMP/files/etc/wireguard/awg0.conf" ]; then
    mkdir -p /etc/wireguard; cp -a "$TMP/files/etc/wireguard/awg0.conf" /etc/wireguard/awg0.conf
  fi
  restore_file "$TMP/files/etc/nginx/sites-available/awg31-panel" nginx-awg31-panel /etc/nginx/sites-available/awg31-panel
  chmod 600 /etc/awg31-panel/panel-secret 2>/dev/null || true
  chmod 600 /etc/awg31-panel/telegram.env 2>/dev/null || true

  systemctl daemon-reload
  nginx -t
  systemctl start awg-quick@awg0.service
  systemctl start awg31-network.service 2>/dev/null || true
  systemctl start awgpanel.service
  sleep 2
  systemctl is-active --quiet awgpanel.service
  curl -fsS --max-time 8 http://127.0.0.1:8080/login >/dev/null
  systemctl start awgpanel-telegram.service 2>/dev/null || true
  systemctl reload nginx 2>/dev/null || true

  echo
  echo 'NOVA migration import completed.'
  echo "Pre-import backup: $SAVE"
  echo
  echo 'NEXT STEP: set the NEW server endpoint/IP in NOVA before distributing new client configs.'
  echo 'The AWG server configuration was restored exactly from the source bundle.'
}

usage(){
  echo "Usage: $0 export | import <bundle.tar.gz.enc> | validate"
}

case "${1:-}" in
  export) export_bundle ;;
  import) shift; import_bundle "$@" ;;
  validate) validate ;;
  *) usage; exit 2 ;;
esac
