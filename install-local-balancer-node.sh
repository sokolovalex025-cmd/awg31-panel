#!/usr/bin/env bash
set -euo pipefail
ENV=/etc/awg31-panel/balancer.env
[ -f "$ENV" ] || { echo "Run install-balancer.sh first."; exit 1; }
TOKEN=$(sed -n 's/^BALANCER_TOKEN=//p' "$ENV" | head -1)
[ -n "$TOKEN" ] || { echo "BALANCER_TOKEN is empty."; exit 1; }
exec "$(dirname "$0")/install-balancer-node.sh" "$TOKEN"
