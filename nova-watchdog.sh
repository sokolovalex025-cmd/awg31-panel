#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
LOG=/var/log/nova-watchdog.log
mkdir -p "$(dirname "$LOG")"
log(){ printf '%s %s\n' "$(date -Is)" "$*" >> "$LOG"; }
restart_if_down(){ local svc="$1"; if ! systemctl is-active --quiet "$svc"; then log "DOWN $svc -> restart"; systemctl restart "$svc" || log "FAILED restart $svc"; else log "OK $svc"; fi; }
restart_if_down awg-quick@awg0.service
restart_if_down awgpanel.service
restart_if_down nginx.service
if command -v awg >/dev/null 2>&1 && ! awg show awg0 >/dev/null 2>&1; then
  log "AWG interface unhealthy -> guarded migration/check"
  "$BASE/venv/bin/python" "$BASE/nova_awg31_fix.py" check >/dev/null 2>&1 || "$BASE/venv/bin/python" "$BASE/nova_awg31_fix.py" >> "$LOG" 2>&1 || log "AWG guarded repair failed"
fi
