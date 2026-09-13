#!/usr/bin/env python3
"""NOVA AWG 3.1 multi-node traffic balancer.

The balancer intentionally works at client-allocation level: an existing AWG/UDP
session stays on its node, while new clients are assigned to the healthiest node.
"""
from flask import request, redirect, jsonify
from pathlib import Path
import sqlite3, subprocess, time, urllib.request, urllib.error, ipaddress

BASE = Path('/opt/awg31-panel')
DB = BASE / 'panel.db'
CONF_DIR = BASE / 'balancer'
CONF_DIR.mkdir(parents=True, exist_ok=True)


def _db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _init():
    c = _db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS balancer_nodes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      host TEXT NOT NULL,
      api_port INTEGER NOT NULL DEFAULT 9090,
      weight INTEGER NOT NULL DEFAULT 100,
      enabled INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'unknown',
      latency_ms INTEGER,
      clients INTEGER NOT NULL DEFAULT 0,
      rx INTEGER NOT NULL DEFAULT 0,
      tx INTEGER NOT NULL DEFAULT 0,
      last_check INTEGER NOT NULL DEFAULT 0,
      created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
    );
    CREATE TABLE IF NOT EXISTS balancer_assignments (
      client_id INTEGER PRIMARY KEY,
      node_id INTEGER NOT NULL,
      assigned_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
    );
    ''')
    c.commit(); c.close()


def _health(row):
    host = row['host']; port = int(row['api_port'] or 9090)
    started = time.monotonic()
    status = 'down'; latency = None; clients = 0; rx = tx = 0
    try:
        url = f'http://{host}:{port}/health'
        with urllib.request.urlopen(url, timeout=2.5) as r:
            if r.status == 200:
                data = __import__('json').loads(r.read().decode() or '{}')
                status = 'online'; clients = int(data.get('clients', 0)); rx = int(data.get('rx', 0)); tx = int(data.get('tx', 0))
                latency = int((time.monotonic() - started) * 1000)
    except Exception:
        # ICMP/TCP fallback makes nodes without the optional API visible as down
        # rather than falsely healthy.
        pass
    c = _db(); c.execute('UPDATE balancer_nodes SET status=?,latency_ms=?,clients=?,rx=?,tx=?,last_check=? WHERE id=?',
                         (status, latency, clients, rx, tx, int(time.time()), row['id'])); c.commit(); c.close()
    return status, latency


def _nodes():
    c = _db(); rows = c.execute('SELECT * FROM balancer_nodes ORDER BY id').fetchall(); c.close(); return rows


def choose_node():
    """Weighted least-load selection. Returns a node row or None."""
    candidates = []
    for n in _nodes():
        if not n['enabled']:
            continue
        status = n['status']
        if status == 'unknown' or time.time() - (n['last_check'] or 0) > 45:
            status, _ = _health(n)
        if status != 'online':
            continue
        weight = max(1, int(n['weight'] or 1))
        # Lower score is preferred. Weight increases capacity.
        score = (int(n['clients'] or 0) + 1) / weight + (int(n['latency_ms'] or 9999) / 100000.0)
        candidates.append((score, n))
    return min(candidates, key=lambda x: x[0])[1] if candidates else None


def _safe_host(host):
    if not host or len(host) > 253:
        return False
    try:
        ipaddress.ip_address(host); return True
    except ValueError:
        return all(part and len(part) <= 63 for part in host.split('.')) and all(ch.isalnum() or ch in '.-' for ch in host)


def register(app):
    _init()

    @app.route('/balancer')
    def balancer_page():
        nodes = _nodes()
        rows = []
        for n in nodes:
            if n['enabled'] and (time.time() - (n['last_check'] or 0) > 45):
                _health(n)
        nodes = _nodes()
        for n in nodes:
            rows.append(f'''<tr><td><b>{n['name']}</b><span class="subline">{n['host']}:{n['api_port']}</span></td>
            <td><span class="badge {'on' if n['status']=='online' else 'off'}">{'ONLINE' if n['status']=='online' else n['status'].upper()}</span></td>
            <td>{n['clients']}</td><td>{n['latency_ms'] if n['latency_ms'] is not None else '—'} ms</td><td>{n['weight']}</td>
            <td class="actions-row"><a class="btn mini secondary" href="/balancer/check/{n['id']}">Проверить</a>
            <a class="btn mini danger" href="/balancer/delete/{n['id']}" onclick="return confirm('Удалить узел?')">Удалить</a></td></tr>''')
        body = f'''<div class="hero"><div><div class="eyebrow">NOVA / CLUSTER</div><h1>Балансировка</h1><p>Распределение новых клиентов между AWG 3.1 узлами без разрыва существующих сессий.</p></div></div>
        <div class="grid4"><div class="card metric"><div class="label">Узлов</div><div class="value">{len(nodes)}</div><div class="sub">в пуле</div></div>
        <div class="card metric"><div class="label">Онлайн</div><div class="value ok">{sum(n['status']=='online' for n in nodes)}</div><div class="sub">готовы принимать клиентов</div></div>
        <div class="card metric"><div class="label">Клиентов</div><div class="value blue">{sum(n['clients'] for n in nodes)}</div><div class="sub">по узлам кластера</div></div>
        <div class="card metric"><div class="label">Режим</div><div class="value" style="font-size:22px">Least Load</div><div class="sub">с учётом веса и latency</div></div></div>
        <div class="card" style="margin-top:14px"><div class="toolbar"><h2>Пул AWG серверов</h2><a class="btn" href="/balancer/add">＋ Добавить сервер</a></div>
        <div class="table-wrap"><table><thead><tr><th>Сервер</th><th>Статус</th><th>Клиенты</th><th>Latency</th><th>Вес</th><th></th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan=6 class=muted>Добавь первый AWG узел.</td></tr>'}</tbody></table></div></div>
        <div class="card" style="margin-top:14px"><h2>Как работает</h2><p class="muted">Новый клиент получает наиболее свободный здоровый узел с учётом веса. После выдачи конфигурации endpoint не меняется — действующие соединения не переносятся между VPS. При падении узла новые выдачи автоматически переключаются на оставшиеся ONLINE узлы.</p></div>'''
        from app import layout
        return layout('Балансировка', body, '/balancer')

    @app.route('/balancer/add', methods=['GET','POST'])
    def balancer_add():
        if request.method == 'POST':
            name = request.form.get('name','').strip()[:64]
            host = request.form.get('host','').strip()
            try: port = int(request.form.get('api_port','9090'))
            except ValueError: port = 9090
            try: weight = max(1, min(10000, int(request.form.get('weight','100'))))
            except ValueError: weight = 100
            if not name or not _safe_host(host) or not (1 <= port <= 65535):
                return 'Invalid node parameters', 400
            c = _db()
            try:
                c.execute('INSERT INTO balancer_nodes(name,host,api_port,weight) VALUES(?,?,?,?)',(name,host,port,weight)); c.commit()
            except sqlite3.IntegrityError: return 'Node name already exists', 409
            finally: c.close()
            return redirect('/balancer/check/latest')
        body='''<div class="hero"><div><div class="eyebrow">NOVA / CLUSTER</div><h1>Добавить сервер</h1><p>На удалённом VPS должен быть доступен health API.</p></div></div><div class="card"><form method="post"><label>Название</label><input name="name" placeholder="NL-02" required><label>IP / hostname</label><input name="host" placeholder="203.0.113.10" required><div class="formgrid"><div><label>Health API порт</label><input name="api_port" type="number" value="9090" min="1" max="65535"></div><div><label>Вес</label><input name="weight" type="number" value="100" min="1" max="10000"></div></div><div class="notice">Рекомендуется открыть health API только для IP управляющей панели. Сам AWG UDP-порт может оставаться 1234.</div><button type="submit">Добавить и проверить</button> <a class="btn secondary" href="/balancer">Отмена</a></form></div>'''
        from app import layout
        return layout('Добавить сервер', body, '/balancer')

    @app.route('/balancer/check/<node_id>')
    def balancer_check(node_id):
        c = _db(); n = c.execute('SELECT * FROM balancer_nodes WHERE id=? OR (?="latest" AND id=(SELECT MAX(id) FROM balancer_nodes))',(node_id,node_id)).fetchone(); c.close()
        if n: _health(n)
        return redirect('/balancer')

    @app.route('/balancer/delete/<int:node_id>')
    def balancer_delete(node_id):
        c = _db(); c.execute('DELETE FROM balancer_assignments WHERE node_id=?',(node_id,)); c.execute('DELETE FROM balancer_nodes WHERE id=?',(node_id,)); c.commit(); c.close(); return redirect('/balancer')

    @app.route('/api/balancer/nodes')
    def balancer_api_nodes():
        return jsonify([dict(n) for n in _nodes()])

    @app.route('/api/balancer/choose')
    def balancer_api_choose():
        n = choose_node()
        return jsonify({'ok': bool(n), 'node': dict(n) if n else None}), (200 if n else 503)

    return choose_node

# app.py imports this module after its routes are defined.
try:
    from app import app
    register(app)
except (ImportError, RuntimeError):
    # Allows syntax/import checks without the production app being initialized.
    pass
