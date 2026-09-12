#!/usr/bin/env python3
"""NOVA Telegram bot: self-service AWG 3.1 profiles with expiry/renewal.

Secrets stay in /etc/awg31-panel/telegram.env (created by the panel UI):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_ADMIN_IDS=123,456
  TELEGRAM_ALLOWED_IDS=123,456   (optional; empty means public self-service)
  TELEGRAM_NOTIFY=1              (optional)
  VPN_DEFAULT_DAYS=30            (optional)
"""
import io, json, os, re, sqlite3, subprocess, time, urllib.parse, urllib.request
from pathlib import Path
from flask import request, redirect, render_template_string

BASE=Path('/opt/awg31-panel'); ENV=Path('/etc/awg31-panel/telegram.env'); SERVICE='awgpanel-telegram.service'
DB=BASE/'panel.db'; CONF=Path('/etc/amnezia/amneziawg/awg0.conf')
if not CONF.exists(): CONF=Path('/etc/wireguard/awg0.conf')

def env():
    d={}
    try:
        for line in ENV.read_text(errors='replace').splitlines():
            line=line.strip()
            if '=' in line and not line.startswith('#'):
                k,v=line.split('=',1); d[k]=v.strip().strip('"')
    except Exception: pass
    return d

def save_env(token,ids,notify='0'):
    ENV.parent.mkdir(parents=True,exist_ok=True)
    ENV.write_text('TELEGRAM_BOT_TOKEN='+token+'\nTELEGRAM_ADMIN_IDS='+ids+'\nTELEGRAM_NOTIFY='+notify+'\n')
    os.chmod(ENV,0o600)

def tg(method,data=None,timeout=40):
    token=env().get('TELEGRAM_BOT_TOKEN','')
    if not token:return {}
    try:
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/'+method,data=urllib.parse.urlencode(data or {}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
        return json.loads(urllib.request.urlopen(req,timeout=timeout).read().decode())
    except Exception:return {}

def run(*a):
    try:return subprocess.run(a,text=True,capture_output=True,timeout=20)
    except Exception as x:return subprocess.CompletedProcess(a,1,'',str(x))

def status(s):return run('systemctl','is-active','--quiet',s).returncode==0

def ids(key):return {int(x.strip()) for x in env().get(key,'').split(',') if x.strip().isdigit()}

def allowed(uid):
    a=ids('TELEGRAM_ALLOWED_IDS'); admins=ids('TELEGRAM_ADMIN_IDS')
    return not a or uid in a or uid in admins

def admin(uid):return uid in ids('TELEGRAM_ADMIN_IDS')

def db():
    c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c

def init_db():
    c=db()
    c.execute('''CREATE TABLE IF NOT EXISTS telegram_subscriptions(
        telegram_id INTEGER PRIMARY KEY, username TEXT, client_id INTEGER NOT NULL,
        expires INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1,
        created INTEGER NOT NULL, peer_block TEXT DEFAULT ''
    )''')
    try:c.execute("ALTER TABLE telegram_subscriptions ADD COLUMN peer_block TEXT DEFAULT ''")
    except sqlite3.OperationalError:pass
    c.commit();c.close()

def subscription(uid):
    c=db();r=c.execute('SELECT * FROM telegram_subscriptions WHERE telegram_id=?',(uid,)).fetchone();c.close();return r

def client_row(cid):
    c=db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone();c.close();return r

def fmt(ts):return time.strftime('%d.%m.%Y %H:%M',time.localtime(ts))

def panel_request(path,method='GET',data=None):
    import app as panel
    client=panel.app.test_client()
    r=client.post('/login',data={'login':panel.setting('login','admin'),'password':panel.setting('password','change-me')})
    if r.status_code not in (301,302): raise RuntimeError('panel login failed')
    if method=='POST': return client.post(path,data=data or {},follow_redirects=False)
    return client.get(path)

def create_client(name):
    panel_request('/clients/create','POST',{'name':name})
    c=db();r=c.execute('SELECT * FROM clients WHERE name=? ORDER BY id DESC LIMIT 1',(name,)).fetchone();c.close()
    if not r:raise RuntimeError('client was not created')
    return r

def conf_bytes(cid):
    r=panel_request(f'/clients/{cid}/conf')
    if r.status_code!=200:raise RuntimeError('config endpoint failed')
    return r.data

def qr_bytes(cid):
    r=panel_request(f'/clients/{cid}/qr')
    if r.status_code!=200:raise RuntimeError('QR endpoint failed')
    return r.data

def peer_block(pub):
    if not CONF.exists():return ''
    parts=CONF.read_text(errors='replace').split('[Peer]')
    for p in parts[1:]:
        block='[Peer]'+p
        if re.search(r'^\s*PublicKey\s*=\s*'+re.escape(pub)+r'\s*$',block,re.M):return block.strip()+'\n'
    return ''

def set_peer_enabled(pub,enabled,stored=''):
    if not CONF.exists():return False
    text=CONF.read_text(errors='replace'); parts=text.split('[Peer]')
    found=False; out=[parts[0].rstrip()]
    for p in parts[1:]:
        block='[Peer]'+p
        if re.search(r'^\s*PublicKey\s*=\s*'+re.escape(pub)+r'\s*$',block,re.M):
            found=True
            if enabled: out.append(block.strip())
        else: out.append(block.strip())
    if not enabled and not found:return False
    if enabled and not found:
        if not stored:return False
        out.append(stored.strip())
    CONF.write_text('\n\n'.join(x for x in out if x.strip())+'\n');os.chmod(CONF,0o600)
    r=run('awg-quick','strip','awg0')
    if r.returncode!=0:return False
    r=run('systemctl','reload','awg-quick@awg0')
    if r.returncode!=0:r=run('systemctl','restart','awg-quick@awg0')
    return r.returncode==0

def save_sub(uid,username,cid,expires,block):
    c=db();now=int(time.time())
    c.execute('''INSERT INTO telegram_subscriptions(telegram_id,username,client_id,expires,active,created,peer_block)
                 VALUES(?,?,?,?,1,?,?) ON CONFLICT(telegram_id) DO UPDATE SET
                 username=excluded.username,client_id=excluded.client_id,expires=excluded.expires,active=1,peer_block=excluded.peer_block''',
              (uid,username or '',cid,expires,now,block))
    c.commit();c.close()

def issue(uid,username,days):
    now=int(time.time());s=subscription(uid)
    if s and client_row(s['client_id']):
        c=client_row(s['client_id']); block=s['peer_block'] or peer_block(c['public_key'])
        set_peer_enabled(c['public_key'],True,block)
        expires=max(now,s['expires'])+days*86400
        save_sub(uid,username,c['id'],expires,block)
        return c['id'],expires,False
    name='TG-'+str(uid)
    r=create_client(re.sub(r'[^A-Za-z0-9_.-]','-',name)[:32])
    block=peer_block(r['public_key']);expires=now+days*86400
    save_sub(uid,username,r['id'],expires,block)
    return r['id'],expires,True

def menu():
    return json.dumps({'inline_keyboard':[
        [{'text':'🔐 Получить VPN','callback_data':'get'}],
        [{'text':'📱 Мой VPN','callback_data':'my'},{'text':'♻️ Продлить','callback_data':'renew'}],
        [{'text':'ℹ️ Помощь','callback_data':'help'}]
    ]},ensure_ascii=False)

def send(chat,text,markup=True):
    tg('sendMessage',{'chat_id':chat,'text':text,'parse_mode':'HTML','reply_markup':menu() if markup else ''})

def send_vpn(chat,uid,username):
    try:
        cid,expires,created=issue(uid,username, int(env().get('VPN_DEFAULT_DAYS','30')))
        conf=conf_bytes(cid);qr=qr_bytes(cid)
        tg('sendMessage',{'chat_id':chat,'text':f'✅ <b>VPN готов</b>\nСрок до: <b>{fmt(expires)}</b>\nAWG 3.1 · Strong Mobile'})
        tg('sendDocument',{'chat_id':chat,'document':'attach://config','caption':'📄 Конфигурация AmneziaWG','parse_mode':'HTML'},files={'config':conf})
        tg('sendPhoto',{'chat_id':chat,'photo':'attach://qr','caption':'📲 QR-код для подключения'},files={'qr':qr})
    except Exception as e:
        send(chat,'❌ Не удалось создать VPN-профиль. Проверьте AWG и панель.',False)
        if admin(uid):send(chat,'<code>'+str(e).replace('&','&amp;')[:1000]+'</code>',False)

def multipart_request(method,data,files):
    token=env().get('TELEGRAM_BOT_TOKEN','');url=f'https://api.telegram.org/bot{token}/{method}'
    boundary='----NOVABotBoundary'+str(int(time.time()*1000));body=bytearray()
    for k,v in data.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
    for k,(fn,content,mime) in files.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {mime}\r\n\r\n').encode()+content+b'\r\n'
    body += (f'--{boundary}--\r\n').encode()
    try:
        req=urllib.request.Request(url,data=bytes(body),headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
        return json.loads(urllib.request.urlopen(req,timeout=40).read().decode())
    except Exception:return {}

# Patch send_vpn's binary uploads through multipart Telegram API.
def deliver_vpn(chat,uid,username):
    try:
        cid,expires,_=issue(uid,username,int(env().get('VPN_DEFAULT_DAYS','30')))
        conf=conf_bytes(cid);qr=qr_bytes(cid)
        tg('sendMessage',{'chat_id':chat,'text':f'✅ <b>VPN готов</b>\nСрок до: <b>{fmt(expires)}</b>\nAWG 3.1 · Strong Mobile','parse_mode':'HTML'})
        multipart_request('sendDocument',{'chat_id':chat,'caption':'📄 Конфигурация AmneziaWG'}, {'document':('NOVA-'+str(cid)+'.conf',conf,'text/plain')})
        multipart_request('sendPhoto',{'chat_id':chat,'caption':'📲 QR-код для подключения'}, {'photo':('NOVA-'+str(cid)+'.png',qr,'image/png')})
    except Exception as e:
        send(chat,'❌ Не удалось создать VPN-профиль. Проверьте AWG и панель.',False)
        if admin(uid):send(chat,'<code>'+str(e).replace('&','&amp;')[:1000]+'</code>',False)

def process_update(u):
    if 'callback_query' in u:
        q=u['callback_query'];uid=q['from']['id'];chat=q['message']['chat']['id'];data=q.get('data','')
        tg('answerCallbackQuery',{'callback_query_id':q['id']})
        if not allowed(uid):send(chat,'⛔ Доступ запрещён.',False);return
        if data=='get':deliver_vpn(chat,uid,q['from'].get('username',''))
        elif data=='my':show_my(chat,uid)
        elif data=='renew':renew(chat,uid,q['from'].get('username',''))
        elif data=='help':send(chat,'<b>NOVA VPN Bot</b>\n\nПолучить VPN — создаёт AWG 3.1 профиль.\nМой VPN — показывает срок.\nПродлить — добавляет срок и восстанавливает доступ после истечения.',True)
        return
    if 'message' in u:
        m=u['message'];uid=m['from']['id'];chat=m['chat']['id'];cmd=(m.get('text') or '').split()[0].lower()
        if not allowed(uid):send(chat,'⛔ Доступ запрещён.',False);return
        if cmd in ('/start','/help'):send(chat,'🚀 <b>NOVA Network Control Center</b>\n\nУправление AmneziaWG 3.1 прямо из Telegram.',True)
        elif cmd in ('/vpn','/get'):deliver_vpn(chat,uid,m['from'].get('username',''))
        elif cmd in ('/myvpn','/my'):show_my(chat,uid)
        elif cmd=='/renew':renew(chat,uid,m['from'].get('username',''))
        elif cmd=='/admin' and admin(uid):
            c=db();n=c.execute('SELECT COUNT(*) FROM telegram_subscriptions').fetchone()[0];c.close();send(chat,f'🛠 Подписчиков: <b>{n}</b>\nDefault: {env().get("VPN_DEFAULT_DAYS","30")} дней',True)
        else:send(chat,'Используйте кнопки меню.',True)

def show_my(chat,uid):
    s=subscription(uid)
    if not s:send(chat,'📱 У вас пока нет VPN-профиля.',True);return
    c=client_row(s['client_id']);now=int(time.time());active=bool(s['active']) and s['expires']>now
    state='🟢 Активен' if active else '🔴 Истёк'
    send(chat,f'📱 <b>{c["name"] if c else "NOVA VPN"}</b>\nIP: <code>{c["address"] if c else "-"}</code>\nСтатус: <b>{state}</b>\nДо: <b>{fmt(s["expires"])}</b>',True)

def renew(chat,uid,username):
    s=subscription(uid)
    if not s:send(chat,'Сначала нажмите «🔐 Получить VPN».',True);return
    try:
        cid,expires,_=issue(uid,username,int(env().get('VPN_DEFAULT_DAYS','30')))
        send(chat,f'♻️ <b>VPN продлён</b>\nЕщё {env().get("VPN_DEFAULT_DAYS","30")} дней.\nДо: <b>{fmt(expires)}</b>',True)
    except Exception:send(chat,'❌ Не удалось продлить VPN.',True)

def expire_once():
    now=int(time.time());c=db();rows=c.execute('SELECT * FROM telegram_subscriptions WHERE active=1 AND expires<=?',(now,)).fetchall()
    for s in rows:
        cl=client_row(s['client_id'])
        if cl:set_peer_enabled(cl['public_key'],False,s['peer_block'])
        c.execute('UPDATE telegram_subscriptions SET active=0 WHERE telegram_id=?',(s['telegram_id'],))
    c.commit();c.close()
    for s in rows:
        try:send(s['telegram_id'],'⏰ <b>Срок VPN закончился.</b>\nНажмите «♻️ Продлить», чтобы восстановить доступ.',True)
        except Exception:pass

def loop():
    init_db();offset=0;last_expire=0
    while True:
        if time.time()-last_expire>60:expire_once();last_expire=time.time()
        r=tg('getUpdates',{'offset':offset,'timeout':25,'allowed_updates':'["message","callback_query"]'},35)
        if not r.get('ok'):time.sleep(3);continue
        for u in r.get('result',[]):
            offset=u['update_id']+1
            try:process_update(u)
            except Exception:pass

def register(app):
    mod=__import__('app')
    if hasattr(mod,'nav') and not getattr(mod.nav,'_telegram_wrapped',False):
        original=mod.nav
        def nav2(p):return original(p)+f'<a class="{"active" if p=="/telegram" else ""}" href="/telegram">🤖&nbsp;&nbsp;Telegram Bot</a>'
        nav2._telegram_wrapped=True;mod.nav=nav2
    @app.route('/telegram',methods=['GET','POST'])
    def telegram_page():
        if request.method=='POST':
            action=request.form.get('action','')
            if action=='save':
                token=request.form.get('token','').strip();idsv=request.form.get('ids','').strip();notify='1' if request.form.get('notify') else '0'
                if not token or not idsv:return redirect('/telegram?err=Заполните%20Token%20и%20Telegram%20ID')
                # Validate token before storing it.
                test=tg('getMe') if token==env().get('TELEGRAM_BOT_TOKEN','') else {}
                if token!=env().get('TELEGRAM_BOT_TOKEN',''):
                    try:
                        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/getMe')
                        test=json.loads(urllib.request.urlopen(req,timeout=8).read().decode())
                    except Exception:test={}
                if not test.get('ok'):return redirect('/telegram?err=Token%20не%20прошёл%20проверку')
                save_env(token,idsv,notify);run('systemctl','daemon-reload');run('systemctl','enable',SERVICE);run('systemctl','restart',SERVICE);return redirect('/telegram?ok=Бот%20подключён')
            if action=='test':
                first=env().get('TELEGRAM_ADMIN_IDS','').split(',')[0].strip();r=tg('getMe');bot=r.get('result',{}).get('username','')
                if bot and first:tg('sendMessage',{'chat_id':first,'text':'✅ NOVA: Telegram Bot подключён.\nБот: @'+bot})
            elif action=='start':run('systemctl','enable','--now',SERVICE)
            elif action=='stop':run('systemctl','disable','--now',SERVICE)
            elif action=='restart':run('systemctl','restart',SERVICE)
            return redirect('/telegram')
        e=env();active=status(SERVICE);token=e.get('TELEGRAM_BOT_TOKEN','');idsv=e.get('TELEGRAM_ADMIN_IDS','');msg=request.args.get('err') or request.args.get('ok','')
        masked=('*'*8+token[-4:]) if len(token)>4 else ('*'*len(token))
        body=render_template_string('''<div class=hero><div><div class=eyebrow>TELEGRAM</div><h1>Telegram Bot</h1><p>Выдача и продление AWG 3.1 профилей.</p></div></div>{% if msg %}<div class="notice">{{msg}}</div>{% endif %}<div class=card><div class=notice>Сервис: <b class="{{'ok' if active else 'bad'}}">{{'ONLINE' if active else 'OFFLINE'}}</b></div><form method=post><input type=hidden name=action value=save><label>Bot Token</label><input name=token type=password value="{{token}}" placeholder="123456:ABC..." required><label>Telegram ID администратора</label><input name=ids value="{{ids}}" placeholder="123456789" required><label style="display:flex;gap:10px;align-items:center"><input type=checkbox name=notify value=1 {% if e.get('TELEGRAM_NOTIFY')=='1' %}checked{% endif %}> Уведомления</label><button>💾 Проверить, сохранить и запустить</button></form><p class=muted>Токен хранится только на VPS в /etc/awg31-panel/telegram.env (600). В Git токен не попадает.</p></div><div class=card style="margin-top:16px"><h2>Управление</h2><form method=post><button name=action value=test>📨 Тест</button> <button name=action value=start>▶ Запустить</button> <button name=action value=restart>🔄 Перезапустить</button> <button class=btn alt name=action value=stop>⏹ Остановить</button></form></div>''',active=active,token='',masked=masked,ids=idsv,e=e,msg=msg)
        # Never render the real token back into HTML; the password field is intentionally blank.
        return mod.layout('Telegram Bot',body,'/telegram')
    
if __name__=='__main__':loop()
