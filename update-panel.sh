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
git -C "$REPO_DIR" clean -fd

echo "NOVA deploy ref: $PANEL_REF"
echo "NOVA commit: $(git -C "$REPO_DIR" rev-parse --short HEAD)"

python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --upgrade pip
"$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]' pytest
mkdir -p "$BASE/backups"
for f in app.py app9.py nova11.py nova11_fixes.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py nova15_theme.py nova16_server_card_fix.py nova_scroll_buttons.py nova_awg31_fix.py antiblock.py nova_shield.py nova_resilience.py nova_doctor_ui.py nova_diagnostics.py nova12_diagnostics.py nova_mobile_diagnostics3.py nova_mobile_monitor.py nova_toolza_center.py awg-toolz-daemon.py awg-toolz.service nova12_clients.py nova_client_center.py nova12_ui.py domain_manager.py naiveproxy_panel.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py telegram_payments.py system_panel.py mobile_nav.py security_hardening.py keenetic.py balancer.py balancer_provision.py nova_mobile_diagnostics.py nova_command_center.py background.svg keenetic-routing-guide.txt nova-network-fix.sh nova-max-backup.sh nova-migrate.sh nova-verify.sh nova-watchdog.sh nova-watchdog.service nova-watchdog.timer; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
# Keep runtime sources exact; never patch Python bootstrap through sed heuristics.
# panel_bootstrap.py is copied verbatim from main above. All feature modules are
# already imported by the canonical bootstrap; do not mutate it with sed.
chmod 755 "$BASE/nova_awg31_fix.py" "$BASE/nova-network-fix.sh" "$BASE/nova-max-backup.sh" "$BASE/nova-migrate.sh" "$BASE/nova-verify.sh" "$BASE/panel_bootstrap.py" "$BASE/nova-watchdog.sh"
install -m 644 "$BASE/nova-watchdog.service" /etc/systemd/system/nova-watchdog.service
install -m 644 "$BASE/nova-watchdog.timer" /etc/systemd/system/nova-watchdog.timer
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE"/*.py
"$REPO_DIR/venv/bin/python" "$BASE/nova_awg31_fix.py"
mkdir -p /etc/awg-toolz
umask 077
[ -s /etc/awg-toolz/token ] || python3 -c "import secrets; print(secrets.token_urlsafe(48))" > /etc/awg-toolz/token
chmod 600 /etc/awg-toolz/token
install -m 644 "$BASE/awg-toolz.service" /etc/systemd/system/awg-toolz.service
chmod 755 "$BASE/awg-toolz-daemon.py"
systemctl daemon-reload
systemctl enable --now nova-watchdog.timer
systemctl enable --now awg-toolz.service
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
echo 'NOVA AWG Toolz daemon: 127.0.0.1:9090 + /awg-toolza'
echo 'NOVA 11.1 compatibility fixes: READY'
echo 'Telegram Bot: UPDATED'
echo 'AWG 3.1 configuration was migrated and checked.'
