#!/usr/bin/env python3
from pathlib import Path

APP = Path('/opt/awg31-panel/app.py')
BACKUP = APP.with_name('app.py.telegram-ui.bak')

if not APP.exists():
    raise SystemExit(f'not found: {APP}')
s = APP.read_text()

# Add Telegram Bot to the existing sidebar navigation.
if "'Telegram Bot','/telegram'" not in s:
    old = "('⚙','Настройки','/settings'),('ⓘ','О NOVA','/about')"
    new = "('⚙','Настройки','/settings'),('✈','Telegram Bot','/telegram'),('ⓘ','О NOVA','/about')"
    if old not in s:
        raise SystemExit('navigation anchor not found in current app.py')
    s = s.replace(old, new, 1)

if 'def nova_telegram_page' not in s:
    block = '''

TELEGRAM_ENV=Path('/etc/awg31-panel/telegram.env')

def telegram_env_values():
    out={}
    if TELEGRAM_ENV.exists():
        for line in TELEGRAM_ENV.read_text(errors='replace').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); out[k.strip()]=v.strip()
    return out

def telegram_env_write(values):
    TELEGRAM_ENV.parent.mkdir(parents=True, exist_ok=True)
    order=['TELEGRAM_BOT_TOKEN','TELEGRAM_ADMIN_IDS','TELEGRAM_ALLOWED_IDS','TELEGRAM_NOTIFY','VPN_DEFAULT_DAYS','NOVA_ROUTES_URL','NOVA_ROUTES_FILE','NOVA_ROUTES_INTERVAL']
    old=telegram_env_values(); old.update(values)
    lines=['# NOVA Telegram Bot configuration']
    for k in order:
        if old.get(k,'') != '': lines.append(f'{k}={old[k]}')
    TELEGRAM_ENV.write_text('\\n'.join(lines)+'\\n')
    import os; os.chmod(TELEGRAM_ENV,0o600)

def telegram_token_check(token):
    if not token: return False,'Токен не указан.'
    try:
        import urllib.request,json
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/getMe',headers={'User-Agent':'NOVA-Panel/10'})
        with urllib.request.urlopen(req,timeout=10) as r: data=json.loads(r.read().decode())
        if data.get('ok'):
            u=data.get('result',{}); return True,'@'+str(u.get('username') or u.get('first_name') or 'bot')
        return False,str(data.get('description') or 'Telegram API error')
    except Exception as e: return False,str(e)

@app.route('/telegram',methods=['GET','POST'])
def nova_telegram_page():
    if request.method=='POST':
        action=request.form.get('action','save')
        if action=='test':
            ok,msg=telegram_token_check(telegram_env_values().get('TELEGRAM_BOT_TOKEN',''))
            body='<div class="hero"><div><div class="eyebrow">NOVA CONTROL</div><h1>Telegram Bot</h1><p>Проверка подключения к Telegram.</p></div></div>'
            body += '<div class="notice '+('good' if ok else 'badbox')+'"><b>'+('✓ Подключение успешно' if ok else '✕ Ошибка подключения')+'</b><br>'+msg+'</div><a class="btn" href="/telegram">← Назад</a>'
            return layout('Telegram Bot',body,'/telegram')
        token=request.form.get('token','').strip() or telegram_env_values().get('TELEGRAM_BOT_TOKEN','')
        if request.form.get('token','').strip():
            ok,msg=telegram_token_check(token)
            if not ok:
                body='<div class="hero"><div><div class="eyebrow">NOVA CONTROL</div><h1>Telegram Bot</h1><p>Токен не сохранён.</p></div></div><div class="notice badbox"><b>✕ Telegram API:</b> '+msg+'</div><a class="btn" href="/telegram">← Назад</a>'
                return layout('Telegram Bot',body,'/telegram')
        telegram_env_write({'TELEGRAM_BOT_TOKEN':token,'TELEGRAM_ADMIN_IDS':request.form.get('admin_ids','').strip(),'TELEGRAM_ALLOWED_IDS':request.form.get('allowed_ids','').strip(),'TELEGRAM_NOTIFY':'1' if request.form.get('notify')=='1' else '0','VPN_DEFAULT_DAYS':request.form.get('days','30').strip() or '30','NOVA_ROUTES_URL':request.form.get('routes_url','').strip(),'NOVA_ROUTES_FILE':request.form.get('routes_file','').strip(),'NOVA_ROUTES_INTERVAL':request.form.get('routes_interval','900').strip() or '900'})
        cmd('systemctl','restart','awgpanel-telegram.service')
        body='<div class="hero"><div><div class="eyebrow">NOVA CONTROL</div><h1>Telegram Bot</h1><p>Настройки сохранены.</p></div></div><div class="notice good"><b>✓ Готово</b><br>Конфигурация сохранена. Бот перезапущен.</div><a class="btn" href="/telegram">Открыть Telegram Bot</a>'
        return layout('Telegram Bot',body,'/telegram')
    v=telegram_env_values(); configured=bool(v.get('TELEGRAM_BOT_TOKEN')); status=cmd('systemctl','is-active','awgpanel-telegram.service').stdout.strip() or 'unknown'
    masked=('••••••••…'+v['TELEGRAM_BOT_TOKEN'][-4:]) if configured and len(v['TELEGRAM_BOT_TOKEN'])>4 else ('Настроен' if configured else 'Не настроен')
    body='<div class="hero"><div><div class="eyebrow">NOVA CONTROL</div><h1>Telegram Bot</h1><p>Управление Telegram-ботом NOVA VPN прямо из панели.</p></div></div>'
    body += '<div class="card"><div class="toolbar"><h2>🤖 Подключение</h2><span class="badge '+('on' if configured else 'warn')+'">'+('НАСТРОЕН' if configured else 'НЕ НАСТРОЕН')+'</span></div><div class="notice">Статус службы: <b>'+status+'</b><br>Токен: <b>'+masked+'</b></div><form method="post"><label>Bot Token</label><input name="token" type="password" placeholder="Вставьте токен от @BotFather" autocomplete="new-password"><div class="formgrid"><div><label>Telegram Admin ID</label><input name="admin_ids" value="'+v.get('TELEGRAM_ADMIN_IDS','')+'" placeholder="123456789"></div><div><label>Разрешённые ID</label><input name="allowed_ids" value="'+v.get('TELEGRAM_ALLOWED_IDS','')+'" placeholder="123456789,987654321"></div></div><div class="formgrid"><div><label>Срок VPN по умолчанию, дней</label><input name="days" value="'+v.get('VPN_DEFAULT_DAYS','30')+'"></div><div><label>Интервал проверки Routes, сек</label><input name="routes_interval" value="'+v.get('NOVA_ROUTES_INTERVAL','900')+'"></div></div><label>NOVA Routes URL</label><input name="routes_url" value="'+v.get('NOVA_ROUTES_URL','')+'" placeholder="https://example.com/routes.txt"><label>NOVA Routes File</label><input name="routes_file" value="'+v.get('NOVA_ROUTES_FILE','')+'" placeholder="/opt/awg31-panel/nova-routes.txt"><label><input type="checkbox" name="notify" value="1" style="width:auto" '+('checked' if v.get('TELEGRAM_NOTIFY')=='1' else '')+'> Уведомлять администраторов</label><div class="actions-row" style="margin-top:16px"><button type="submit">💾 Сохранить и перезапустить</button></div></form></div>'
    body += '<div class="card" style="margin-top:14px"><div class="toolbar"><h2>🧪 Проверка</h2></div><p class="muted">Токен проверяется через Telegram API. Сам токен в интерфейсе не показывается.</p><form method="post"><input type="hidden" name="action" value="test"><button class="btn secondary" type="submit">Проверить подключение</button></form></div>'
    return layout('Telegram Bot',body,'/telegram')
'''
    anchor='\n@app.before_request\ndef auth():'
    if anchor not in s:
        raise SystemExit('auth anchor not found')
    BACKUP.write_text(s)
    s=s.replace(anchor, block+anchor, 1)
    APP.write_text(s)
    print('Telegram UI installed')
else:
    print('Telegram UI already installed')
