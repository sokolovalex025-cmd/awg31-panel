#!/usr/bin/env python3
"""NOVA AWG Toolz daemon: localhost-only, token-protected AWG operations API."""
from __future__ import annotations
import json, os, secrets, shutil, subprocess, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST="127.0.0.1"; PORT=int(os.environ.get("AWG_TOOLZ_PORT","9090"))
TOKEN_FILE=Path(os.environ.get("AWG_TOOLZ_TOKEN","/etc/awg-toolz/token"))
CONF=Path("/etc/amnezia/amneziawg/awg0.conf")
BACKUP_DIR=Path("/etc/awg-toolz/backups")
BASE=Path("/opt/awg31-panel")
PARAMS={"Jc":"4","Jmin":"40","Jmax":"120","S1":"16","S2":"16","S3":"16","S4":"16","H1":"1","H2":"2","H3":"3","H4":"4","RandomTrailers":"on","DisableCookies":"on"}

def run(*args, timeout=15):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        return {"ok":p.returncode==0,"stdout":p.stdout.strip(),"stderr":p.stderr.strip(),"code":p.returncode}
    except Exception as e: return {"ok":False,"stdout":"","stderr":str(e),"code":-1}

def token():
    try:return TOKEN_FILE.read_text().strip()
    except Exception:return ""

def read_config():
    cfg={}
    try:
        for line in CONF.read_text(errors="replace").splitlines():
            if "=" in line:
                k,v=line.split("=",1); k=k.strip(); v=v.strip()
                if k in PARAMS or k=="ListenPort": cfg[k]=v
    except Exception: pass
    return cfg

def status():
    cfg=read_config()
    mism={k:{"expected":v,"actual":cfg.get(k)} for k,v in PARAMS.items() if cfg.get(k)!=v}
    return {"awg":run("awg","--version")["stdout"] or "unknown","interface":run("awg","show","awg0")["ok"],"config":cfg,"profile_ok":not mism,"mismatches":mism}

def backup():
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    if not CONF.exists(): return None
    name=time.strftime("awg0-%Y%m%d-%H%M%S.conf")
    dst=BACKUP_DIR/name; shutil.copy2(CONF,dst); os.chmod(dst,0o600)
    return str(dst)

def action(name):
    if name=="apply-profile":
        b=backup()
        if not b: return {"ok":False,"error":"awg0.conf not found"}
        r=run("python3",str(BASE/"nova_awg31_fix.py"),timeout=30)
        return {"ok":r["ok"],"action":name,"backup":b,"result":r,"status":status()}
    if name=="repair-nat":
        r=run("bash",str(BASE/"nova-network-fix.sh"),timeout=15)
        return {"ok":r["ok"],"action":name,"result":r}
    if name=="restart-awg":
        r=run("systemctl","restart","awg-quick@awg0.service",timeout=20)
        return {"ok":r["ok"],"action":name,"result":r,"status":status()}
    if name=="restart-panel":
        r=run("systemctl","restart","awgpanel.service",timeout=20)
        return {"ok":r["ok"],"action":name,"result":r}
    if name=="repair-all":
        b=backup()
        if not b: return {"ok":False,"error":"awg0.conf not found"}
        steps=[
            ("profile",run("python3",str(BASE/"nova_awg31_fix.py"),timeout=30)),
            ("nat",run("bash",str(BASE/"nova-network-fix.sh"),timeout=15)),
        ]
        ok=all(x[1]["ok"] for x in steps)
        if ok:
            rr=run("systemctl","restart","awg-quick@awg0.service",timeout=20)
            ok=rr["ok"]
            steps.append(("restart_awg",rr))
        return {"ok":ok,"action":name,"backup":b,"steps":steps,"status":status()}
    return {"ok":False,"error":"unknown action"}

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False,default=str).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def authorized(self):
        return secrets.compare_digest(self.headers.get("X-NOVA-Toolz-Token",""),token())
    def do_GET(self):
        if not self.authorized(): return self.send(401,{"ok":False,"error":"unauthorized"})
        p=urllib.parse.urlparse(self.path).path
        if p in ("/v1/status","/v1/profile/check"): return self.send(200,{"ok":True,"mode":"read-write-confirmed","status":status()})
        if p=="/v1/network/check":
            return self.send(200,{"ok":True,"forwarding":Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()=="1","route":run("ip","-4","route","show","default")["stdout"]})
        return self.send(404,{"ok":False,"error":"not found"})
    def do_POST(self):
        if not self.authorized(): return self.send(401,{"ok":False,"error":"unauthorized"})
        p=urllib.parse.urlparse(self.path).path
        if p!="/v1/action": return self.send(404,{"ok":False,"error":"not found"})
        if self.headers.get("X-NOVA-Confirm")!="APPLY": return self.send(428,{"ok":False,"error":"confirmation required"})
        try:
            n=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        except Exception:return self.send(400,{"ok":False,"error":"invalid json"})
        result=action(str(body.get("action","")))
        return self.send(200 if result.get("ok") else 500,result)

if __name__=="__main__":
    TOKEN_FILE.parent.mkdir(parents=True,exist_ok=True)
    if not token(): TOKEN_FILE.write_text(secrets.token_urlsafe(48)); os.chmod(TOKEN_FILE,0o600)
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
