#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
FILE=$BASE/telegram_bot.py
ENV=/etc/awg31-panel/telegram.env
SERVICE=awgpanel-telegram.service
[ -f "$FILE" ] || { echo "Не найден $FILE"; exit 1; }
mkdir -p /etc/awg31-panel "$BASE/backups"
TS=$(date +%Y%m%d-%H%M%S)
cp -a "$FILE" "$BASE/backups/telegram_bot-before-fix-$TS.py"

python3 - "$FILE" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
s=p.read_text()
old="""    try:r=json.loads(urllib.request.urlopen(urllib.request.Request('https://api.telegram.org/bot'+token+'/getMe'),timeout=8).read().decode())
    except Exception:r={}
    if not r.get('ok'):return redirect('/telegram?err=Token%20не%20прошёл%20проверку')
    save_env(token,idsv,notify);run('systemctl','daemon-reload');run('systemctl','enable',SERVICE);run('systemctl','restart',SERVICE);return redirect('/telegram?ok=Бот%20подключён')
"""
new="""    # Validate Telegram ID list before touching the configuration.
    try:
     id_list=[int(x.strip()) for x in idsv.split(',') if x.strip()]
    except Exception:
     id_list=[]
    if not id_list:return redirect('/telegram?err=Telegram%20ID%20должен%20быть%20числом%20или%20списком%20чисел')
    # Telegram may be temporarily unreachable from the VPS. In that case we still
    # save the credentials so the user can retry/restart the bot from the panel.
    tg_error=''
    try:
     rr=urllib.request.urlopen(urllib.request.Request('https://api.telegram.org/bot'+token+'/getMe'),timeout=8)
     check=json.loads(rr.read().decode())
     if not check.get('ok'):
      return redirect('/telegram?err=Token%20Telegram%20недействителен')
    except Exception as exc:
     tg_error=str(exc)[:180]
    save_env(token,','.join(str(x) for x in id_list),notify)
    run('chmod','600',str(ENV))
    run('systemctl','daemon-reload')
    sr=run('systemctl','enable','--now',SERVICE,timeout=15)
    if sr.returncode!=0:
     return redirect('/telegram?err=Токен%20сохранён,%20но%20сервис%20не%20запустился')
    sr=run('systemctl','restart',SERVICE,timeout=15)
    if sr.returncode!=0:
     return redirect('/telegram?err=Токен%20сохранён,%20но%20бот%20не%20запустился')
    if tg_error:
     return redirect('/telegram?ok=Сохранено.%20Telegram%20временно%20недоступен,%20бот%20будет%20повторять%20подключение')
    return redirect('/telegram?ok=Бот%20подключён%20и%20запущен')
"""
if old not in s:
 print('Нужный блок не найден; версия telegram_bot.py отличается.',file=sys.stderr)
 sys.exit(2)
p.write_text(s.replace(old,new,1))
PY

PY=$BASE/venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"

# Make the service definition deterministic and independent from the panel process.
cat >/etc/systemd/system/$SERVICE <<EOF
[Unit]
Description=AWG Panel 8.1 Telegram Bot
After=network-online.target awgpanel.service
Wants=network-online.target

[Service]
WorkingDirectory=$BASE
EnvironmentFile=-$ENV
ExecStart=$BASE/venv/bin/python $FILE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
chmod 600 /etc/systemd/system/$SERVICE
systemctl daemon-reload
if [ -s "$ENV" ]; then
  chmod 600 "$ENV"
  systemctl enable --now "$SERVICE"
  systemctl restart "$SERVICE"
else
  systemctl disable --now "$SERVICE" >/dev/null 2>&1 || true
fi

echo
 echo '=== Telegram integration fixed ==='
echo "File: $FILE"
echo "Config: $ENV"
echo "Service: $(systemctl is-active "$SERVICE" 2>/dev/null || true)"
[ -s "$ENV" ] && echo 'telegram.env: PRESENT' || echo 'telegram.env: NOT CONFIGURED — enter Token + Telegram ID in the panel'
