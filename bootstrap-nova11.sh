#!/usr/bin/env bash
set -Eeuo pipefail

log(){ printf '\n\033[1;36m[NOVA] %s\033[0m\n' "$*"; }
ok(){ printf '\033[1;32m[ OK ] %s\033[0m\n' "$*"; }
fail(){ printf '\033[1;31m[FAIL] %s\033[0m\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || fail 'Run as root.'
export DEBIAN_FRONTEND=noninteractive
REPO_URL=https://github.com/sokolovalex025-cmd/awg31-panel.git
REPO_DIR=/root/awg31-panel
BASE=/opt/awg31-panel
log 'Waiting for dpkg lock'
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/dpkg/lock >/dev/null 2>&1; do echo '  dpkg is busy; waiting 5s...'; sleep 5; done
dpkg --configure -a || true
log 'Installing base packages'
apt-get update
apt-get install -y ca-certificates curl git python3 python3-venv python3-pip qrencode iproute2 iptables
AWG_INSTALL=/tmp/amneziawg-install.sh
curl -fsSL https://raw.githubusercontent.com/wiresock/amneziawg-install/main/amneziawg-install.sh -o "$AWG_INSTALL"
chmod 700 "$AWG_INSTALL"
if ! command -v awg >/dev/null 2>&1; then
  log 'Installing AmneziaWG'
  AUTO_INSTALL=y ENABLE_IPV6=n SERVER_PORT=1234 CREATE_INITIAL_CLIENT=no bash "$AWG_INSTALL"
  command -v awg >/dev/null 2>&1 || fail 'AmneziaWG installation did not provide awg.'
else ok 'AmneziaWG userspace already installed'; fi
log 'Ensuring AmneziaWG 3.1'
if "$AWG_INSTALL" --protocol-status 2>/dev/null | grep -q '3\.1'; then ok 'AmneziaWG 3.1 enabled'; else bash "$AWG_INSTALL" --enable-awg31 || fail 'Could not enable AmneziaWG 3.1.'; fi
command -v awg >/dev/null 2>&1 || fail 'awg command missing after AWG setup.'
modprobe amneziawg 2>/dev/null || true
log 'Installing NOVA 11 panel'
REPO_URL="$REPO_URL" REPO_DIR="$REPO_DIR" BASE="$BASE" bash <(curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install-nova11.sh)
for f in app.py nova11.py panel_bootstrap.py keenetic.py balancer.py balancer_provision.py; do [ -f "$BASE/$f" ] || fail "Missing panel file: $BASE/$f"; done
[ -x "$REPO_DIR/venv/bin/python" ] || fail "Missing Python venv: $REPO_DIR/venv/bin/python"
log 'Verifying Python modules'
cd "$BASE"
PYTHONPATH="$BASE" "$REPO_DIR/venv/bin/python" - <<'PY'
import sys, importlib
print('[INFO] Python:', sys.executable)
for name in ('app','nova11','keenetic','balancer','balancer_provision','panel_bootstrap'):
    mod=importlib.import_module(name)
    print('[ OK ] import', name, '->', getattr(mod,'__file__','?'))
PY
log 'Verifying AWG'
systemctl is-active --quiet awg-quick@awg0.service || systemctl start awg-quick@awg0.service || true
awg show >/dev/null 2>&1 || fail 'awg show failed.'
ok 'AWG command works'
ip link show awg0 >/dev/null 2>&1 && ok 'awg0 interface exists' || fail 'awg0 interface missing'
log 'Verifying NOVA service'
systemctl is-active --quiet awgpanel || fail 'awgpanel is not active.'
ok 'awgpanel is active'
curl -fsS --max-time 10 http://127.0.0.1:8080/login >/dev/null || fail 'NOVA HTTP check failed.'
ok 'NOVA HTTP :8080 responds'
curl -fsS --max-time 10 http://127.0.0.1:8080/api/nova/health >/dev/null || fail 'NOVA health endpoint failed.'
ok 'NOVA health endpoint responds'
printf '\n\033[1;32m========================================\n NOVA 11 FULL INSTALL COMPLETE\n========================================\033[0m\n'
printf 'Panel:     http://SERVER:8080\nKeenetic:  http://SERVER:8080/keenetic\nHealth:    http://SERVER:8080/api/nova/health\nService:   systemctl status awgpanel\nAWG:       awg show\n'
