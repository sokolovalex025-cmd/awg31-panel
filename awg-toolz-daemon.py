#!/usr/bin/env python3
"""NOVA AWG Toolz daemon: localhost-only, token-protected AWG operations API."""
from __future__ import annotations
import json, os, secrets, subprocess, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST="127.0.0.1"; PORT=int(os.environ.get("AWG_TOOLZ_PORT","9090"))
TOKEN_FILE=Path(os.environ.get("AWG_TOOLZ_TOKEN","/etc/awg-toolz/token"))
BASE=Path("/opt/awg31-panel")
PARAMS={"Jc":"4","Jmin":"40","Jmax":"120","S1":"16","S2":"16","S3":"16","S4":"16","H1":"1","H2":"2","H3":"3","H4":"4","RandomTrailers":"on","DisableCookies":"on"}

def run(*args, timeout=5):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        return {"ok":p.returncode==0,"stdout":p.stdout.strip(),"stderr":p.stderr.strip(),"code":p.returncode}
    except Exception as e: return {"ok":False,"stdout":"","stderr":str(e),"code":-1}

def token():
    try:return TOKEN_FILE.read_text().strip()
    except Exception:return ""

def status():
    cfg={}
    try:
        for line in Path("/etc/amnezia/amneziawg/awg0.conf").read_text(errors="replace").splitlines():
            if "=" in line:
                k,v=line.split("=",1); k=k.strip(); v=v.strip()
                if k in PARAMS or k=="ListenPort": cfg[k]=v
    except Exception: pass
    mism={k:{"expected":v,"actual":cfg.get(k)} for k,v in PARAMS.items() if cfg.get(k)!=v}
    return {"awg":run("awg","--version")["stdout"] or "unknown","interface":run("awg","show","awg0")["ok"],"config":cfg,"profile_ok":not mism,"mismatches":mism}

def allowed_action(path):
    return path in ("/v1/status","/v1/profile/check","/v1/network/check")

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.headers.get("X-NOVA-Toolz-Token","")!=token(): return self.send(401,{"ok":False,"error":"unauthorized"})
        p=urllib.parse.urlparse(self.path).path
        if p=="/v1/status": return self.send(200,{"ok":True,"mode":"read-only","status":status()})
        if p=="/v1/profile/check": return self.send(200,{"ok":True,"profile":status()})
        if p=="/v1/network/check":
            return self.send(200,{"ok":True,"forwarding":Path("/proc/sys/net/ipv4/ip_forward").read_text().strip()=="1","route":run("ip","-4","route","show","default")["stdout"]})
        return self.send(404,{"ok":False,"error":"not found"})
    def do_POST(self):
        if self.headers.get("X-NOVA-Toolz-Token","")!=token(): return self.send(401,{"ok":False,"error":"unauthorized"})
        p=urllib.parse.urlparse(self.path).path
        # Mutating operations are deliberately disabled in v1; panel remains read-only.
        if p.startswith("/v1/"): return self.send(403,{"ok":False,"error":"mutating operations disabled in this release"})
        return self.send(404,{"ok":False,"error":"not found"})

if __name__=="__main__":
    TOKEN_FILE.parent.mkdir(parents=True,exist_ok=True)
    if not token(): TOKEN_FILE.write_text(secrets.token_urlsafe(48)); os.chmod(TOKEN_FILE,0o600)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
