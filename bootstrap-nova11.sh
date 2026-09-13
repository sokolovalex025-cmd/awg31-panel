#!/usr/bin/env bash
set -Eeuo pipefail

# NOVA 11 full bootstrap for a clean Ubuntu/Debian VPS.
# Installs prerequisites, AmneziaWG 3.1, NOVA 11 panel and verifies components.

log(){ printf '\n\033[1;36m[NOVA] %s\033[0m\n' "$*"; }
ok(){ printf '\033[1;32m[ OK ] %s\033[0m\n' "$*"; }
fail(){ printf '\033[1;31m[FAIL] %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || fail 'Run as root.'

export DEBIAN_FRONTEND=noninteractive
log 'Installing base packages'
apt-get update
apt-get install -y ca-certificates curl git python3 python3-venv python3-pip qrencode iproute2 iptables

AWG_INSTALL=/tmp/amneziawg-install.sh
if ! command -v awg >/dev/null 2>&1; then
  log 'Installing AmneziaWG'
  curl -fsSL https://raw.githubusercontent.com/wiresock/amneziawg-install/main/amneziawg-install.sh -o "$AWG_INSTALL"
  chmod 700 "$AWG_INSTALL"
  AUTO_INSTALL=y ENABLE_IPV6=n SERVER_PORT=1234 CREATE_INITIAL_CLIENT=no bash "$AWG_INSTALL"
  command -v awg >/dev/null 2>&1 || fail 'AmneziaWG installation did not provide awg.'
else
  ok 'AmneziaWG userspace already installed'
fi

if "$AWG_INSTALL" --protocol-status 2>/dev/null | grep -q '3\.1'; then
  ok 'AmneziaWG 3.1 already enabled'
elif "$AWG_INSTALL" --protocol-status 2>/dev/null | grep -q '3\.0'; then
  log 'Upgrading AmneziaWG protocol to 3.1'
  bash "$AWG_INSTALL" --enable-awg31
else
  log 'Enabling AmneziaWG 3.1'
  [ -x "$AWG_INSTALL" ] || curl -fsSL https://raw.githubusercontent.com/wiresock/amneziawg-install/main/amneziawg-install.sh -o "$AWG_INSTALL"
  chmod 700 "$AWG_INSTALL"
  bash "$AWG_INSTALL" --enable-awg31
fi

command -v awg >/dev/null 2>&1 || fail 'awg command missing after AWG setup.'
modprobe amneziawg 2>/dev/null || true

log 'Installing NOVA 11 panel'
REPO_URL=https://github.com/sokolovalex025-cmd/awg31-panel.git \
  bash <(curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install-nova11.sh)

log 'Verifying AWG'
systemctl is-active --quiet awg-quick@awg0.service || systemctl start awg-quick@awg0.service || true
awg show >/dev/null 2>&1 || fail 'awg show failed.'
ok 'AWG command works'

if ip link show awg0 >/dev/null 2>&1; then ok 'awg0 interface exists'; else fail 'awg0 interface missing'; fi

PORT=$(awk -F' *= *' '/^ListenPort[[:space:]]*=/{print $2; exit}' /etc/amnezia/amneziawg/awg0.conf /etc/wireguard/awg0.conf 2>/dev/null || true)
[ -n "${PORT:-}" ] && ok "AWG ListenPort: $PORT" || log 'ListenPort not found in config; keeping installer value.'

log 'Verifying NOVA service'
systemctl is-active --quiet awgpanel || fail 'awgpanel is not active.'
ok 'awgpanel is active'
curl -fsS --max-time 10 http://127.0.0.1:8080/login >/dev/null || fail 'NOVA HTTP check failed.'
ok 'NOVA HTTP :8080 responds'
curl -fsS --max-time 10 http://127.0.0.1:8080/api/nova/health >/dev/null || fail 'NOVA health endpoint failed.'
ok 'NOVA health endpoint responds'

log 'Verifying optional modules'
python3 - <<'PY'
import importlib
for name in ('app','nova11','keenetic','balancer','balancer_provision','panel_bootstrap'):
    importlib.import_module(name)
    print('[ OK ] import', name)
PY

printf '\n\033[1;32m========================================\n'
printf ' NOVA 11 FULL INSTALL COMPLETE\n'
printf '========================================\033[0m\n'
printf 'Panel:     http://SERVER:8080\n'
printf 'Keenetic:  http://SERVER:8080/keenetic\n'
printf 'Health:    http://SERVER:8080/api/nova/health\n'
printf 'Service:   systemctl status awgpanel\n'
printf 'AWG:       awg show\n'
printf '\nIMPORTANT: the AWG config is not overwritten by the panel installer.\n'
printf 'For a fresh VPS, the upstream installer created awg0 and the NOVA panel was installed afterwards.\n'
