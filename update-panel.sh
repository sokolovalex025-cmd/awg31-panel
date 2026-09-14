#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"; REPO_DIR="${REPO_DIR:-/root/awg31-panel}"; BASE=/opt/awg31-panel
if [ ! -d "$REPO_DIR/.git" ]; then git clone --depth 1 "$REPO_URL" "$REPO_DIR"; else git -C "$REPO_DIR" fetch origin main; git -C "$REPO_DIR" reset --hard origin/main; fi
python3 -m venv "$REPO_DIR/venv"; "$REPO_DIR/venv/bin/pip" install --upgrade pip; "$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]' pytest
mkdir -p "$BASE/backups"
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py nova15_theme.py nova16_server_card_fix.py nova_scroll_buttons.py nova_awg31_fix.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py keenetic.py balancer.py balancer_provision.py nova_mobile_diagnostics.py nova_command_center.py background.svg nova-network-fix.sh nova-max-backup.sh nova-migrate.sh nova-verify.sh nova-watchdog.sh nova-watchdog.service nova-watchdog.timer; do [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"; done
# Keep the runtime bootstrap compatible with both old and new repository layouts.
if ! grep -q 'nova_command_center' "$BASE/panel_bootstrap.py"; then
  sed -i "/^nova11\.core\.app\.run/i\\try:\n    import nova_command_center; nova_command_center.apply(nova11); print('NOVA Command Center: READY',flush=True)\nexcept Exception as e: print('NOVA Command Center disabled:',e,flush=True)" "$BASE/panel_bootstrap.py"
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
echo 'NOVA Doctor: /doctor'
echo 'NOVA Watchdog: every minute'
echo 'NOVA Sidebar Controls: UP/DOWN'
echo 'NOVA Command Center: READY'
echo 'AWG 3.1 configuration was migrated and checked.'
