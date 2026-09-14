#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
BASE=/opt/awg31-panel
REPO_DIR=${REPO_DIR:-/root/awg31-panel}
FAIL=0
ok(){ printf '  [OK]   %s\n' "$*"; }
bad(){ printf '  [FAIL] %s\n' "$*"; FAIL=1; }
check(){ if "$@" >/dev/null 2>&1; then ok "$*"; else bad "$*"; fi; }

echo '=== NOVA MAX verification ==='
for f in app.py nova11.py panel_bootstrap.py nova14_theme.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py telegram_bot.py telegram_runner.py keenetic.py balancer.py nova_mobile_diagnostics.py nova_awg31_fix.py nova-max-backup.sh nova-migrate.sh; do
  [ -f "$BASE/$f" ] && ok "file $f" || bad "missing $BASE/$f"
done

PY="$REPO_DIR/venv/bin/python"; [ -x "$PY" ] || PY=python3
for f in "$BASE"/*.py; do
  "$PY" -m py_compile "$f" >/dev/null 2>&1 && ok "python syntax $(basename "$f")" || bad "python syntax $(basename "$f")"
done

[ -x "$BASE/nova-migrate.sh" ] && ok 'migration executable' || bad 'migration executable'
[ -x "$BASE/nova-max-backup.sh" ] && ok 'backup executable' || bad 'backup executable'
[ -r /etc/awg31-panel/panel-secret ] && ok 'panel secret present' || bad 'panel secret missing'
[ "$(stat -c '%a' /etc/awg31-panel/panel-secret 2>/dev/null || echo 000)" = 600 ] && ok 'panel secret permissions 600' || bad 'panel secret permissions'

if command -v awg >/dev/null 2>&1; then
  check awg show awg0
else bad 'awg command missing'; fi
check systemctl is-active awgpanel.service
check systemctl is-active nginx.service
check curl -fsS --max-time 8 http://127.0.0.1:8080/login
check curl -fsS --max-time 8 http://127.0.0.1/login
nginx -t >/dev/null 2>&1 && ok 'nginx configuration' || bad 'nginx configuration'

if "$PY" "$BASE/nova_awg31_fix.py" check >/tmp/nova-awg31-check.out 2>&1; then
  ok 'AWG 3.1 live parameters'
else
  bad "AWG 3.1 live parameters: $(tr '\n' ' ' </tmp/nova-awg31-check.out | cut -c1-240)"
fi

if systemctl is-enabled --quiet awgpanel.service; then ok 'awgpanel enabled'; else bad 'awgpanel not enabled'; fi
if systemctl is-enabled --quiet nginx.service; then ok 'nginx enabled'; else bad 'nginx not enabled'; fi

if grep -q "nova_resilience" "$BASE/panel_bootstrap.py"; then ok 'resilience registered'; else bad 'resilience not registered'; fi
if grep -q "nova_shield" "$BASE/panel_bootstrap.py"; then ok 'shield registered'; else bad 'shield not registered'; fi
if grep -q "domain_manager" "$BASE/panel_bootstrap.py"; then ok 'domain manager registered'; else bad 'domain manager not registered'; fi
if grep -q "nova_awg31_fix" "$BASE/panel_bootstrap.py"; then ok 'AWG 3.1 guard registered'; else bad 'AWG 3.1 guard not registered'; fi

printf '\n=== Result ===\n'
if [ "$FAIL" -eq 0 ]; then
  echo 'NOVA MAX verification: PASS'
  echo 'No verification step changes awg0 configuration.'
  exit 0
else
  echo 'NOVA MAX verification: FAIL'
  echo 'Review the failed checks above before using this server.'
  exit 10
fi
