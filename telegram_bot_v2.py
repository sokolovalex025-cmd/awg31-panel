#!/usr/bin/env python3
"""NOVA Telegram Bot v2 wrapper.
Keeps the existing self-service bot and adds an admin control plane plus NOVA route diff monitoring.
"""
import html, ipaddress, json, re, time, urllib.request
from pathlib import Path
import telegram_bot as base

BASE=Path('/opt/awg31-panel'); ROUTES_STATE=BASE/'nova_routes_state.json'; ROUTES_HISTORY=BASE/'nova_routes_history.jsonl'

def admin_menu():
 return json.dumps({'inline_keyboard':[[{'text':'📊 Статус','callback_data':'admin_status'},{'text':'👥 Клиенты','callback_data':'admin_users'}],[{'text':'🛡 NOVA Routes','callback_data':'admin_routes'},{'text':'🔄 Проверить Routes','callback_data':'admin_routes_check'}],[{'text':'⚙️ AWG','callback_data':'admin_awg'},{'text':'ℹ️ Помощь','callback_data':'admin_help'}]]},ensure_ascii=False)

def send_admin(chat,text): base.tg('sendMessage',{'chat_id':chat,'text':text,'parse_mode':'HTML','reply_markup':admin_menu()})

def route_source():
 e=base.env(); return e.get('NOVA_ROUTES_URL','').strip(),e.get('NOVA_ROUTES_FILE','').strip()

def parse_routes(text):
 routes=set()
 for raw in text.splitlines():
  line=raw.strip()
  if not line or line.startswith('#') or line.startswith(';'): continue
  for token in re.split(r'[\s,;]+',line):
   token=token.strip('"\'')
   if '/' not in token: continue
   try: routes.add(str(ipaddress.ip_network(token,strict=False)))
   except ValueError: pass
 return routes

def load_routes():
 url,path=route_source()
 if url:
  req=urllib.request.Request(url,headers={'User-Agent':'NOVA-Route-Monitor/1.0'})
  with urllib.request.urlopen(req,timeout=25) as r: data=r.read()
  if not data or len(data)>50*1024*1024: raise RuntimeError('feed is empty or too large')
  return parse_routes(data.decode('utf-8','replace'))
 if path:
  p=Path(path)
  if not p.exists(): raise RuntimeError('NOVA_ROUTES_FILE not found')
  data=p.read_text(errors='replace')
  if not data.strip(): raise RuntimeError('feed is empty')
  return parse_routes(data)
 raise RuntimeError('NOVA_ROUTES_URL or NOVA_ROUTES_FILE is not configured')

def read_state():
 try: return json.loads(ROUTES_STATE.read_text())
 except Exception: return {}

def check_routes(notify=True):
 current=load_routes(); old=set(read_state().get('routes',[]))
 key=lambda x:(ipaddress.ip_network(x).version,ipaddress.ip_network(x).network_address,ipaddress.ip_network(x).prefixlen)
 added=sorted(current-old,key=key); removed=sorted(old-current,key=key)
 ROUTES_STATE.write_text(json.dumps({'checked':int(time.time()),'count':len(current),'routes':sorted(current)},ensure_ascii=False,indent=2))
 with ROUTES_HISTORY.open('a') as f: f.write(json.dumps({'ts':int(time.time()),'count':len(current),'added':added,'removed':removed})+'\n')
 if notify and (added or removed):
  lines=[f'🛡 <b>NOVA Routes изменились</b>',f'Маршрутов: <b>{len(old)} → {len(current)}</b>',f'Добавлено: <b>{len(added)}</b>',f'Удалено: <b>{len(removed)}</b>']
  if added: lines.append('➕ <code>'+html.escape('\n'.join(added[:80]))+'</code>')
  if removed: lines.append('➖ <code>'+html.escape('\n'.join(removed[:80]))+'</code>')
  if len(added)>80 or len(removed)>80: lines.append('… показаны первые 80 записей каждой группы')
  for uid in base.ids('TELEGRAM_ADMIN_IDS'): base.tg('sendMessage',{'chat_id':uid,'text':'\n'.join(lines),'parse_mode':'HTML'})
 return len(old),len(current),added,removed

def status_text():
 awg=base.status('awg-quick@awg0'); bot=base.status(base.SERVICE); c=base.db(); users=c.execute('SELECT COUNT(*) FROM telegram_subscriptions').fetchone()[0]; active=c.execute('SELECT COUNT(*) FROM telegram_subscriptions WHERE active=1 AND expires>?',(int(time.time()),)).fetchone()[0]; c.close(); st=read_state(); checked=st.get('checked'); when=time.strftime('%d.%m.%Y %H:%M',time.localtime(checked)) if checked else '—'
 return f'📊 <b>NOVA Status</b>\n\nAWG: <b>{"🟢 ONLINE" if awg else "🔴 OFFLINE"}</b>\nBot: <b>{"🟢 ONLINE" if bot else "🔴 OFFLINE"}</b>\nКлиенты: <b>{users}</b>\nАктивные: <b>{active}</b>\nNOVA Routes: <b>{st.get("count","—")}</b>\nПоследняя проверка: <b>{when}</b>'

def users_text():
 c=base.db(); rows=c.execute('SELECT telegram_id,username,client_id,expires,active FROM telegram_subscriptions ORDER BY expires').fetchall(); c.close()
 if not rows:return '👥 <b>Клиенты</b>\n\nНет подписчиков.'
 out=['👥 <b>Клиенты</b>']
 for r in rows[:60]:
  state='🟢' if r['active'] and r['expires']>int(time.time()) else '🔴'; name=html.escape(r['username'] or str(r['telegram_id'])); out.append(f'{state} <b>{name}</b> · #{r["client_id"]} · до {base.fmt(r["expires"])}')
 if len(rows)>60: out.append(f'… ещё {len(rows)-60}')
 return '\n'.join(out)

def routes_text():
 st=read_state(); checked=st.get('checked'); when=time.strftime('%d.%m.%Y %H:%M:%S',time.localtime(checked)) if checked else 'нет данных'; url,_=route_source(); source=html.escape(url or 'локальный файл')
 return f'🛡 <b>NOVA Routes</b>\n\nИсточник: <code>{source}</code>\nCIDR: <b>{st.get("count",0)}</b>\nПроверено: <b>{when}</b>\n\nИзменений нет — уведомление не отправляется.'

def process(u):
 if 'callback_query' in u:
  q=u['callback_query']; uid=q['from']['id']; chat=q['message']['chat']['id']; data=q.get('data',''); base.tg('answerCallbackQuery',{'callback_query_id':q['id']})
  if not base.admin(uid): base.send(chat,'⛔ Только администратор.',False); return
  try:
   if data=='admin_status': base.send(chat,status_text(),True)
   elif data=='admin_users': base.send(chat,users_text(),True)
   elif data=='admin_routes': base.send(chat,routes_text(),True)
   elif data=='admin_routes_check':
    _,new,a,r=check_routes(True); base.send(chat,f'🔄 Проверка завершена\nМаршрутов: <b>{new}</b>\nДобавлено: <b>{len(a)}</b>\nУдалено: <b>{len(r)}</b>',True)
   elif data=='admin_awg': base.send(chat,f'⚙️ <b>AWG</b>\n\nСтатус: <b>{"🟢 ONLINE" if base.status("awg-quick@awg0") else "🔴 OFFLINE"}</b>',True)
   elif data=='admin_help': base.send(chat,'<b>Админ-панель NOVA</b>\n\nСтатус — состояние сервисов.\nКлиенты — подписчики Telegram.\nNOVA Routes — состояние feed.\nПроверить Routes — принудительная проверка и уведомление только при изменениях.',True)
  except Exception as exc: base.send(chat,'❌ Ошибка: <code>'+html.escape(str(exc)[:1000])+'</code>',True)
  return
 if 'message' in u:
  m=u['message']; uid=m['from']['id']; chat=m['chat']['id']; text=(m.get('text') or '').split()[0].lower()
  if text=='/admin' and base.admin(uid): send_admin(chat,status_text()); return
  if text=='/status' and base.admin(uid): base.send(chat,status_text(),True); return
  if text=='/routes' and base.admin(uid): base.send(chat,routes_text(),True); return
  if text=='/routes_check' and base.admin(uid):
   try:
    _,new,a,r=check_routes(True); base.send(chat,f'🔄 Проверка завершена\nМаршрутов: <b>{new}</b>\nДобавлено: <b>{len(a)}</b>\nУдалено: <b>{len(r)}</b>',True)
   except Exception as exc: base.send(chat,'❌ Routes: <code>'+html.escape(str(exc)[:1000])+'</code>',True)
   return
  base.process(u)

def loop():
 base.init_db(); offset=0; last_expire=0; last_routes=0; interval=max(300,int(base.env().get('NOVA_ROUTES_INTERVAL','900')))
 while True:
  now=time.time()
  if now-last_expire>60:
   try: base.expire_once()
   except Exception: pass
   last_expire=now
  if now-last_routes>interval:
   try: check_routes(True)
   except Exception: pass
   last_routes=now
  r=base.tg('getUpdates',{'offset':offset,'timeout':25,'allowed_updates':'["message","callback_query"]'},35)
  if not r.get('ok'): time.sleep(3); continue
  for u in r.get('result',[]):
   offset=u['update_id']+1
   try: process(u)
   except Exception: pass

if __name__=='__main__': loop()
