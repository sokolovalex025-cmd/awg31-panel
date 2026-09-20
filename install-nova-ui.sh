#!/usr/bin/env bash
set -euo pipefail

APP=/opt/nova-ui
PORT=${NOVA_UI_PORT:-8080}

echo "[NOVA-UI] Installing to $APP"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip iproute2 iptables curl

mkdir -p "$APP/app" "$APP/templates" "$APP/static" "$APP/data"

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
import subprocess,shutil,json,uuid,time,socket,urllib.parse,re

APP=Path("/opt/nova-ui"); DATA=APP/"data"; DATA.mkdir(parents=True,exist_ok=True)
CLIENTS=DATA/"clients.json"; INBOUNDS=DATA/"inbounds.json"
XRAY=Path("/etc/xray"); MANAGED=XRAY/"nova-managed.json"; BACKUP=XRAY/"nova-managed.json.bak"
app=FastAPI(title="NOVA-UI",version="0.3.1"); templates=Jinja2Templates(directory=str(APP/"templates"))

def run(c,t=10):
    try:
        p=subprocess.run(c,shell=True,text=True,capture_output=True,timeout=t)
        return p.returncode,(p.stdout or "").strip(),(p.stderr or "").strip()
    except Exception as e:return 99,"",str(e)
def load(p,d):
    try:return json.loads(p.read_text()) if p.exists() else d
    except:return d
def save(p,x):
    tmp=p.with_suffix(".tmp");tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2));tmp.replace(p)
def service(n):
    _,o,e=run("systemctl is-active "+n);return {"ok":o=="active","value":o or e or "unknown"}
def diagnostics(port=443):
    q=[("Xray installed",shutil.which("xray") is not None),
       ("AmneziaWG installed",shutil.which("awg") is not None or shutil.which("awg-quick") is not None),
       ("Xray service",service("xray")["ok"]),
       ("AWG interface",Path("/sys/class/net/awg0").exists())]
    q.append((f"Port {port} listening",run(f"ss -lntup | grep -E '[:.]({int(port)})\\b'")[0]==0))
    _,o,_=run("sysctl -n net.ipv4.ip_forward");q.append(("IPv4 forwarding",o=="1"))
    _,o,_=run("getent hosts cloudflare.com");q.append(("DNS resolution",bool(o)))
    _,o,_=run("ip route show default");q.append(("Default route",bool(o)))
    return [{"name":n,"ok":bool(v)} for n,v in q]
def cfg():
    ins=load(INBOUNDS,[{"id":"default","tag":"nova-vless","protocol":"vless","port":443}]);cs=load(CLIENTS,[])
    out=[]
    for i in ins:
        enabled=[{"id":c["uuid"],"email":c["name"]} for c in cs if c.get("enabled") and c.get("protocol","vless")==i["protocol"]]
        p=i["protocol"]
        if p=="vless": x={"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"vless","settings":{"clients":enabled,"decryption":"none"},"streamSettings":{"network":"tcp","security":"none"}}
        elif p=="trojan": x={"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"trojan","settings":{"clients":[{"password":c["password"],"email":c["name"]} for c in cs if c.get("enabled") and c.get("protocol")=="trojan"]},"streamSettings":{"network":"tcp","security":"none"}}
        else: x={"tag":i["tag"],"listen":"0.0.0.0","port":i["port"],"protocol":"shadowsocks","settings":{"method":"aes-128-gcm","password":"CHANGE-ME"}}
        out.append(x)
    return {"log":{"loglevel":"warning"},"inbounds":out,"outbounds":[{"protocol":"freedom","tag":"direct"}]}
@app.get("/",response_class=HTMLResponse)
async def index(request:Request):return templates.TemplateResponse("index.html",{"request":request})
@app.get("/health")
async def health():return {"status":"ok","version":"0.3.1"}
@app.get("/api/diagnostics")
async def diag(port:int=443):return {"timestamp":int(time.time()),"checks":diagnostics(port)}
@app.get("/api/inbounds")
async def get_i():return load(INBOUNDS,[{"id":"default","tag":"nova-vless","protocol":"vless","port":443}])
@app.post("/api/inbounds")
async def add_i(tag:str=Form(...),protocol:str=Form(...),port:int=Form(...)):
    a=load(INBOUNDS,[{"id":"default","tag":"nova-vless","protocol":"vless","port":443}])
    if not 1<=port<=65535:return JSONResponse({"ok":False,"error":"invalid port"},400)
    if any(x["tag"]==tag or x["port"]==port for x in a):return JSONResponse({"ok":False,"error":"tag or port exists"},409)
    x={"id":str(uuid.uuid4()),"tag":tag,"protocol":protocol,"port":port};a.append(x);save(INBOUNDS,a);return {"ok":True,"inbound":x}
@app.get("/api/clients")
async def get_c():return load(CLIENTS,[])
@app.post("/api/clients")
async def add_c(name:str=Form(...),protocol:str=Form("vless")):
    name=re.sub(r"[^A-Za-z0-9_.@-]+","-",name.strip())[:64];a=load(CLIENTS,[])
    if not name or any(x["name"].lower()==name.lower() for x in a):return JSONResponse({"ok":False,"error":"invalid or duplicate name"},400)
    c={"id":str(uuid.uuid4()),"name":name,"protocol":protocol,"uuid":str(uuid.uuid4()),"password":uuid.uuid4().hex,"enabled":True,"created_at":int(time.time())}
    a.append(c);save(CLIENTS,a);return {"ok":True,"client":c}
@app.delete("/api/clients/{cid}")
async def del_c(cid:str):
    a=load(CLIENTS,[]);b=[x for x in a if x["id"]!=cid]
    if len(a)==len(b):return JSONResponse({"ok":False,"error":"not found"},404)
    save(CLIENTS,b);return {"ok":True}
@app.get("/api/clients/{cid}/config")
async def get_config(cid:str):
    c=next((x for x in load(CLIENTS,[]) if x["id"]==cid),None)
    if not c:return JSONResponse({"ok":False,"error":"not found"},404)
    i=next((x for x in load(INBOUNDS,[{"id":"default","tag":"nova-vless","protocol":"vless","port":443}]) if x["protocol"]==c["protocol"]),None)
    if not i:return JSONResponse({"ok":False,"error":"matching inbound not found"},404)
    host=socket.getfqdn()
    if c["protocol"]=="vless":
        return PlainTextResponse(f"vless://{c['uuid']}@{host}:{i['port']}?type=tcp&security=none#{urllib.parse.quote(c['name'])}")
    if c["protocol"]=="trojan":return PlainTextResponse(f"trojan://{urllib.parse.quote(c['password'])}@{host}:{i['port']}#{urllib.parse.quote(c['name'])}")
    return JSONResponse({"client":c,"inbound":i})
@app.post("/api/apply")
async def apply():
    XRAY.mkdir(parents=True,exist_ok=True);tmp=MANAGED.with_suffix(".tmp");tmp.write_text(json.dumps(cfg(),indent=2))
    if shutil.which("xray"):
        rc,o,e=run("xray run -test -config '"+str(tmp)+"'",15)
        if rc:tmp.unlink(missing_ok=True);return JSONResponse({"ok":False,"stage":"validation","error":o or e},400)
    if MANAGED.exists():shutil.copy2(MANAGED,BACKUP)
    tmp.replace(MANAGED);return {"ok":True,"validated":True,"config":str(MANAGED),"restarted":False}
@app.post("/api/rollback")
async def rollback():
    if not BACKUP.exists():return JSONResponse({"ok":False,"error":"backup not found"},404)
    shutil.copy2(BACKUP,MANAGED);return {"ok":True}
PY

cat > "$APP/templates/index.html" <<'HTML'
<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVA-UI</title><link rel="stylesheet" href="/static/style.css"><body><main>
<h1>NOVA-UI <small id="v"></small></h1><p>Панель Xray + AmneziaWG</p>
<div class="grid"><button onclick="diag()">🔍 Диагностика</button><button onclick="apply()">⚙ Проверить и сохранить конфиг</button><button onclick="location.reload()">↻ Обновить</button></div>
<section><h2>Диагностика</h2><div id="d"></div></section>
<section><h2>Inbound</h2><form id="if"><input name="tag" placeholder="nova-vless" required><select name="protocol"><option>vless</option><option>xhttp</option><option>trojan</option><option>shadowsocks</option></select><input name="port" type="number" value="443"><button>Добавить</button></form><div id="i"></div></section>
<section><h2>Клиенты</h2><form id="cf"><input name="name" placeholder="client-01" required><select name="protocol"><option>vless</option><option>trojan</option><option>shadowsocks</option></select><button>Создать</button></form><div id="c"></div></section><pre id="o"></pre>
<script>
const $=x=>document.querySelector(x),out=x=>$('#o').textContent=typeof x==='string'?x:JSON.stringify(x,null,2);
async function j(u,o){return await(await fetch(u,o)).json()}
async function diag(){let x=await j('/api/diagnostics');$('#d').innerHTML=x.checks.map(a=>'<div class="'+(a.ok?'ok':'bad')+'">'+(a.ok?'✓':'✕')+' '+a.name+' <b>'+(a.ok?'OK':'ОШИБКА')+'</b></div>').join('')}
async function load(){let i=await j('/api/inbounds'),c=await j('/api/clients');$('#i').innerHTML=i.map(x=>'<div class="row"><b>'+x.tag+'</b> '+x.protocol+':'+x.port+'</div>').join('');$('#c').innerHTML=c.map(x=>'<div class="row"><b>'+x.name+'</b> '+x.protocol+' <button onclick="cfg(\''+x.id+'\')">Конфиг</button><button onclick="delc(\''+x.id+'\')">Удалить</button></div>').join('')}
async function cfg(id){out(await(await fetch('/api/clients/'+id+'/config')).text())}async function delc(id){await fetch('/api/clients/'+id,{method:'DELETE'});load()}
async function apply(){out(await j('/api/apply',{method:'POST'}))}$('#if').onsubmit=async e=>{e.preventDefault();out(await j('/api/inbounds',{method:'POST',body:new FormData(e.target)}));load()}
$('#cf').onsubmit=async e=>{e.preventDefault();out(await j('/api/clients',{method:'POST',body:new FormData(e.target)}));load()}
fetch('/health').then(r=>r.json()).then(x=>$('#v').textContent='v'+x.version);diag();load();
</script></section></main></body></html>
HTML

cat > "$APP/static/style.css" <<'CSS'
body{margin:0;background:#0b1020;color:#eef2ff;font:14px system-ui}main{max-width:1100px;margin:auto;padding:30px}section{background:#11182c;border:1px solid #26304a;border-radius:14px;padding:20px;margin:18px 0}button,input,select{padding:10px;border-radius:8px;border:1px solid #34415f;background:#0b1020;color:#fff;margin:4px}.grid{display:flex;gap:8px;flex-wrap:wrap}.ok{color:#45d49a;padding:8px;border-bottom:1px solid #202a42}.bad{color:#ff6b7a;padding:8px;border-bottom:1px solid #202a42}.row{padding:12px;border-bottom:1px solid #202a42}small{color:#45d49a}pre{white-space:pre-wrap}
CSS

python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"

cat > /etc/systemd/system/nova-ui.service <<EOF
[Unit]
Description=NOVA-UI Xray AmneziaWG Panel
After=network-online.target
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
systemctl enable --now nova-ui
echo
echo "NOVA-UI installed: http://SERVER-IP:$PORT"
echo "Check: systemctl status nova-ui --no-pager"
