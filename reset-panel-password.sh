#!/usr/bin/env bash
set -euo pipefail

BASE="/opt/awg31-panel"
DB="$BASE/panel.db"
PYTHON="/root/awg31-panel/venv/bin/python"
SERVICE="awgpanel.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash reset-panel-password.sh"
  exit 1
fi

if [[ ! -f "$DB" ]]; then
  echo "ERROR: $DB not found. Is NOVA 11 installed?"
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

echo "NOVA 11 password reset"
echo "Login will remain unchanged."
read -r -p "Login [admin]: " LOGIN
LOGIN="${LOGIN:-admin}"

while true; do
  read -r -s -p "New password (min 10 characters): " PASSWORD
  echo
  read -r -s -p "Repeat password: " PASSWORD2
  echo

  if [[ "$PASSWORD" != "$PASSWORD2" ]]; then
    echo "ERROR: passwords do not match."
    continue
  fi
  if [[ "${#PASSWORD}" -lt 10 ]]; then
    echo "ERROR: password must contain at least 10 characters."
    continue
  fi
  break
done

export NOVA_LOGIN="$LOGIN"
export NOVA_PASSWORD="$PASSWORD"

"$PYTHON" - <<'PY'
import os
import sqlite3
from pathlib import Path

DB = Path('/opt/awg31-panel/panel.db')
login = os.environ['NOVA_LOGIN']
password = os.environ['NOVA_PASSWORD']

con = sqlite3.connect(DB)
try:
    con.execute('CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)')
    con.execute("INSERT INTO settings(k,v) VALUES('login',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (login,))
    con.execute("INSERT INTO settings(k,v) VALUES('password',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (password,))
    con.commit()
finally:
    con.close()
PY

unset NOVA_LOGIN NOVA_PASSWORD

systemctl restart "$SERVICE"
sleep 2

if systemctl is-active --quiet "$SERVICE" && curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/login | grep -q '^200$'; then
  echo
  echo "OK: NOVA 11 password changed successfully."
  echo "Login: $LOGIN"
else
  echo
  echo "ERROR: password was changed, but panel health check failed."
  systemctl status "$SERVICE" --no-pager -l | tail -30 || true
  exit 1
fi
