#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

# AWG Panel 8.1 / AmneziaWG 3.1 universal bootstrap.
# Officially targets Ubuntu 22.04/24.04 and Debian 12/13.
# The existing install.sh remains the canonical panel installer; this wrapper
# prepares the OS and AWG package, then runs it with its Ubuntu-only guard bypassed.

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install-universal.sh'; exit 1; }

. /etc/os-release
OS_ID=${ID:-unknown}
OS_VER=${VERSION_ID:-unknown}
CODENAME=${VERSION_CODENAME:-}

case "$OS_ID:$OS_VER" in
  ubuntu:22.04|ubuntu:24.04)
    echo "[OK] Supported OS: Ubuntu $OS_VER"
    ;;
  debian:12|debian:13)
    echo "[OK] Supported OS: Debian $OS_VER"
    ;;
  *)
    echo "ОШИБКА: поддерживаются Ubuntu 22.04/24.04 и Debian 12/13."
    echo "Обнаружено: ${PRETTY_NAME:-$OS_ID $OS_VER}"
    exit 1
    ;;
esac

ARCH=$(dpkg --print-architecture 2>/dev/null || true)
case "$ARCH" in
  amd64) ;;
  *)
    echo "ОШИБКА: для этого установщика требуется amd64/x86_64. Обнаружено: ${ARCH:-unknown}"
    exit 1
    ;;
esac

KERNEL=$(uname -r)
if [ "$(systemd-detect-virt 2>/dev/null || true)" = "lxc" ] || [ "$(systemd-detect-virt 2>/dev/null || true)" = "openvz" ]; then
  echo 'ОШИБКА: LXC/OpenVZ не поддерживаются. Используйте KVM VPS.'
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl gnupg2 iproute2 iptables python3 python3-venv python3-pip qrencode openssl

install_debian_awg() {
  echo '[INFO] Preparing AmneziaWG repository for Debian...'
  apt-get install -y linux-headers-"$KERNEL" software-properties-common python3-launchpadlib

  # Amnezia documents the Ubuntu PPA's focal suite for Debian. Keep the key in
  # a dedicated keyring instead of using the deprecated apt-key command.
  install -d -m 0755 /etc/apt/keyrings
  if ! gpg --batch --no-tty --list-keys 57290828 >/dev/null 2>&1; then
    tmp=$(mktemp)
    curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x57290828&output=armor' -o "$tmp"
    gpg --batch --yes --dearmor -o /etc/apt/keyrings/amnezia-archive-keyring.gpg "$tmp"
    rm -f "$tmp"
  fi
  cat >/etc/apt/sources.list.d/amneziawg.list <<'EOF'
deb [signed-by=/etc/apt/keyrings/amnezia-archive-keyring.gpg] https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main
EOF
  apt-get update
  apt-get install -y amneziawg
}

install_ubuntu_awg() {
  apt-get install -y software-properties-common python3-launchpadlib gnupg2 linux-headers-"$KERNEL"
  if ! apt-cache policy amneziawg 2>/dev/null | grep -q 'Candidate:'; then
    add-apt-repository -y ppa:amnezia/ppa
    apt-get update
  fi
  apt-get install -y amneziawg
}

if command -v awg >/dev/null 2>&1 && command -v awg-quick >/dev/null 2>&1; then
  echo '[OK] AmneziaWG tools already installed.'
else
  case "$OS_ID" in
    ubuntu) install_ubuntu_awg ;;
    debian) install_debian_awg ;;
  esac
fi

modprobe amneziawg >/dev/null 2>&1 || true
command -v awg >/dev/null 2>&1 || { echo 'ОШИБКА: awg не установлен.'; exit 1; }
command -v awg-quick >/dev/null 2>&1 || { echo 'ОШИБКА: awg-quick не установлен.'; exit 1; }

echo '=== AmneziaWG version check ==='
awg --version || true
printf 'kernel module: '
cat /sys/module/amneziawg/version 2>/dev/null || echo unknown

SRC=$(cd "$(dirname "$0")" && pwd)
TMP_INSTALL=$(mktemp /tmp/awg31-install.XXXXXX.sh)
trap 'rm -f "$TMP_INSTALL"' EXIT

if [ -f "$SRC/install.sh" ]; then
  cp "$SRC/install.sh" "$TMP_INSTALL"
else
  curl -fsSL 'https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install.sh' -o "$TMP_INSTALL"
fi
chmod 700 "$TMP_INSTALL"

# install.sh historically required Ubuntu. At this point the OS has already
# been validated and Debian has AWG preinstalled, so bypass only that guard.
python3 - "$TMP_INSTALL" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
s=s.replace("[ \"${ID:-}\" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }", "case \"${ID:-}\" in ubuntu|debian) ;; *) echo 'Неподдерживаемая ОС'; exit 1;; esac")
p.write_text(s)
PY

exec bash "$TMP_INSTALL"
