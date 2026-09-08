#!/usr/bin/env python3
import json,os,time,urllib.parse,urllib.request,subprocess
from pathlib import Path
BASE=Path('/opt/awg31-panel'); ENV=Path('/etc/awg31-panel/telegram.env'); SERVICE='awgpanel-telegram.service'
def env():
 d={}
 try:
  for line in ENV.read_text().splitlines():
   if '=' in line and not line.startswith('#'):
    k,v=line.split('=',1); d[k]=v.strip().strip('"')
 except Exception: pass
 return d
def save_env(token,ids):
 ENV.parent.mkdir(parents=True,exist_ok=True)
 ENV.write_text('TELEGRAM_BOT_TOKEN='+token+'\nTELEGRAM_ADMIN_IDS='+ids+'\n'); os.chmod(ENV,0o600)
def tg(method,data=None,timeout=40):
 e=env(); token=e.get('TELEGRAM_BOT_TOKEN','')
 if not token:return {}
 url='https://api.telegram.org/bot'+token+'/'+method
 req=urllib.request.Request(url,data=urllib.parse.urlencode(data or {}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 try:return json.loads(urllib.request.urlopen(req,timeout=timeout).read().decode())
 except Exception:return {}
def allowed(uid):
 e=env(); return str(uid) in [x.strip() for x in e.get('TELEGRAM_ADMIN_IDS','').split(',') if x.strip()]
def run(*a):
 try:return subprocess.run(a,text=True,capture_output=True,timeout=20)
 except Exception as x:return subprocess.CompletedProcess(a,1,'',str(x))
def status(s):return run('systemctl','is-active','--quiet',s).returncode==0
def metrics():
 a=status('awg-quick@awg0'); n=status('naiveproxy.service');
 r=run('awg','show','awg0','dump'); lines=[x for x in r.stdout.splitlines() if x.strip()]
 return a,n,len(lines)-1 if lines else 0
def menu():
 return json.dumps({'inline_keyboard':[[{'text':'📊 Статус','callback_data':'status'},{'text':'👥 Клиенты','callback_data':'clients'}],[{'text':'🛡 AWG','callback_data':'awg'},{'text':'🚀 NaïveProxy','callback_data':'naive'}],[{'text':'🔄 Перезапустить AWG','callback_data':'restart_awg'}]]},ensure_ascii=False)
def text_status():
 a,n,c=metrics(); return '🖥 <b>AWG Panel</b>\n\n🛡 AWG: <b>'+('ONLINE' if a else 'OFFLINE')+'</b>\n🚀 NaïveProxy: <b>'+('ONLINE' if n else 'OFFLINE')+'</b>\n👥 Peers: <b>'+str(c)+'</b>'
def send(chat,text,markup=True):tg('sendMessage',{'chat_id':chat,'text':text,'parse_mode':'HTML','reply_markup':menu() if markup else ''})
def loop():
 offset=0
 while True:
  r=tg('getUpdates',{'offset':offset,'timeout':25,'allowed_updates':'["message","callback_query"]'},35)
  if not r.get('ok'):time.sleep(3);continue
  for u in r.get('result',[]):
   offset=u['update_id']+1
   if 'callback_query' in u:
    q=u['callback_query']; uid=q['from']['id']; chat=q['message']['chat']['id']; data=q.get('data',''); tg('answerCallbackQuery',{'callback_query_id':q['id']})
    if not allowed(uid):send(chat,'⛔ Доступ запрещён.',False);continue
    if data=='status':send(chat,text_status())
    elif data=='awg':send(chat,'🛡 AWG: <b>'+('ONLINE' if status('awg-quick@awg0') else 'OFFLINE')+'</b>')
    elif data=='naive':send(chat,'🚀 NaïveProxy: <b>'+('ONLINE' if status('naiveproxy.service') else 'OFFLINE')+'</b>')
    elif data=='clients':send(chat,'👥 Клиентов/peers: <b>'+str(metrics()[2])+'</b>')
    elif data=='restart_awg':
     ok=run('systemctl','restart','awg-quick@awg0').returncode==0;send(chat,'🔄 AWG перезапущен.' if ok else '❌ Не удалось перезапустить AWG.')
   elif 'message' in u:
    m=u['message']; uid=m['from']['id'];chat=m['chat']['id'];cmd=(m.get('text') or '').split()[0].lower()
    if not allowed(uid):send(chat,'⛔ Доступ запрещён.',False);continue
    if cmd in ('/start','/help'):send(chat,'🤖 <b>AWG Panel Bot</b>\n\nУправление сервером и мониторинг AWG/NaïveProxy.',True)
    elif cmd=='/status':send(chat,text_status())
    elif cmd=='/restart':
     ok=run('systemctl','restart','awg-quick@awg0').returncode==0;send(chat,'🔄 AWG перезапущен.' if ok else '❌ Ошибка перезапуска.')
    else:send(chat,'Используйте /status или кнопки меню.',True)
def register(app):
 mod=__import__('app')
 if hasattr(mod,'nav') and not getattr(mod.nav,'_telegram_wrapped',False):
  original=mod.nav
  def nav2(p):
   return original(p)+f'<a class="{"active" if p=="/telegram" else ""}" href="/telegram">🤖&nbsp;&nbsp;Telegram Bot</a>'
  nav2._telegram_wrapped=True;mod.nav=nav2
 @app.route('/telegram',methods=['GET','POST'])
 def telegram_page():
  if request.method=='POST':
   from flask import request,redirect
   action=request.form.get('action','')
   if action=='save':
    save_env(request.form.get('token','').strip(),request.form.get('ids','').strip());run('systemctl','daemon-reload');run('systemctl','restart',SERVICE)
   elif action=='start':run('systemctl','enable','--now',SERVICE)
   elif action=='stop':run('systemctl','disable','--now',SERVICE)
   elif action=='restart':run('systemctl','restart',SERVICE)
   return redirect('/telegram')
  from flask import render_template_string
  e=env(); active=status(SERVICE); token=e.get('TELEGRAM_BOT_TOKEN',''); ids=e.get('TELEGRAM_ADMIN_IDS','')
  body=render_template_string('''<div class=hero><div><div class=eyebrow>TELEGRAM</div><h1>Telegram Bot</h1><p>Удалённое управление AWG Panel.</p></div></div><div class=card><div class=notice>Статус: <b class="{{'ok' if active else 'bad'}}">{{'ONLINE' if active else 'OFFLINE'}}</b></div><form method=post><input type=hidden name=action value=save><label>Bot Token</label><input name=token type=password value="{{token}}" placeholder="123456:ABC..." required><label>Разрешённые Telegram ID</label><input name=ids value="{{ids}}" placeholder="123456789,987654321" required><button>💾 Сохранить и запустить</button></form></div><div class=card style="margin-top:16px"><h2>Управление</h2><form method=post><button name=action value=start>▶ Запустить</button> <button name=action value=restart>🔄 Перезапустить</button> <button class=btn alt name=action value=stop>⏹ Остановить</button></form><p class=muted>Токен хранится в /etc/awg31-panel/telegram.env с правами 600.</p></div>''',active=active,token=token,ids=ids)
  return mod.layout('Telegram Bot',body,'/telegram')
if __name__=='__main__':loop()
