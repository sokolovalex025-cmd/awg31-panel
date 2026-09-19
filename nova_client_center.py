#!/usr/bin/env python3
"""NOVA 12 Client Center.

Polishes the client-management screen and makes generated client profiles
follow the canonical NOVA AWG 3.1 profile.  The module only replaces existing
Flask view functions; it does not add a second set of client routes.
"""
from pathlib import Path
import io
import re
import sqlite3
import time
import subprocess

from flask import render_template_string, request, redirect, Response, send_file
from werkzeug.utils import secure_filename

import app as core


CSS = r"""
<style>
.nc-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:4px 0 18px}.nc-title h1{margin:5px 0;font-size:38px;letter-spacing:-.055em}.nc-title p{margin:0;color:#8190a5;font-size:13px}.nc-actions{display:flex;gap:8px;flex-wrap:wrap}
.nc-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:13px}.nc-stat{padding:16px 17px;border:1px solid #e4eaf1;border-radius:16px;background:#fff;box-shadow:0 9px 28px rgba(30,50,80,.055)}.nc-stat span{display:block;color:#718096;font-size:9px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.nc-stat b{display:block;margin-top:8px;font-size:24px}.nc-stat small{display:block;margin-top:4px;color:#7b899d;font-size:10px}
.nc-create{display:grid;grid-template-columns:1.1fr .9fr;gap:13px;margin-bottom:13px}.nc-panel{padding:18px;border:1px solid #e4eaf1;border-radius:18px;background:#fff;box-shadow:0 9px 28px rgba(30,50,80,.05)}.nc-panel h2{margin:0;font-size:16px}.nc-muted{color:#718096;font-size:11px}.nc-form{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end;margin-top:13px}.nc-form label{margin:0 0 6px}.nc-hint{margin-top:13px;padding:12px;border-radius:12px;background:#f2f8ff;border:1px solid #dceaf8;color:#66788e;font-size:11px;line-height:1.6}
.nc-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px}.nc-search{width:min(310px,100%)}.nc-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:11px;margin-top:14px}.nc-client-card{border:1px solid #e4eaf1;border-radius:16px;background:#fff;padding:15px;box-shadow:0 7px 22px rgba(30,50,80,.04);transition:.18s}.nc-client-card:hover{transform:translateY(-1px);box-shadow:0 11px 28px rgba(30,50,80,.07)}
.nc-client-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.nc-client{display:flex;align-items:center;gap:10px;min-width:0}.nc-avatar{width:38px;height:38px;flex:0 0 38px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,#10b981,#3b82f6);color:#fff;font-weight:900}.nc-name{font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nc-ip{font:11px Consolas,monospace;color:#718096}.nc-key{font:9px Consolas,monospace;color:#93a0b2;margin-top:2px}.nc-meta{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:13px}.nc-meta-item{padding:9px;border-radius:11px;background:#f8fafc;border:1px solid #edf0f4}.nc-meta-item span{display:block;color:#8592a5;font-size:9px;font-weight:750;text-transform:uppercase}.nc-meta-item b{display:block;margin-top:4px;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.nc-card-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:12px;padding-top:11px;border-top:1px solid #edf0f4}.nc-empty{text-align:center;padding:38px 15px;color:#718096}.nc-empty strong{display:block;color:#344154;margin-bottom:5px}.nc-toast{padding:11px 13px;border-radius:11px;margin-bottom:13px;background:#effcf7;border:1px solid #d5f3e7;color:#0f8f69}.nc-danger{background:#fff4f6!important;color:#a63b4d!important;border:1px solid #f0d5db!important}.nc-warning{background:#fff9ed!important;color:#9a6a12!important;border:1px solid #f0dfb4!important}
@media(max-width:1050px){.nc-stats{grid-template-columns:repeat(2,1fr)}.nc-create,.nc-grid{grid-template-columns:1fr}}@media(max-width:650px){.nc-head{align-items:flex-start;flex-direction:column}.nc-title h1{font-size:31px}.nc-stats{grid-template-columns:1fr 1fr}.nc-form{grid-template-columns:1fr}.nc-search{width:100%}.nc-meta{grid-template-columns:1fr 1fr}}@media(max-width:430px){.nc-stats,.nc-meta{grid-template-columns:1fr}}
</style>
"""

PAGE = CSS + r"""
<div class="nc-head"><div class="nc-title"><div class="eyebrow">NOVA CLIENT CENTER</div><h1>Клиенты</h1><p>Создание, выдача и управление профилями AmneziaWG 3.1.</p></div><div class="nc-actions"><a class="btn secondary" href="/active">🟢 Активные</a><a class="btn" href="#new-client">＋ Новый клиент</a></div></div>
{% if message %}<div class="nc-toast">{{ message }}</div>{% endif %}
<div class="nc-stats"><div class="nc-stat"><span>Всего</span><b>{{ total }}</b><small>профилей в панели</small></div><div class="nc-stat"><span>Онлайн</span><b class="ok">{{ online }}</b><small>handshake ≤ 3 минут</small></div><div class="nc-stat"><span>Свободные IP</span><b class="blue">{{ free }}</b><small>из 10.66.66.0/24</small></div><div class="nc-stat"><span>Трафик RX</span><b>{{ total_rx }}</b><small>TX {{ total_tx }}</small></div></div>
<div class="nc-create"><section class="nc-panel" id="new-client"><div class="toolbar"><div><h2>Создать нового клиента</h2><div class="nc-muted">Имя, ключи и IP выдаются автоматически.</div></div><span class="tag">AWG 3.1</span></div><form class="nc-form" method="post" action="/clients/create"><div><label>Название клиента</label><input name="name" maxlength="64" autocomplete="off" placeholder="iPhone · Android · Windows · Laptop" required></div><button type="submit">Создать профиль</button></form></section><section class="nc-panel"><h2>Быстрая выдача</h2><div class="nc-hint">После создания доступны <b>.conf</b> и <b>QR</b>. В карточке видны handshake, RX/TX и состояние профиля. Отключение не удаляет клиента.</div></section></div>
<section class="nc-panel"><div class="nc-toolbar"><div><h2>Все клиенты</h2><div class="nc-muted">Поиск по имени, IP и ключу</div></div><input id="clientSearch" class="nc-search" placeholder="🔎  Найти клиента..." oninput="filterClients()"></div><div class="nc-grid">
{% for r in rows %}{% set st=stats.get(r.id,{}) %}<article class="nc-client-card client-row" data-search="{{ (r.name ~ ' ' ~ r.address ~ ' ' ~ r.public_key)|lower }}"><div class="nc-client-top"><div class="nc-client"><div class="nc-avatar">{{ r.name[:1]|upper }}</div><div><div class="nc-name">{{ r.name }}</div><div class="nc-ip">{{ r.address }}</div><div class="nc-key">{{ r.public_key[:24] }}…</div></div></div><span class="badge {{ 'on' if st.get('online') and st.get('enabled',True) else 'off' }}">{{ 'ONLINE' if st.get('online') and st.get('enabled',True) else ('DISABLED' if not st.get('enabled',True) else 'OFFLINE') }}</span></div><div class="nc-meta"><div class="nc-meta-item"><span>Handshake</span><b>{{ ago(st.get('handshake')) }}</b></div><div class="nc-meta-item"><span>RX</span><b>{{ fmt_bytes(st.get('rx')) }}</b></div><div class="nc-meta-item"><span>TX</span><b>{{ fmt_bytes(st.get('tx')) }}</b></div></div><div class="nc-card-actions"><a class="btn mini" href="/clients/{{ r.id }}/conf">↓ CONF</a><a class="btn secondary mini" href="/clients/{{ r.id }}/qr" target="_blank" rel="noopener">▣ QR</a><form method="post" action="/clients/{{ r.id }}/toggle" onsubmit="return confirm('{{ 'Включить' if not st.get('enabled',True) else 'Отключить' }} клиента «{{ r.name|e }}»?')"><button type="submit" class="btn mini {{ 'nc-warning' if st.get('enabled',True) else '' }}">{{ '▶ Включить' if not st.get('enabled',True) else '⏸ Отключить' }}</button></form><form method="post" action="/clients/{{ r.id }}/delete" onsubmit="return confirm('Удалить клиента «{{ r.name|e }}»?')"><button type="submit" class="btn mini nc-danger">Удалить</button></form></div></article>{% else %}<div class="nc-empty" style="grid-column:1/-1"><strong>Клиентов пока нет</strong>Создайте первый профиль выше.</div>{% endfor %}</div></section>
<script>function filterClients(){const q=(document.getElementById('clientSearch').value||'').trim().toLowerCase();document.querySelectorAll('.client-row').forEach(r=>r.style.display=!q||r.dataset.search.includes(q)?'':'none')}</script>
"""
def _canonical_params():
    try:
        import nova_awg31_fix
        return dict(nova_awg31_fix.PARAMS)
    except Exception:
        return {
            "Jc":"4","Jmin":"40","Jmax":"120",
            "S1":"16","S2":"16","S3":"16","S4":"16",
            "H1":"1","H2":"2","H3":"3","H4":"4",
        }


def _run(*args, input_text=None):
    try:
        return subprocess.run(args, text=True, input=input_text, capture_output=True, timeout=30)
    except Exception as exc:
        return subprocess.CompletedProcess(args, 1, "", str(exc))


def _client_config(row):
    it = core.cfg()
    ep = core.setting("endpoint", "") or ((_run("hostname", "-I").stdout.split() or ["SERVER_IP"])[0])
    params = _canonical_params()
    lines = [
        "[Interface]",
        f"PrivateKey = {row['private_key']}",
        f"Address = {row['address']}",
        f"DNS = {core.setting('dns', '10.66.66.1')}",
        f"MTU = {it.get('MTU', '1280')}",
    ]
    for key in (
        "Jc","Jmin","Jmax","S1","S2","S3","S4","H1","H2","H3","H4",
        "ContentPaddingAddition","RekeyAfterTime","RekeyTimeout",
        "RejectAfterTime","KeepaliveTimeout","MaxHandshakeAttempts",
        "RandomTrailers","DisableCookies",
    ):
        value = params.get(key)
        if value is None:
            value = it.get(key)
        if value is not None and str(value) != "":
            lines.append(f"{key} = {value}")
    hp = it.get("HeaderProtectionKey")
    if hp:
        lines.append(f"HeaderProtectionKey = {hp}")
    lines += [
        "",
        "[Peer]",
        f"PublicKey = {_run('awg','show','awg0','public-key').stdout.strip()}",
        f"PresharedKey = {row['psk']}",
        "AllowedIPs = 0.0.0.0/0",
        f"Endpoint = {ep}:{it.get('ListenPort', '1234')}",
        "PersistentKeepalive = 25",
    ]
    return "\n".join(lines) + "\n"


def _fmt_bytes(n):
    n=float(n or 0)
    for u in ("B","KB","MB","GB","TB"):
        if n < 1024: return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def _ago(ts):
    if not ts: return "Нет handshake"
    sec=max(0,int(time.time())-int(ts))
    if sec < 60: return f"{sec} сек. назад"
    if sec < 3600: return f"{sec//60} мин. назад"
    if sec < 86400: return f"{sec//3600} ч. назад"
    return f"{sec//86400} дн. назад"


def _ensure_enabled_column():
    con=core.db()
    try:
        cols={r["name"] for r in con.execute("PRAGMA table_info(clients)").fetchall()}
        if "enabled" not in cols:
            con.execute("ALTER TABLE clients ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
            con.commit()
    finally: con.close()


def _client_peer(row):
    return "\\n\\n[Peer]\\nPublicKey = "+row["public_key"]+"\\nPresharedKey = "+row["psk"]+"\\nAllowedIPs = "+row["address"]+"\\n"


def _set_client_enabled(cid):
    _ensure_enabled_column()
    con=core.db(); row=con.execute("SELECT * FROM clients WHERE id=?",(cid,)).fetchone(); con.close()
    if not row: return Response("Клиент не найден.",status=404,mimetype="text/plain")
    target=not bool(row["enabled"]); conf=core.CONF; old=conf.read_text(errors="replace") if conf.exists() else ""
    if conf.exists(): conf.with_name("awg0.conf.bak-toggle-"+time.strftime("%Y%m%d-%H%M%S")).write_text(old)
    if target:
        if "PublicKey = "+row["public_key"] not in old: conf.write_text(old.rstrip()+_client_peer(row))
    else:
        blocks=old.split("[Peer]"); head=blocks[0]; kept=[b for b in blocks[1:] if "PublicKey = "+row["public_key"] not in b]; conf.write_text(head+"".join("[Peer]"+b for b in kept))
    result=_run("systemctl","restart","awg-quick@awg0")
    if result.returncode:
        if conf.exists(): conf.write_text(old)
        _run("systemctl","restart","awg-quick@awg0")
        return Response("Изменение не применилось. Конфигурация восстановлена.",status=500,mimetype="text/plain")
    con=core.db()
    try:
        con.execute("UPDATE clients SET enabled=? WHERE id=?",(1 if target else 0,cid)); con.commit()
    finally: con.close()
    return redirect("/clients")


def _clients_page():
    _ensure_enabled_column()
    rows=core.rows()
    raw={x["id"]:x for x in core.client_stats()}
    stats={}
    for row in rows:
        x=dict(raw.get(row["id"],{})); x["enabled"]=bool(row["enabled"]) if "enabled" in row.keys() else True; stats[row["id"]]=x
    used=set()
    for row in rows:
        m=re.search(r"10\.66\.66\.(\d+)",row["address"] or "")
        if m: used.add(int(m.group(1)))
    free=max(0,253-len([x for x in used if 2<=x<=254]))
    total_rx=sum(int(x.get("rx") or 0) for x in stats.values()); total_tx=sum(int(x.get("tx") or 0) for x in stats.values())
    body=render_template_string(PAGE,rows=rows,stats=stats,total=len(rows),online=sum(1 for x in stats.values() if x.get("online") and x.get("enabled",True)),free=free,total_rx=_fmt_bytes(total_rx),total_tx=_fmt_bytes(total_tx),ago=_ago,fmt_bytes=_fmt_bytes,message=request.args.get("message",""))
    return core.layout("Клиенты",body,"/clients")


def _create_client():
    name = request.form.get("name", "").strip()
    if not name:
        return Response("Название клиента обязательно.", status=400, mimetype="text/plain")
    if len(name) > 64:
        return Response("Название клиента слишком длинное.", status=400, mimetype="text/plain")

    con = core.db()
    try:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM clients WHERE lower(name)=lower(?)", (name,)).fetchone():
            con.rollback()
            return Response(
                "<script>alert('Клиент с таким именем уже существует.');location='/clients#new-client'</script>",
                status=409,
                mimetype="text/html",
            )
        used = {
            int(m.group(1))
            for row in con.execute("SELECT address FROM clients")
            for m in [re.search(r"10\.66\.66\.(\d+)", row["address"] or "")]
            if m
        }
        address = next((f"10.66.66.{n}/32" for n in range(2, 255) if n not in used), None)
        if not address:
            con.rollback()
            return Response("Свободные адреса закончились.", status=409, mimetype="text/plain")

        priv = _run("awg", "genkey").stdout.strip()
        pub = _run("awg", "pubkey", input_text=priv + "\n").stdout.strip()
        psk = _run("awg", "genpsk").stdout.strip()
        if not priv or not pub or not psk:
            con.rollback()
            return Response("Не удалось сгенерировать ключи AWG.", status=500, mimetype="text/plain")

        con.execute(
            "INSERT INTO clients(name,address,private_key,public_key,psk,created,enabled) VALUES(?,?,?,?,?,?,?)",
            (name, address, priv, pub, psk, int(time.time()), 1),
        )
        con.commit()
    finally:
        con.close()

    conf = core.CONF
    old = conf.read_text(errors="replace") if conf.exists() else ""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = conf.with_name(f"awg0.conf.bak-client-{stamp}") if conf.exists() else None
    if conf.exists():
        backup.write_text(old)
    peer = f"\n\n[Peer]\nPublicKey = {pub}\nPresharedKey = {psk}\nAllowedIPs = {address}\n"
    conf.write_text(old.rstrip() + peer)

    result = _run("systemctl", "restart", "awg-quick@awg0")
    if result.returncode:
        if conf.exists():
            conf.write_text(old)
        _run("systemctl", "restart", "awg-quick@awg0")
        con = core.db()
        try:
            con.execute("DELETE FROM clients WHERE public_key=?", (pub,))
            con.commit()
        finally:
            con.close()
        return Response(
            "AWG не принял новый профиль. Конфигурация восстановлена автоматически.",
            status=500,
            mimetype="text/plain",
        )
    return redirect("/clients")


def _delete_client(cid):
    con = core.db()
    row = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    con.close()
    if not row:
        return Response("Клиент не найден.", status=404, mimetype="text/plain")

    conf = core.CONF
    old = conf.read_text(errors="replace") if conf.exists() else ""
    if conf.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        conf.with_name(f"awg0.conf.bak-delete-{stamp}").write_text(old)
        blocks = old.split("[Peer]")
        head = blocks[0]
        kept = [block for block in blocks[1:] if f"PublicKey = {row['public_key']}" not in block]
        conf.write_text(head + "".join("[Peer]" + block for block in kept))
        result = _run("systemctl", "restart", "awg-quick@awg0")
        if result.returncode:
            conf.write_text(old)
            _run("systemctl", "restart", "awg-quick@awg0")
            return Response("Удаление не применилось. Конфигурация восстановлена.", status=500, mimetype="text/plain")

    con = core.db()
    try:
        con.execute("DELETE FROM clients WHERE id=?", (cid,))
        con.commit()
    finally:
        con.close()
    return redirect("/clients")


def _conf(cid):
    con = core.db()
    row = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    con.close()
    if not row:
        return Response("Клиент не найден.", status=404, mimetype="text/plain")
    safe = secure_filename(row["name"]) or f"client-{cid}"
    return Response(
        _client_config(row),
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{safe}.conf"'},
    )


def _qr(cid):
    con = core.db()
    row = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    con.close()
    if not row:
        return Response("Клиент не найден.", status=404, mimetype="text/plain")
    try:
        import qrcode
        image = io.BytesIO()
        qrcode.make(_client_config(row)).save(image, "PNG")
        image.seek(0)
        return send_file(image, mimetype="image/png")
    except Exception as exc:
        return Response(f"QR generation failed: {exc}", status=500, mimetype="text/plain")


def apply(nova):
    """Install the polished client-center view functions."""
    app = core.app
    app.view_functions["clients_page"] = _clients_page
    app.view_functions["create_client"] = _create_client
    _ensure_enabled_column()
    app.view_functions["delete_client"] = _delete_client
    app.add_url_rule("/clients/<int:cid>/toggle", "nova_toggle_client", _set_client_enabled, methods=["POST"])
    app.view_functions["conf"] = _conf
    app.view_functions["qr"] = _qr
    core.client_config = _client_config
    return nova
