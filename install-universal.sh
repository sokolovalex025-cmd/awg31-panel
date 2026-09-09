#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

# AWG Panel 8.1 / AmneziaWG 3.1 universal installer.
# Supported: Ubuntu 22.04/24.04, Debian 12/13, amd64/x86_64, systemd VPS.
# This script installs/prepares the OS and then executes the repository's
# canonical install.sh directly. It does NOT patch another script at runtime.

log(){ printf '[%s] %s\n' "$1" "$2"; }
die(){ log ERROR "$1"; exit 1; }

[ "$(id -u)" -eq 0 ] || die 'Запустите от root: sudo ./install-universal.sh'
[ -r /etc/os-release ] || die 'Не найден /etc/os-release.'
. /etc/os-release

OS_ID=${ID:-unknown}
OS_VER=${VERSION_ID:-unknown}

case "$OS_ID:$OS_VER" in
  ubuntu:22.04|ubuntu:24.04) log OK "Поддерживаемая ОС: Ubuntu $OS_VER" ;;
  debian:12|debian:13) log OK "Поддерживаемая ОС: Debian $OS_VER" ;;
  *) die "Поддерживаются Ubuntu 22.04/24.04 и Debian 12/13. Обнаружено: ${PRETTY_NAME:-$OS_ID $OS_VER}" ;;
esac

command -v systemctl >/dev/null 2>&1 || die 'Требуется systemd.'
ARCH=$(dpkg --print-architecture 2>/dev/null || true)
[ "$ARCH" = amd64 ] || die "Требуется amd64/x86_64. Обнаружено: ${ARCH:-unknown}"

VIRT=$(systemd-detect-virt 2>/dev/null || true)
case "$VIRT" in lxc|openvz) die "LXC/OpenVZ не поддерживаются. Используйте KVM VPS.";; esac

apt-get update
apt-get install -y ca-certificates curl gnupg2 iproute2 iptables python3 python3-venv python3-pip qrencode openssl

install_ubuntu_awg(){
  log INFO 'Установка AmneziaWG из PPA Amnezia для Ubuntu...'
  apt-get install -y software-properties-common python3-launchpadlib gnupg2
  if ! apt-cache policy amneziawg 2>/dev/null | grep -q '^  Candidate:'; then
    add-apt-repository -y ppa:amnezia/ppa
    apt-get update
  fi
  apt-get install -y amneziawg
}

install_debian_awg(){
  log INFO 'Подготовка AmneziaWG для Debian...'
  apt-get install -y linux-headers-amd64 || apt-get install -y "linux-headers-$(uname -r)" || true
  install -d -m 0755 /etc/apt/keyrings

  # Amnezia's Launchpad PPA publishes Ubuntu packages. The focal suite is used
  # here only for Debian systems for which this package route is available.
  # We verify the package and module after installation; failure is fatal.
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' RETURN
  curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x57290828&output=armor' -o "$tmp"
  gpg --batch --yes --dearmor -o /etc/apt/keyrings/amnezia-archive-keyring.gpg "$tmp"
  rm -f "$tmp"

  cat >/etc/apt/sources.list.d/amneziawg.list <<'EOF'
deb [signed-by=/etc/apt/keyrings/amnezia-archive-keyring.gpg] https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main
EOF
  apt-get update
  apt-get install -y amneziawg
}

if command -v awg >/dev/null 2>&1 && command -v awg-quick >/dev/null 2>&1; then
  log OK 'AmneziaWG tools уже установлены.'
else
  case "$OS_ID" in
    ubuntu) install_ubuntu_awg ;;
    debian) install_debian_awg ;;
  esac
fi

command -v awg >/dev/null 2>&1 || die 'awg не установлен.'
command -v awg-quick >/dev/null 2>&1 || die 'awg-quick не установлен.'

modprobe amneziawg >/dev/null 2>&1 || true
TOOLS_VERSION=$(awg --version 2>/dev/null || true)
MODULE_VERSION=$(cat /sys/module/amneziawg/version 2>/dev/null || true)
echo '=== AmneziaWG version check ==='
echo "tools:  ${TOOLS_VERSION:-unknown}"
echo "kernel: ${MODULE_VERSION:-unknown}"

grep -q '3\.1' <<<"$TOOLS_VERSION" || die 'Версия awg tools не подтверждена как 3.1.'
grep -q '3\.1' <<<"$MODULE_VERSION" || die 'Модуль amneziawg не загружен или его версия не 3.1.'

SRC=$(cd "$(dirname "$0")" && pwd)
INSTALL="$SRC/install.sh"
[ -f "$INSTALL" ] || die 'В каталоге не найден install.sh.'

# The canonical installer must be distro-aware. No regex patching or temporary
# mutation is performed here.
python3 - "$INSTALL" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8', errors='strict')
if 'AWG Panel 8.1' not in s:
    raise SystemExit('install.sh не похож на ожидаемый установщик AWG Panel 8.1')
PY

log INFO 'Запуск основного установщика...'
bash "$INSTALL"

if [ -x "$SRC/diagnostics.sh" ]; then
  log INFO 'Запуск итоговой диагностики...'
  bash "$SRC/diagnostics.sh" || {
    log ERROR 'Диагностика завершилась с ошибками. Панель установлена, но требуется проверка.'
    exit 1
  }
fi

log OK 'Установка AWG Panel завершена.'
