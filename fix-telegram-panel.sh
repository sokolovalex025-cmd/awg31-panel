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
import re,sys
p=Path(sys.argv[1])
s=p.read_text()
# Patch the whole save action rather than relying on one exact historical block.
pattern=r"(?ms)^   if action=='save':\n.*?(?=^   if action=='test':)"
new="""   if action=='save':
    token=request.form.get('token','').strip();idsv=request.form.get('ids','').strip();notify='1' if request.form.get('notify') else '0'
    if not token or not idsv:return redirect('/telegram?err=Заполните%20Token%20и%20Telegram%20ID')
    try:
     id_list=[int(x.strip()) for x in idsv.split(',') if x.strip()]
    except Exception:
     id_list=[]
    if not id_list:return redirect('/telegram?err=Telegram%20ID%20должен%20быть%20числом%20или%20списком%20чисел')
    tg_error=''
    try:
     rr=urllib.request.urlopen(urllib.request.Request('https://api.telegram.org/bot'+token+'/getMe'),timeout=8)
     check=json.loads(rr.read().decode())
     if not check.get('ok'):return redirect('/telegram?err=Token%20Telegram%20недействителен')
    except Exception as exc:
     tg_error=str(exc)[:180]
    save_env(token,','.join(str(x) for x in id_list),notify)
    run('chmod','600',str(ENV));run('systemctl','daemon-reload')
    run('systemctl','enable','--now',SERVICE)
    sr=run('systemctl','restart',SERVICE)
    if sr.returncode!=0:return redirect('/telegram?err=Токен%20сохранён,%20но%20бот%20не%20запустился')
    if tg_error:return redirect('/telegram?ok=Сохранено.%20Telegram%20временно%20недоступен,%20бот%20будет%20повторять%20подключение')
    return redirect('/telegram?ok=Бот%20подключён%20и%20запущен')
"""
m=re.search(pattern,s)
if not m:
 print('Не найден блок action=save в telegram_bot.py.',file=sys.stderr);sys.exit(2)
s=s[:m.start()]+new+s[m.end():]
p.write_text(s)
print('Telegram save block patched successfully.')
PY

PY=$BASE/venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" -m py_compile "$FILE"
chmod 600 "$FILE"

cat >/etc/systemd/system/$SERVICE <<EOF
[Unit]
Description=NOVA AWG 3.1 Telegram Bot
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
