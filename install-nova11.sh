#!/usr/bin/env bash
set -Eeuo pipefail
# Compatibility wrapper: use the current NOVA installer.
exec bash <(curl -fsSL https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/main/install-nova.sh) "$@"
