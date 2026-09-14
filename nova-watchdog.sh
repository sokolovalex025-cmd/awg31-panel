#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel; REPO=/root/awg31-panel; LOG=/var/log/nova-watchdog.log
mkdir -p "$(dirname "$LOG")"
log(){ printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
restart_if_down(){ local svc="$1"; if ! systemctl is-active --quiet "$svc"; then log "DOWN $svc -> restart"; systemctl restart "$svc" || log "FAILED restart $svc"; fi; }
restart_if_down awg-quick@awg0.service
restart_if_down awgpanel.service
restart_if_down nginx.service
PY="$REPO/venv/bin/python"; [ -x "$PY" ] || PY=python3
if command -v awg >/dev/null 2>&1 && ! awg show awg0 >/dev/null 2>&1; then
 log "AWG interface unhealthy -> guarded check/repair"
 "$PY" "$BASE/nova_awg31_fix.py" check >/dev/null 2>&1 || "$PY" "$BASE/nova_awg31_fix.py" >> "$LOG" 2>&1 || log "AWG guarded repair failed"
fi
