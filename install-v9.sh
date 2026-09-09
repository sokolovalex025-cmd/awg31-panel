#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
SRC=$(cd "$(dirname "$0")" && pwd)
[ -x "$SRC/install.sh" ] || chmod +x "$SRC/install.sh"
[ -x "$SRC/upgrade-panel9.sh" ] || chmod +x "$SRC/upgrade-panel9.sh"
printf '%s\n' '=== AWG Panel 9.0 installer ==='
bash "$SRC/install.sh"
bash "$SRC/upgrade-panel9.sh"
printf '%s\n' '=== AWG Panel 9.0 готов ==='
