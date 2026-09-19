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
.nc-head{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:4px 0 20px}
.nc-title h1{margin:5px 0 6px;font-size:38px;letter-spacing:-.055em}
.nc-title p{margin:0;color:#8997aa}
.nc-actions{display:flex;gap:8px;flex-wrap:wrap}
.nc-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}
.nc-stat{padding:17px 18px;border:1px solid rgba(255,255,255,.07);border-radius:15px;background:linear-gradient(145deg,rgba(20,29,42,.92),rgba(10,15,23,.94));box-shadow:0 16px 45px rgba(0,0,0,.20)}
.nc-stat span{display:block;color:#718096;font-size:9px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}
.nc-stat b{display:block;margin-top:9px;font-size:25px;letter-spacing:-.04em}
.nc-stat small{display:block;margin-top:4px;color:#657489}
.nc-create{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;margin-bottom:14px}
.nc-panel{padding:19px;border:1px solid rgba(255,255,255,.075);border-radius:17px;background:linear-gradient(145deg,rgba(18,26,38,.90),rgba(10,15,23,.93));box-shadow:0 20px 60px rgba(0,0,0,.24)}
.nc-panel h2{margin:0;font-size:16px}
.nc-muted{color:#718096;font-size:11px}
.nc-form{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end}
.nc-form label{margin:0 0 6px}
.nc-hint{padding:12px;border-radius:12px;background:rgba(72,112,255,.06);border:1px solid rgba(112,139,255,.16);color:#9aa8bb;font-size:11px;line-height:1.55}
.nc-search{width:min(310px,100%)}
.nc-table table{min-width:760px}
.nc-client{display:flex;align-items:center;gap:10px}
.nc-avatar{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:linear-gradient(145deg,#7489ff,#3ed1b8);color:#071018;font-weight:950}
.nc-name{font-weight:800}
.nc-ip{font-family:Consolas,monospace;color:#9eabc0;font-size:11px}
.nc-key{font-family:Consolas,monospace;color:#68778b;font-size:9px}
.nc-row-actions{display:flex;gap:5px;align-items:center;flex-wrap:wrap}
.nc-empty{text-align:center;padding:35px 15px;color:#6f7e92}
.nc-empty strong{display:block;color:#c8d1dc;margin-bottom:6px}
.nc-toast{padding:11px 13px;border-radius:11px;margin-bottom:13px;background:#0c251f;border:1px solid #1b5c4c;color:#76e5c6}
.nc-danger{background:#351722!important;color:#ff9bab!important;border:1px solid #683243!important}
@media(max-width:1050px){.nc-stats{grid-template-columns:repeat(2,1fr)}.nc-create{grid-template-columns:1fr}}
@media(max-width:600px){.nc-head{align-items:flex-start;flex-direction:column}.nc-title h1{font-size:31px}.nc-stats{grid-template-columns:1fr 1fr}.nc-form{grid-template-columns:1fr}.nc-search{width:100%}}
@media(max-width:430px){.nc-stats{grid-template-columns:1fr}}
</style>
"""


PAGE = CSS + r"""
<div class="nc-head">
  <div class="nc-title">
    <div class="eyebrow">CLIENT CENTER</div>
    <h1>Клиенты</h1>
    <p>Создание, выдача и управление профилями AmneziaWG 3.1.</p>
  </div>
  <div class="nc-actions">
    <a class="btn secondary" href="/active">🟢 Активные</a>
    <a class="btn" href="#new-client">＋ Новый клиент</a>
  </div>
</div>

{% if message %}
<div class="nc-toast">{{ message }}</div>
{% endif %}

<div class="nc-stats">
  <div class="nc-stat"><span>Всего</span><b>{{ total }}</b><small>профилей в панели</small></div>
  <div class="nc-stat"><span>Онлайн</span><b class="ok">{{ online }}</b><small>handshake ≤ 3 минут</small></div>
  <div class="nc-stat"><span>Свободные IP</span><b class="blue">{{ free }}</b><small>из диапазона 10.66.66.0/24</small></div>
  <div class="nc-stat"><span>Профиль</span><b>AWG 3.1</b><small>канонический NOVA</small></div>
</div>

<div class="nc-create">
  <section class="nc-panel" id="new-client">
    <div class="toolbar">
      <div><h2>Создать нового клиента</h2><div class="nc-muted">Ключи и адрес выдаются автоматически.</div></div>
      <span class="tag">SECURE</span>
    </div>
    <form class="nc-form" method="post" action="/clients/create">
      <div>
        <label>Название клиента</label>
        <input name="name" maxlength="64" autocomplete="off" placeholder="iPhone · Android · Windows · Laptop" required>
      </div>
      <button type="submit">Создать профиль</button>
    </form>
  </section>
  <section class="nc-panel">
    <h2>Что получит клиент</h2>
    <div class="nc-hint">
      После создания можно сразу скачать <b>.conf</b> или открыть <b>QR</b>.
      Профиль использует текущий endpoint, DNS, MTU и канонические параметры
      NOVA AWG 3.1. После применения AWG перезапускается с автоматическим
      откатом при ошибке.
    </div>
  </section>
</div>

<section class="nc-panel nc-table">
  <div class="toolbar">
    <div><h2>Все клиенты</h2><div class="nc-muted">Быстрый поиск по имени и адресу</div></div>
    <input id="clientSearch" class="nc-search" placeholder="🔎  Найти клиента..." oninput="filterClients()">
  </div>
  <div class="table-wrap">
    <table id="clientTable">
      <tr><th>Клиент</th><th>IP</th><th>Статус</th><th>Создан</th><th>Действия</th></tr>
      {% for r in rows %}
      {% set st = stats.get(r.id, {}) %}
      <tr class="client-row" data-search="{{ (r.name ~ ' ' ~ r.address)|lower }}">
        <td>
          <div class="nc-client">
            <div class="nc-avatar">{{ r.name[:1]|upper }}</div>
            <div><div class="nc-name">{{ r.name }}</div><div class="nc-key">{{ r.public_key[:20] }}…</div></div>
          </div>
        </td>
        <td><span class="nc-ip">{{ r.address }}</span></td>
        <td><span class="badge {{ 'on' if st.get('online') else 'off' }}">{{ 'ONLINE' if st.get('online') else 'OFFLINE' }}</span></td>
        <td>{{ created(r.created) }}</td>
        <td>
          <div class="nc-row-actions">
            <a class="btn mini" href="/clients/{{ r.id }}/conf">↓ CONF</a>
            <a class="btn secondary mini" href="/clients/{{ r.id }}/qr" target="_blank" rel="noopener">▣ QR</a>
            <form method="post" action="/clients/{{ r.id }}/delete" onsubmit="return confirm('Удалить клиента «{{ r.name|e }}»?')">
              <button type="submit" class="btn mini nc-danger">Удалить</button>
            </form>
          </div>
        </td>
      </tr>
      {% else %}
      <tr><td colspan="5"><div class="nc-empty"><strong>Клиентов пока нет</strong>Создайте первый профиль выше.</div></td></tr>
      {% endfor %}
    </table>
  </div>
</section>

<script>
function filterClients(){
  const q=(document.getElementById('clientSearch').value||'').trim().toLowerCase();
  document.querySelectorAll('.client-row').forEach(r=>{
    r.style.display=!q || r.dataset.search.includes(q) ? '' : 'none';
  });
}
</script>
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
        value = it.get(key, params.get(key))
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


def _clients_page():
    rows = core.rows()
    stats = {x["id"]: x for x in core.client_stats()}
    total = len(rows)
    online = sum(1 for x in stats.values() if x.get("online"))
    used = set()
    for row in rows:
        match = re.search(r"10\.66\.66\.(\d+)", row["address"] or "")
        if match:
            used.add(int(match.group(1)))
    free = max(0, 253 - len([x for x in used if 2 <= x <= 254]))
    body = render_template_string(
        PAGE,
        rows=rows,
        stats=stats,
        total=total,
        online=online,
        free=free,
        created=lambda ts: time.strftime("%d.%m.%Y", time.localtime(ts or 0)),
    )
    return core.layout("Клиенты", body, "/clients")


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
            "INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)",
            (name, address, priv, pub, psk, int(time.time())),
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
    app.view_functions["delete_client"] = _delete_client
    app.view_functions["conf"] = _conf
    app.view_functions["qr"] = _qr
    core.client_config = _client_config
    return nova
