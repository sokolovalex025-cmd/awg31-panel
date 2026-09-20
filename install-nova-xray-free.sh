#!/usr/bin/env bash
set -euo pipefail
APP=/opt/nova-xray-free
PORT=\${NOVA_UI_PORT:-9091}
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip curl ca-certificates jq iproute2 iptables ufw
if ! command -v xray >/dev/null 2>&1; then
  curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray-install.sh
  bash /tmp/xray-install.sh install
fi
mkdir -p "$APP/app" "$APP/templates" "$APP/static" "$APP/data" /etc/xray
cat > "$APP/requirements.txt" <<'REQ'
fastapi==0.116.1
uvicorn[standard]==0.35.0
jinja2==3.1.6
python-multipart==0.0.20
REQ
cat > "$APP/app/main.py" <<'PY'
from fastapi import FastAPI,Request,Form
from fastapi.responses import HTMLResponse,JSONResponse,PlainTextResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import subprocess,json,uuid,time,shutil,secrets,urllib.parse,re,socket
APP=Path("/opt/nova-xray-free"); DATA=APP/"data"; DATA.mkdir(parents=True,exist_ok=True)
C=DATA/"clients.json"; I=DATA/"inbounds.json"; X=Path("/etc/xray"); CFG=X/"config.json"; BAK=X/"nova-xray-free.bak"
V="1.0.0"; app=FastAPI(title="NOVA X-ray Free",version=V); t=Jinja2Templates(directory=str(APP/"templates"))
def run(c,timeout=15):
 try:
  p=subprocess.run(c,shell=True,text=True,capture_output=True,timeout=timeout); return p.returncode,p.stdout.strip(),p.stderr.strip()
 except Exception as e:return 99,"",str(e)
def load(p,d):
 try:return json.loads(p.read_text()) if p.exists() else d
 except:return d
def save(p,x):
 q=p.with_suffix(".tmp");q.write_text(json.dumps(x,ensure_ascii=False,indent=2));q.replace(p)
def active(s):return run("systemctl is-active "+s)[1]=="active"
def ip():return run("hostname -I | awk '{print $1}'")[1] or socket.getfqdn()
def keys():
 r,o,e=run("xray x25519")
 if r:return None
 a={}
 for l in o.splitlines():
  if "Private key:" in l:a["private"]=l.split(":",1)[1].strip()
  if "Public key:" in l:a["public"]=l.split(":",1)[1].strip()
 return a if len(a)==2 else None
def inbounds():
 a=load(I,[])
 if not a:
  x={"id":str(uuid.uuid4()),"tag":"nova-vless-reality","protocol":"vless","port":443,"security":"reality","serverName":"www.microsoft.com","network":"tcp","shortIds":[secrets.token_hex(4)]}
  k=keys()
  if k:x.update(k)
  a=[x];save(I,a)
 if not C.exists():save(C,[])
 return a
def config():
 out=[]
 for i in inbounds():
  cs=[c for c in load(C,[]) if c.get("enabled",True) and c.get("protocol")==i["protocol"]]
  p=i["protocol"]
  if p=="vless":
   st={"network":i.get("network","tcp"),"security":i.get("security","none")}
   if st["security"]=="reality":
    st["realitySettings"]={"show":False,"dest":i.get("serverName","www.microsoft.com")+":443","xver":0,"serverNames":[i.get("serverName","www.microsoft.com")],"privateKey":i.get("private",""),"shortIds":i.get("shortIds",[])}
   out.append({"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"vless","settings":{"clients":[{"id":c["uuid"],"email":c["name"]} for c in cs],"decryption":"none"},"streamSettings":st})
  elif p=="trojan":
   out.append({"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"trojan","settings":{"clients":[{"password":c["password"],"email":c["name"]} for c in cs]},"streamSettings":{"network":"tcp","security":"none"}})
  elif p=="shadowsocks":
   out.append({"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"shadowsocks","settings":{"method":"aes-128-gcm","password":i.get("password","CHANGE-ME")}})
 return {"log":{"loglevel":"warning"},"inbounds":out,"outbounds":[{"protocol":"freedom","tag":"direct"},{"protocol":"blackhole","tag":"blocked"}]}
def checks():
 a=[("Xray installed",shutil.which("xray") is not None),("Xray service",active("xray")),("NOVA service",active("nova-xray-free")),("AmneziaWG installed",shutil.which("awg") is not None or shutil.which("awg-quick") is not None),("IPv4 forwarding",run("sysctl -n net.ipv4.ip_forward")[1]=="1"),("DNS resolution",bool(run("getent hosts cloudflare.com")[1])),("Default route",bool(run("ip route show default")[1]))]
 for i in inbounds():a.append((f"Port {i['port']} listening",run(f"ss -lntup | grep -E '[:.]({i['port']})\\b'")[0]==0))
 z=X/"nova-test.json";z.write_text(json.dumps(config()));r,_,e=run(f"xray run -test -config {z}",20);z.unlink(missing_ok=True);a.append(("Xray config validation",r==0))
 return [{"name":n,"ok":bool(v)} for n,v in a]
def uri(c):
 i=next((x for x in inbounds() if x["protocol"]==c["protocol"]),None)
 if not i:return ""
 h=ip()
 if c["protocol"]=="vless":
  q={"type":i.get("network","tcp"),"security":i.get("security","none")}
  if i.get("security")=="reality":q.update({"pbk":i.get("public",""),"fp":"chrome","sni":i.get("serverName","www.microsoft.com"),"sid":i.get("shortIds",[""])[0]})
  return f"vless://{c['uuid']}@{h}:{i['port']}?{urllib.parse.urlencode(q)}#{urllib.parse.quote(c['name'])}"
 if c["protocol"]=="trojan":return f"trojan://{urllib.parse.quote(c['password'])}@{h}:{i['port']}#{urllib.parse.quote(c['name'])}"
 return ""
@app.get("/",response_class=HTMLResponse)
async def home(request:Request):return t.TemplateResponse("index.html",{"request":request,"version":V})
@app.get("/health")
async def health():return {"status":"ok","version":V,"name":"NOVA X-ray Free"}
@app.get("/api/status")
async def status():return {"xray":active("xray"),"panel":active("nova-xray-free"),"ip":ip(),"clients":len(load(C,[]))}
@app.get("/api/diagnostics")
async def diagnostics():return {"checks":checks()}
@app.get("/api/inbounds")
async def get_i():return inbounds()
@app.post("/api/inbounds")
async def add_i(tag:str=Form(...),protocol:str=Form(...),port:int=Form(...),security:str=Form("none"),serverName:str=Form("www.microsoft.com")):
 a=inbounds()
 if not 1<=port<=65535 or any(x["tag"]==tag or x["port"]==port for x in a):return JSONResponse({"ok":False,"error":"tag or port exists"},400)
 x={"id":str(uuid.uuid4()),"tag":tag,"protocol":protocol,"port":port,"security":security,"serverName":serverName,"network":"tcp","shortIds":[secrets.token_hex(4)]}
 if protocol=="vless" and security=="reality":x.update(keys() or {})
 a.append(x);save(I,a);return {"ok":True,"inbound":x}
@app.delete("/api/inbounds/{id}")
async def del_i(id:str):
 a=inbounds();b=[x for x in a if x["id"]!=id]
 if len(a)==len(b):return JSONResponse({"ok":False,"error":"not found"},404)
 save(I,b);return {"ok":True}
@app.get("/api/clients")
async def get_c():return load(C,[])
@app.post("/api/clients")
async def add_c(name:str=Form(...),protocol:str=Form("vless")):
 name=re.sub(r"[^A-Za-z0-9_.@-]+","-",name.strip())[:64];a=load(C,[])
 if not name or any(x["name"].lower()==name.lower() for x in a):return JSONResponse({"ok":False,"error":"invalid or duplicate name"},400)
 c={"id":str(uuid.uuid4()),"name":name,"protocol":protocol,"uuid":str(uuid.uuid4()),"password":secrets.token_urlsafe(18),"enabled":True,"created_at":int(time.time())};a.append(c);save(C,a);return {"ok":True,"client":c,"config":uri(c)}
@app.patch("/api/clients/{id}")
async def patch_c(id:str,enabled:bool=Form(...)):
 a=load(C,[]);c=next((x for x in a if x["id"]==id),None)
 if not c:return JSONResponse({"ok":False,"error":"not found"},404)
 c["enabled"]=enabled;save(C,a);return {"ok":True}
@app.delete("/api/clients/{id}")
async def del_c(id:str):
 a=load(C,[]);b=[x for x in a if x["id"]!=id]
 if len(a)==len(b):return JSONResponse({"ok":False,"error":"not found"},404)
 save(C,b);return {"ok":True}
@app.get("/api/clients/{id}/config")
async def client_config(id:str):
 c=next((x for x in load(C,[]) if x["id"]==id),None)
 return PlainTextResponse(uri(c) if c else "",status_code=200 if c else 404)
@app.get("/api/config")
async def get_config():return config()
@app.post("/api/apply")
async def apply():
 X.mkdir(parents=True,exist_ok=True);z=X/"nova-xray-free.tmp";z.write_text(json.dumps(config(),indent=2));r,o,e=run(f"xray run -test -config {z}",20)
 if r:z.unlink(missing_ok=True);return JSONResponse({"ok":False,"error":o or e},400)
 if CFG.exists():shutil.copy2(CFG,BAK)
 shutil.copy2(z,CFG);z.unlink(missing_ok=True);r,o,e=run("systemctl enable xray && systemctl restart xray",20)
 return {"ok":r==0,"restarted":r==0,"error":e if r else ""}
@app.post("/api/rollback")
async def rollback():
 if not BAK.exists():return JSONResponse({"ok":False,"error":"backup not found"},404)
 shutil.copy2(BAK,CFG);run("systemctl restart xray",20);return {"ok":True}
@app.post("/api/restart/{s}")
async def restart(s:str):
 if s not in ("xray","nova-xray-free"):return JSONResponse({"ok":False,"error":"not allowed"},400)
 r,o,e=run("systemctl restart "+s,20);return {"ok":r==0,"output":o or e}
@app.get("/api/logs")
async def logs():return PlainTextResponse(run("journalctl -u xray -n 100 --no-pager")[1])
@app.get("/api/system")
async def system():return {"hostname":socket.gethostname(),"ip":ip(),"uptime":run("uptime -p")[1],"memory":run("free -h | awk '/Mem:/ {print $3\" / \"$2}'")[1],"disk":run("df -h / | awk 'NR==2 {print $3\" / \"$2}'")[1]}
PY
cat > "$APP/templates/index.html" <<'HTML'
<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA X-ray Free</title><link rel="stylesheet" href="/static/style.css"><body>
<aside><div class="logo">✦ NOVA <b>X-ray Free</b></div><nav><button onclick="tab('dash')">⌂ Дашборд</button><button onclick="tab('in')">◈ Inbounds</button><button onclick="tab('cl')">♙ Клиенты</button><button onclick="tab('dg')">⚕ Диагностика</button><button onclick="tab('cf')">⚙ Конфигурация</button><button onclick="tab('lg')">▤ Логи</button></nav><small>VLESS · Reality · Trojan · Shadowsocks<br>AmneziaWG · v<span id="v"></span></small></aside>
<main><header><div><h1 id="h">Дашборд</h1><p>Управление Xray и VPN-доступом</p></div><div><button onclick="refresh()">↻</button> <button class="primary" onclick="apply()">✓ Применить</button></div></header>
<section id="dash" class="tab"><div class="cards"><div><small>Xray</small><b id="sx">—</b></div><div><small>NOVA</small><b id="sp">—</b></div><div><small>IP</small><b id="ip">—</b></div><div><small>Клиенты</small><b id="cc">—</b></div></div><div class="panel"><h2>Быстрые действия</h2><button onclick="createClient()">＋ Клиент</button><button onclick="createInbound()">＋ Inbound</button><button onclick="tab('dg');diag()">🔍 Диагностика</button><button onclick="restart('xray')">↻ Restart Xray</button></div><div class="panel"><h2>Система</h2><pre id="sys"></pre></div></section>
<section id="in" class="tab hide"><div class="panel"><h2>Inbound <button class="primary" onclick="createInbound()">＋ Добавить</button></h2><div id="il"></div></div></section>
<section id="cl" class="tab hide"><div class="panel"><h2>Клиенты <button class="primary" onclick="createClient()">＋ Создать</button></h2><div id="cll"></div></div></section>
<section id="dg" class="tab hide"><div class="panel"><h2>Диагностика <button onclick="diag()">↻</button></h2><div id="checks"></div></div></section>
<section id="cf" class="tab hide"><div class="panel"><h2>Конфигурация</h2><pre id="json"></pre><button onclick="loadConfig()">Загрузить</button> <button onclick="rollback()">↶ Откат</button></div></section>
<section id="lg" class="tab hide"><div class="panel"><h2>Логи Xray <button onclick="logs()">↻</button></h2><pre id="log"></pre></div></section></main>
<script>
const $=x=>document.querySelector(x);async function j(u,o){let r=await fetch(u,o),t=await r.text();try{return JSON.parse(t)}catch{return t}}
function tab(x){document.querySelectorAll('.tab').forEach(e=>e.classList.add('hide'));$('#'+x).classList.remove('hide');$('#h').textContent={dash:'Дашборд',in:'Inbound',cl:'Клиенты',dg:'Диагностика',cf:'Конфигурация',lg:'Логи'}[x];if(x=='in')loadI();if(x=='cl')loadC();if(x=='dg')diag();if(x=='cf')loadConfig();if(x=='lg')logs()}
async function refresh(){let s=await j('/api/status'),y=await j('/api/system');$('#sx').textContent=s.xray?'ONLINE':'OFFLINE';$('#sp').textContent=s.panel?'ONLINE':'OFFLINE';$('#ip').textContent=s.ip;$('#cc').textContent=s.clients;$('#v').textContent='1.0.0';$('#sys').textContent=JSON.stringify(y,null,2);loadI();loadC()}
async function loadI(){let a=await j('/api/inbounds');$('#il').innerHTML=a.map(x=>'<div class="row"><b>'+x.tag+'</b><span>'+x.protocol+' :'+x.port+' '+(x.security||'')+' <button onclick="delI(\\''+x.id+'\\')">Удалить</button></span></div>').join('')}
async function loadC(){let a=await j('/api/clients');$('#cll').innerHTML=a.map(x=>'<div class="row"><b>'+x.name+'</b><span>'+x.protocol+' · '+(x.enabled?'ON':'OFF')+' <button onclick="showC(\\''+x.id+'\\')">Конфиг</button><button onclick="toggleC(\\''+x.id+'\\','+!x.enabled+')">'+(x.enabled?'OFF':'ON')+'</button><button onclick="delC(\\''+x.id+'\\')">Удалить</button></span></div>').join('')||'<p>Нет клиентов</p>'}
async function diag(){let x=await j('/api/diagnostics');tab('dg');$('#checks').innerHTML=x.checks.map(a=>'<div class="check '+(a.ok?'ok':'bad')+'">'+(a.ok?'✓':'✕')+' '+a.name+' <b>'+(a.ok?'OK':'ОШИБКА')+'</b></div>').join('')}
function modal(title,html,cb){let d=document.createElement('div');d.className='modal';d.innerHTML='<div class="box"><button class="x" onclick="this.parentNode.parentNode.remove()">×</button><h2>'+title+'</h2><form>'+html+'</form></div>';document.body.appendChild(d);d.querySelector('form').onsubmit=async e=>{e.preventDefault();await cb(new FormData(e.target));d.remove();refresh()}}
function createClient(){modal('Новый клиент','<input name="name" placeholder="client-01" required><select name="protocol"><option>vless</option><option>trojan</option><option>shadowsocks</option></select><button class="primary">Создать</button>',async f=>{let x=await j('/api/clients',{method:'POST',body:f});if(x.config)prompt('Готовый конфиг',x.config)})}
function createInbound(){modal('Новый inbound','<input name="tag" value="nova-vless-reality" required><select name="protocol"><option>vless</option><option>trojan</option><option>shadowsocks</option></select><input name="port" type="number" value="443"><select name="security"><option>reality</option><option>none</option></select><input name="serverName" value="www.microsoft.com"><button class="primary">Добавить</button>',async f=>{let x=await j('/api/inbounds',{method:'POST',body:f});if(!x.ok)alert(x.error)})}
async function showC(id){let x=await j('/api/clients/'+id+'/config');prompt('VPN конфиг',x)}
async function delC(id){if(confirm('Удалить клиента?')){await fetch('/api/clients/'+id,{method:'DELETE'});refresh()}}
async function toggleC(id,v){let f=new FormData();f.append('enabled',v);await fetch('/api/clients/'+id,{method:'PATCH',body:f});refresh()}
async function delI(id){if(confirm('Удалить inbound?')){await fetch('/api/inbounds/'+id,{method:'DELETE'});refresh()}}
async function apply(){let x=await j('/api/apply',{method:'POST'});alert(x.ok?'Готово: конфигурация проверена и Xray перезапущен':x.error);refresh()}
async function rollback(){let x=await j('/api/rollback',{method:'POST'});alert(x.ok?'Откат выполнен':x.error);refresh()}
async function restart(s){let x=await j('/api/restart/'+s,{method:'POST'});alert(x.ok?'Перезапущено':x.output);refresh()}
async function loadConfig(){$('#json').textContent=JSON.stringify(await j('/api/config'),null,2)}
async function logs(){$('#log').textContent=await j('/api/logs')}
refresh();
</script></body></html>
HTML
cat > "$APP/static/style.css" <<'CSS'
:root{--bg:#070b13;--p:#0e1625;--p2:#121e31;--l:#24324a;--t:#edf4ff;--m:#8190a8;--a:#58e6a8;--d:#ff6478}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 0,#142a42,#070b13 45%);color:var(--t);font:14px system-ui}aside{position:fixed;inset:0 auto 0 0;width:240px;background:#090e18;border-right:1px solid var(--l);padding:25px 14px;display:flex;flex-direction:column}.logo{font-size:21px;font-weight:800;margin:0 10px 30px}.logo b{color:var(--a)}nav{display:grid;gap:5px}nav button{background:none;border:0;color:#a9b5c8;text-align:left;padding:12px;border-radius:9px}nav button:hover{background:var(--p2);color:#fff}aside small{margin-top:auto;color:var(--m);line-height:1.7}main{margin-left:240px;padding:30px;max-width:1400px}header{display:flex;justify-content:space-between;align-items:center;margin-bottom:25px}h1{margin:0 0 5px;font-size:28px}header p{margin:0;color:var(--m)}button,input,select{padding:10px 13px;border:1px solid #30405c;background:#0b1320;color:#fff;border-radius:9px;margin:3px}button{cursor:pointer}.primary{background:var(--a);color:#06100b;border-color:var(--a);font-weight:800}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.cards>div,.panel{background:rgba(14,22,37,.94);border:1px solid var(--l);border-radius:15px}.cards>div{padding:20px}.cards small{display:block;color:var(--m);margin-bottom:10px}.cards b{font-size:19px}.panel{padding:20px;margin-top:16px}.panel h2{margin:0 0 15px;font-size:17px}.row{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:14px 2px;border-top:1px solid var(--l)}.check{padding:13px;border-bottom:1px solid var(--l)}.check b{float:right}.ok{color:var(--a)}.bad{color:var(--d)}pre{background:#080d16;padding:15px;border-radius:10px;overflow:auto;max-height:600px}.hide{display:none}.modal{position:fixed;inset:0;background:#000b;display:grid;place-items:center;padding:20px}.box{width:min(460px,100%);background:var(--p);border:1px solid var(--l);border-radius:15px;padding:25px;position:relative}.box form{display:grid;gap:8px}.x{position:absolute;right:12px;top:10px;background:none;border:0;font-size:22px}@media(max-width:800px){aside{position:static;width:auto;height:auto;display:block}.logo{margin-bottom:15px}nav{grid-template-columns:repeat(3,1fr)}aside small{display:none}main{margin:0;padding:15px}header{flex-direction:column;align-items:flex-start;gap:12px}.cards{grid-template-columns:repeat(2,1fr)}.row{align-items:flex-start;flex-direction:column}}
CSS
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"
cat > /etc/systemd/system/nova-xray-free.service <<EOF
[Unit]
Description=NOVA X-ray Free Panel
After=network-online.target xray.service
Wants=network-online.target
[Service]
WorkingDirectory=$APP
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now xray || true
systemctl enable --now nova-xray-free
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then ufw allow \${PORT}/tcp >/dev/null || true; fi
echo "NOVA X-ray Free: http://SERVER-IP:\$PORT"
