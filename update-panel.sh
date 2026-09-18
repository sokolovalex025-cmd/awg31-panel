#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
PANEL_REF="${PANEL_REF:-main}"
BASE=/opt/awg31-panel

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 --branch "$PANEL_REF" "$REPO_URL" "$REPO_DIR"
else
  git -C "$REPO_DIR" fetch origin "$PANEL_REF"
  git -C "$REPO_DIR" checkout -B "$PANEL_REF" "origin/$PANEL_REF"
  git -C "$REPO_DIR" reset --hard "origin/$PANEL_REF"
fi

echo "NOVA deploy ref: $PANEL_REF"
echo "NOVA commit: $(git -C "$REPO_DIR" rev-parse --short HEAD)"

python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --upgrade pip
"$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]' pytest
mkdir -p "$BASE/backups"
for f in app.py app9.py nova11.py nova11_fixes.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py nova15_theme.py nova16_server_card_fix.py nova_scroll_buttons.py nova_awg31_fix.py antiblock.py nova_shield.py nova_resilience.py nova_doctor_ui.py nova_diagnostics.py nova12_diagnostics.py nova_mobile_diagnostics3.py nova_mobile_monitor.py nova12_clients.py nova12_ui.py domain_manager.py naiveproxy_panel.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py telegram_payments.py system_panel.py mobile_nav.py security_hardening.py keenetic.py balancer.py balancer_provision.py nova_mobile_diagnostics.py nova_command_center.py background.svg keenetic-routing-guide.txt nova-network-fix.sh nova-max-backup.sh nova-migrate.sh nova-verify.sh nova-watchdog.sh nova-watchdog.service nova-watchdog.timer; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
if ! grep -q 'nova_command_center' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova_command_center; nova_command_center.apply(nova11); print('NOVA Command Center: READY',flush=True)
except Exception as e: print('NOVA Command Center disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova_doctor_ui' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova_doctor_ui; nova_doctor_ui.apply(nova11); print('NOVA Doctor UI: READY',flush=True)
except Exception as e: print('NOVA Doctor UI disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova_diagnostics' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova_diagnostics; nova_diagnostics.apply(nova11); print('NOVA Diagnostics: FULL',flush=True)
except Exception as e: print('NOVA Diagnostics disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova11_fixes' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova11_fixes; nova11_fixes.apply(); print('NOVA 11.1 fixes: READY',flush=True)
except Exception as e: print('NOVA 11.1 fixes disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova12_diagnostics' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova12_diagnostics; nova12_diagnostics.apply(nova11); print('NOVA 12 Mobile Diagnostics: READY',flush=True)
except Exception as e: print('NOVA 12 Mobile Diagnostics disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova_mobile_diagnostics3' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova_mobile_diagnostics3; nova_mobile_diagnostics3.apply(nova11); print('NOVA Mobile Diagnostics 3.0: READY',flush=True)
except Exception as e: print('NOVA Mobile Diagnostics 3.0 disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova_mobile_monitor' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova_mobile_monitor; nova_mobile_monitor.apply(nova11); print('NOVA Live Monitor: READY',flush=True)
except Exception as e: print('NOVA Live Monitor disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova12_clients' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova12_clients; nova12_clients.apply(nova11.core); print('NOVA 12 Client Profiles: READY',flush=True)
except Exception as e: print('NOVA 12 Client Profiles disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
if ! grep -q 'nova12_ui' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11.core.app.run/i\try:
    import nova12_ui; nova12_ui.apply(nova11); print('NOVA 12 UI: READY',flush=True)
except Exception as e: print('NOVA 12 UI disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
fi
chmod 755 "$BASE/nova_awg31_fix.py" "$BASE/nova-network-fix.sh" "$BASE/nova-max-backup.sh" "$BASE/nova-migrate.sh" "$BASE/nova-verify.sh" "$BASE/panel_bootstrap.py" "$BASE/nova-watchdog.sh"
install -m 644 "$BASE/nova-watchdog.service" /etc/systemd/system/nova-watchdog.service
install -m 644 "$BASE/nova-watchdog.timer" /etc/systemd/system/nova-watchdog.timer
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE"/*.py
"$REPO_DIR/venv/bin/python" "$BASE/nova_awg31_fix.py"
systemctl daemon-reload
systemctl enable --now nova-watchdog.timer
systemctl restart awg31-network.service 2>/dev/null || true
systemctl restart awgpanel.service
sleep 2
systemctl is-active --quiet awgpanel.service
curl -fsS --max-time 8 http://127.0.0.1:8080/login >/dev/null
systemctl restart awgpanel-telegram.service 2>/dev/null || true
systemctl restart nginx.service 2>/dev/null || true
"$BASE/nova_awg31_fix.py" check
"$BASE/nova-verify.sh"
echo
echo 'NOVA PANEL UPDATE: SUCCESS'
echo "NOVA Deploy Ref: $PANEL_REF"
echo "NOVA Deploy Commit: $(git -C "$REPO_DIR" rev-parse --short HEAD)"
echo 'NOVA Doctor: /doctor'
echo 'NOVA Diagnostics: FULL /diagnostics + /api/nova/diagnostics/full'
echo 'NOVA Mobile Diagnostics 2.0: /mobile-diagnostics'
echo 'NOVA Mobile Diagnostics 3.0: /mobile-diagnostics-v3'
echo 'NOVA Live Monitor: /live-monitor'
echo 'NOVA Client Profiles 2.0: canonical AWG 3.1 parameters'
echo 'NOVA UI 12.0: mobile diagnostics navigation + version identity'
echo 'NOVA Watchdog: every minute'
echo 'NOVA Sidebar Controls: UP/DOWN'
echo 'NOVA Command Center: READY'
echo 'NOVA 11.1 compatibility fixes: READY'
echo 'Telegram Bot: UPDATED'
echo 'AWG 3.1 configuration was migrated and checked.'
