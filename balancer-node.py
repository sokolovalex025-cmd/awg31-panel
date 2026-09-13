#!/usr/bin/env python3
"""NOVA AWG 3.1 worker-node API. Keep port 9090 reachable only from panel."""
from flask import Flask, jsonify, request
from pathlib import Path
import subprocess, time, os, hmac

app=Flask(__name__); PORT=int(os.getenv('BALANCER_NODE_PORT','9090')); CONF=Path('/etc/amnezia/amneziawg/awg0.conf')
if not CONF.exists(): CONF=Path('/etc/wireguard/awg0.conf')
TOKEN=os.getenv('BALANCER_TOKEN','')

def run(*args):
    try:return subprocess.run(args,text=True,capture_output=True,timeout=5)
    except Exception:return None

def authorized():
    supplied=request.headers.get('Authorization',''); return bool(TOKEN) and hmac.compare_digest(supplied,'Bearer '+TOKEN)

def metrics():
    r=run('awg','show','awg0','dump'); clients=rx=tx=0
    if r and r.returncode==0:
        lines=r.stdout.strip().splitlines(); clients=max(0,len(lines)-1)
        for line in lines[1:]:
            p=line.split('\t')
            if len(p)>=7:
                try:rx+=int(p[5])
                except ValueError:pass
                try:tx+=int(p[6])
                except ValueError:pass
    return clients,rx,tx

def server_public():
    r=run('awg','show','awg0','public-key'); return r.stdout.strip() if r else ''

def restart():
    r=run('systemctl','restart','awg-quick@awg0'); return bool(r and r.returncode==0)

@app.before_request
def auth():
    if request.path=='/health':return
    if not authorized():return jsonify({'ok':False,'error':'unauthorized'}),401

@app.get('/health')
def health():
    r=run('systemctl','is-active','--quiet','awg-quick@awg0')
    if not r or r.returncode!=0:return jsonify({'ok':False,'status':'down'}),503
    clients,rx,tx=metrics();return jsonify({'ok':True,'status':'online','clients':clients,'rx':rx,'tx':tx,'ts':int(time.time())})

@app.get('/info')
def info():return jsonify({'ok':True,'public_key':server_public(),'listen_port':1234})

@app.post('/client/add')
def client_add():
    d=request.get_json(silent=True) or {};pub=d.get('public_key','').strip();psk=d.get('psk','').strip();addr=d.get('address','').strip()
    if not pub or not psk or not addr:return jsonify({'ok':False,'error':'missing fields'}),400
    old=CONF.read_text(errors='replace') if CONF.exists() else ''
    if f'PublicKey = {pub}' in old:return jsonify({'ok':True,'already_exists':True})
    backup=CONF.with_name(CONF.name+'.bak-balancer-'+time.strftime('%Y%m%d-%H%M%S'))
    if CONF.exists():backup.write_text(old)
    CONF.parent.mkdir(parents=True,exist_ok=True);CONF.write_text(old.rstrip()+f'\n\n[Peer]\nPublicKey = {pub}\nPresharedKey = {psk}\nAllowedIPs = {addr}\n')
    if not restart():CONF.write_text(old);restart();return jsonify({'ok':False,'error':'awg restart failed'}),500
    return jsonify({'ok':True})

@app.post('/client/delete')
def client_delete():
    d=request.get_json(silent=True) or {};pub=d.get('public_key','').strip()
    if not pub:return jsonify({'ok':False,'error':'missing public_key'}),400
    old=CONF.read_text(errors='replace') if CONF.exists() else '';parts=old.split('[Peer]');head=parts[0];kept=[x for x in parts[1:] if f'PublicKey = {pub}' not in x];new=head+''.join('[Peer]'+x for x in kept)
    if new==old:return jsonify({'ok':True,'already_deleted':True})
    backup=CONF.with_name(CONF.name+'.bak-balancer-delete-'+time.strftime('%Y%m%d-%H%M%S'));backup.write_text(old);CONF.write_text(new)
    if not restart():CONF.write_text(old);restart();return jsonify({'ok':False,'error':'awg restart failed'}),500
    return jsonify({'ok':True})

if __name__=='__main__':app.run(host='0.0.0.0',port=PORT)
