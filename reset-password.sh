#!/usr/bin/env bash
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./reset-password.sh'; exit 1; }
BASE=/opt/awg31-panel
DB="$BASE/panel.db"

[ -f "$DB" ] || { echo "Ошибка: $DB не найден. Сначала установите панель."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'Ошибка: python3 не найден.'; exit 1; }

NEW_PASS="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(18))
PY
)"

python3 - "$DB" "$NEW_PASS" <<'PY'
import sqlite3, sys

db, password = sys.argv[1], sys.argv[2]
c = sqlite3.connect(db)
c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')")
c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)", (password,))
c.commit()
c.close()
PY

# Keep a root-only copy for recovery; never print an existing password.
printf '%s\n' "$NEW_PASS" > "$BASE/.initial_password"
chmod 600 "$BASE/.initial_password"

systemctl restart awgpanel 2>/dev/null || true
sleep 1

if systemctl is-active --quiet awgpanel; then
  echo 'Пароль панели успешно сброшен.'
else
  echo 'Пароль записан, но awgpanel сейчас не активен.'
  echo 'Проверьте: systemctl status awgpanel --no-pager'
fi

echo
 echo 'Login: admin'
echo "Password: $NEW_PASS"
echo
echo 'Панель: http://SERVER_IP:8080/login'
