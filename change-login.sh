#!/usr/bin/env bash
set -Eeuo pipefail

# Change AWG Panel web login/password safely.
# Usage: sudo ./change-login.sh

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }

BASE=/opt/awg31-panel
DB="$BASE/panel.db"

[ -f "$DB" ] || { echo "ОШИБКА: база панели не найдена: $DB"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo 'ОШИБКА: python3 не найден.'; exit 1; }

read -r -p 'Новый логин: ' NEW_LOGIN
[ -n "$NEW_LOGIN" ] || { echo 'ОШИБКА: логин не может быть пустым.'; exit 1; }

read -r -s -p 'Новый пароль: ' NEW_PASSWORD
printf '\n'
[ -n "$NEW_PASSWORD" ] || { echo 'ОШИБКА: пароль не может быть пустым.'; exit 1; }
read -r -s -p 'Повторите пароль: ' NEW_PASSWORD2
printf '\n'
[ "$NEW_PASSWORD" = "$NEW_PASSWORD2" ] || { echo 'ОШИБКА: пароли не совпадают.'; exit 1; }

# Keep credentials out of shell history/process arguments.
export AWG_NEW_LOGIN="$NEW_LOGIN"
export AWG_NEW_PASSWORD="$NEW_PASSWORD"

python3 - "$DB" <<'PY'
import os, sqlite3, sys
from pathlib import Path

db = Path(sys.argv[1])
login = os.environ['AWG_NEW_LOGIN']
password = os.environ['AWG_NEW_PASSWORD']

c = sqlite3.connect(db)
try:
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)")
    c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('login',?)", (login,))
    c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)", (password,))
    c.commit()
finally:
    c.close()
PY

unset AWG_NEW_LOGIN AWG_NEW_PASSWORD
chmod 600 "$DB"

if systemctl is-enabled --quiet awgpanel 2>/dev/null || systemctl is-active --quiet awgpanel 2>/dev/null; then
    systemctl restart awgpanel
    sleep 1
    if ! systemctl is-active --quiet awgpanel; then
        echo 'ОШИБКА: awgpanel не запустилась после смены данных.'
        journalctl -u awgpanel -n 30 --no-pager || true
        exit 1
    fi
fi

# Remove the old generated password file so it cannot confuse the administrator.
rm -f "$BASE/.initial_password"

echo
 echo '=== ДАННЫЕ ДОСТУПА ОБНОВЛЕНЫ ==='
echo "Логин: $NEW_LOGIN"
echo 'Пароль: установлен новый (не выводится)'
echo 'Панель: http://SERVER_IP:8080/login'
echo 'Готово.'
