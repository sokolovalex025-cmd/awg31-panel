#!/usr/bin/env python3
"""NOVA AWG 3.1 multi-node client allocator and health balancer."""
from flask import request, redirect, jsonify
from pathlib import Path
import sqlite3, time, urllib.request, ipaddress, json, os
BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'; CONF_DIR=BASE/'balancer'; CONF_DIR.mkdir(parents=True,exist_ok=True); TOKEN_FILE=Path('/etc/awg31-panel/balancer.env')
def _token():
    if TOKEN_FILE.exists():
        for line in TOKEN_FILE.read_text(errors='ignore').splitlines():
            if line.startswith('BALANCER_TOKEN='): return line.split('=',1)[1].strip()
    return os.getenv('BALANCER_TOKEN','')
def _db(): c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def _init():
    c=_db(); c.executescript('''CREATE TABLE IF NOT EXISTS balancer_nodes(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,host TEXT NOT NULL,api_port INTEGER NOT NULL DEFAULT 9090,weight INTEGER NOT NULL DEFAULT 100,enabled INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL DEFAULT 'unknown',latency_ms INTEGER,clients INTEGER NOT NULL DEFAULT 0,rx INTEGER NOT NULL DEFAULT 0,tx INTEGER NOT NULL DEFAULT 0,last_check INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));CREATE TABLE IF NOT EXISTS balancer_assignments(client_id INTEGER PRIMARY KEY,node_id INTEGER NOT NULL,assigned_at INTEGER NOT NULL DEFAULT (strftime('%s','now')));'''); c.commit(); c.close()
def _url(row,path): return f"http://{row['host']}:{int(row['api_port'] or 9090)}{path}"
def _request(row,path,method='GET',payload=None):
    headers={'Authorization':'Bearer '+_token(),'Content-Type':'application/json'}; data=json.dumps(payload).encode() if payload is not None else None; req=urllib.request.Request(_url(row,path),data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=3.5) as r:return json.loads(r.read().decode() or '{}')
    except Exception:return None
def _health(row):
    started=time.monotonic(); data=_request(row,'/health'); status='online' if data and data.get('ok') else 'down'; latency=int((time.monotonic()-started)*1000) if status=='online' else None; clients=int(data.get('clients',0)) if data else 0; rx=int(data.get('rx',0)) if data else 0; tx=int(data.get('tx',0)) if data else 0
    c=_db();c.execute('UPDATE balancer_nodes SET status=?,latency_ms=?,clients=?,rx=?,tx=?,last_check=? WHERE id=?',(status,latency,clients,rx,tx,int(time.time()),row['id']));c.commit();c.close();return status,latency
def _nodes(): c=_db();r=c.execute('SELECT * FROM balancer_nodes ORDER BY id').fetchall();c.close();return r
def node_by_id(node_id): c=_db();r=c.execute('SELECT * FROM balancer_nodes WHERE id=?',(node_id,)).fetchone();c.close();return r
def node_for_client(client_id):
    c=_db();r=c.execute('SELECT node_id FROM balancer_assignments WHERE client_id=?',(client_id,)).fetchone();c.close();return node_by_id(r['node_id']) if r else None
def node_info(row): return _request(row,'/info') or {}
def node_add_client(row,pub,psk,addr):
    d=_request(row,'/client/add','POST',{'public_key':pub,'psk':psk,'address':addr});return bool(d and d.get('ok'))
def node_delete_client(row,pub):
    d=_request(row,'/client/delete','POST',{'public_key':pub});return bool(d and d.get('ok'))
def choose_node():
    candidates=[]
    for n in _nodes():
        if not n['enabled']:continue
        if n['status']=='unknown' or time.time()-(n['last_check'] or 0)>45:_health(n)
        n=node_by_id(n['id'])
        if not n or n['status']!='online':continue
        weight=max(1,int(n['weight'] or 1));score=(int(n['clients'] or 0)+1)/weight+(int(n['latency_ms'] or 9999)/100000.0);candidates.append((score,n))
    return min(candidates,key=lambda x:x[0])[1] if candidates else None
def _safe_host(host):
    if not host or len(host)>253:return False
    try:ipaddress.ip_address(host);return True
    except ValueError:return all(part and len(part)<=63 for part in host.split('.')) and all(ch.isalnum() or ch in '.-' for ch in host)
def register(app):
    _init()
    @app.route('/balancer')
    def balancer_page():
        for n in _nodes():
            if n['enabled'] and time.time()-(n['last_check'] or 0)>45:_health(n)
        nodes=_nodes();rows=[]
        for n in nodes:rows.append(f'''<tr><td><b>{n['name']}</b><span class="subline">{n['host']}:{n['api_port']}</span></td><td><span class="badge {'on' if n['status']=='online' else 'off'}">{'ONLINE' if n['status']=='online' else n['status'].upper()}</span></td><td>{n['clients']}</td><td>{n['latency_ms'] if n['latency_ms'] is not None else '—'} ms</td><td>{n['weight']}</td><td class="actions-row"><a class="btn mini secondary" href="/balancer/check/{n['id']}">Проверить</a> <a class="btn mini danger" href="/balancer/delete/{n['id']}" onclick="return confirm('Удалить узел?')">Удалить</a></td></tr>''')
        body=f'''<div class="hero"><div><div class="eyebrow">NOVA / CLUSTER</div><h1>Балансировка</h1><p>Распределение новых клиентов между AWG 3.1 узлами без разрыва существующих сессий.</p></div></div><div class="grid4"><div class="card metric"><div class="label">Узлов</div><div class="value">{len(nodes)}</div><div class="sub">в пуле</div></div><div class="card metric"><div class="label">Онлайн</div><div class="value ok">{sum(n['status']=='online' for n in nodes)}</div><div class="sub">готовы принимать клиентов</div></div><div class="card metric"><div class="label">Клиентов</div><div class="value blue">{sum(n['clients'] for n in nodes)}</div><div class="sub">по узлам кластера</div></div><div class="card metric"><div class="label">Режим</div><div class="value" style="font-size:22px">Least Load</div><div class="sub">вес + latency</div></div></div><div class="card" style="margin-top:14px"><div class="toolbar"><h2>Пул AWG серверов</h2><a class="btn" href="/balancer/add">＋ Добавить сервер</a></div><div class="table-wrap"><table><thead><tr><th>Сервер</th><th>Статус</th><th>Клиенты</th><th>Latency</th><th>Вес</th><th></th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=6 class=muted>Добавь первый AWG узел.</td></tr>'}</tbody></table></div></div><div class="card" style="margin-top:14px"><h2>Принцип работы</h2><p class="muted">Балансируется выдача новых профилей. Уже подключённый клиент остаётся на своём VPS. Если узел недоступен, новые профили автоматически уходят на другой ONLINE узел.</p></div>'''
        from app import layout;return layout('Балансировка',body,'/balancer')
    @app.route('/balancer/add',methods=['GET','POST'])
    def balancer_add():
        if request.method=='POST':
            name=request.form.get('name','').strip()[:64];host=request.form.get('host','').strip()
            try:port=int(request.form.get('api_port','9090'));weight=max(1,min(10000,int(request.form.get('weight','100'))))
            except ValueError:return 'Invalid parameters',400
            if not name or not _safe_host(host) or not 1<=port<=65535:return 'Invalid node parameters',400
            c=_db()
            try:c.execute('INSERT INTO balancer_nodes(name,host,api_port,weight) VALUES(?,?,?,?)',(name,host,port,weight));c.commit()
            except sqlite3.IntegrityError:return 'Node name already exists',409
            finally:c.close()
            return redirect('/balancer/check/latest')
        body='''<div class="hero"><div><div class="eyebrow">NOVA / CLUSTER</div><h1>Добавить сервер</h1><p>На VPS должен работать NOVA node agent.</p></div></div><div class="card"><form method="post"><label>Название</label><input name="name" placeholder="NL-02" required><label>IP / hostname</label><input name="host" required><div class="formgrid"><div><label>Health API порт</label><input name="api_port" type="number" value="9090"></div><div><label>Вес</label><input name="weight" type="number" value="100" min="1" max="10000"></div></div><div class="notice">Health API использует общий секрет из /etc/awg31-panel/balancer.env. Ограничь порт 9090 firewall-правилом по IP панели.</div><button>Добавить и проверить</button> <a class="btn secondary" href="/balancer">Отмена</a></form></div>''';from app import layout;return layout('Добавить сервер',body,'/balancer')
    @app.route('/balancer/check/<node_id>')
    def balancer_check(node_id):
        c=_db();n=c.execute('SELECT * FROM balancer_nodes WHERE id=? OR (?="latest" AND id=(SELECT MAX(id) FROM balancer_nodes))',(node_id,node_id)).fetchone();c.close()
        if n:_health(n)
        return redirect('/balancer')
    @app.route('/balancer/delete/<int:node_id>')
    def balancer_delete(node_id):
        c=_db();c.execute('DELETE FROM balancer_assignments WHERE node_id=?',(node_id,));c.execute('DELETE FROM balancer_nodes WHERE id=?',(node_id,));c.commit();c.close();return redirect('/balancer')
    @app.route('/api/balancer/nodes')
    def balancer_api_nodes():return jsonify([dict(n) for n in _nodes()])
    @app.route('/api/balancer/choose')
    def balancer_api_choose():
        n=choose_node();return jsonify({'ok':bool(n),'node':dict(n) if n else None}),(200 if n else 503)
    return choose_node
try:
    from app import app;register(app)
except (ImportError,RuntimeError):pass
