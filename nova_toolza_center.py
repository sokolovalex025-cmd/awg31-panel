"""NOVA AWG Toolza Center — safe AWG 3.1 operations dashboard.

Read-only by default: inspects the loaded AWG version, listener, config profile and
offers a preview of the canonical NOVA Strong Mobile profile without changing
awg0.conf or restarting services.
"""
from __future__ import annotations
import re, subprocess
from flask import jsonify

PARAMS = {
    "Jc":"4","Jmin":"40","Jmax":"120",
    "S1":"16","S2":"16","S3":"16","S4":"16",
    "H1":"1","H2":"2","H3":"3","H4":"4",
    "RandomTrailers":"on","DisableCookies":"on",
}
SAFE_KEYS = tuple(PARAMS)

def _run(*args):
    try:
        p=subprocess.run(args,capture_output=True,text=True,timeout=3)
        return p.stdout.strip()
    except Exception:
        return ""

def _version():
    tools=_run("awg","--version")
    loaded=_run("bash","-lc","cat /sys/module/amneziawg/version 2>/dev/null")
    return {"tools":tools or "unknown","loaded_module":loaded or "unknown"}

def _listen_port():
    out=_run("bash","-lc","ss -lunH 2>/dev/null | awk '$5 ~ /:([0-9]+)$/ {print $5}'")
    ports=[]
    for line in out.splitlines():
        m=re.search(r":(\d+)$",line)
        if m: ports.append(int(m.group(1)))
    return sorted(set(ports))

def _config():
    path="/etc/amnezia/amneziawg/awg0.conf"
    try:
        data=open(path,encoding="utf-8",errors="replace").read().splitlines()
    except Exception:
        return {}
    result={}
    for line in data:
        if "=" not in line or line.lstrip().startswith("#"): continue
        k,v=line.split("=",1); k=k.strip(); v=v.strip()
        if k in SAFE_KEYS: result[k]=v
        elif k=="ListenPort": result[k]=v
    return result

def snapshot():
    cfg=_config()
    mismatches={k:{"expected":v,"actual":cfg.get(k)} for k,v in PARAMS.items() if cfg.get(k)!=v}
    return {
        "awg": _version(),
        "udp_ports": _listen_port(),
        "listen_port": cfg.get("ListenPort"),
        "profile": cfg,
        "expected_profile": PARAMS,
        "mismatches": mismatches,
        "profile_ok": not mismatches,
        "mode": "read-only",
    }

HTML = r'''<style>
.nova-tz{max-width:1180px;margin:24px auto;padding:0 18px;font-family:inherit}
.nova-tz-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.nova-tz-card{padding:17px;border:1px solid rgba(255,255,255,.08);border-radius:16px;background:rgba(12,20,31,.82)}
.nova-tz-card b{font-size:18px}.nova-tz-card small{display:block;color:#7d899b;margin-top:6px}
.nova-tz-panel{margin-top:14px;padding:18px;border:1px solid rgba(255,255,255,.08);border-radius:16px;background:rgba(12,20,31,.82)}
.nova-tz-ok{color:#55dfb9}.nova-tz-bad{color:#ff7186}.nova-tz-pre{white-space:pre-wrap;font:12px ui-monospace,monospace;color:#cbd5e1}
@media(max-width:800px){.nova-tz-grid{grid-template-columns:repeat(2,1fr)}}
</style><section class="nova-tz">
<h2>🛠️ NOVA AWG Toolza Center</h2>
<p style="color:#7d899b">AWG 3.1 • безопасная проверка • изменения конфигурации не выполняются</p>
<div class="nova-tz-grid">
<div class="nova-tz-card"><b id="tz-tools">—</b><small>awg-tools</small></div>
<div class="nova-tz-card"><b id="tz-kmod">—</b><small>загруженный kernel module</small></div>
<div class="nova-tz-card"><b id="tz-port">—</b><small>UDP listener</small></div>
<div class="nova-tz-card"><b id="tz-profile">—</b><small>NOVA Strong Mobile</small></div>
</div>
<div class="nova-tz-panel"><b>Профиль</b><pre class="nova-tz-pre" id="tz-profile-text">Загрузка…</pre></div>
<div class="nova-tz-panel"><b>Результат проверки</b><div id="tz-result">Проверяем…</div></div>
</section>
<script>
(async function(){
try{
 const r=await fetch('/api/nova/toolza-center',{cache:'no-store'}); const d=await r.json();
 document.getElementById('tz-tools').textContent=d.awg.tools;
 document.getElementById('tz-kmod').textContent=d.awg.loaded_module;
 document.getElementById('tz-port').textContent=d.listen_port||'—';
 document.getElementById('tz-profile').textContent=d.profile_ok?'OK':'CHECK';
 document.getElementById('tz-profile').className=d.profile_ok?'nova-tz-ok':'nova-tz-bad';
 document.getElementById('tz-profile-text').textContent=Object.entries(d.expected_profile).map(x=>x[0]+'='+x[1]).join('\n');
 const bad=Object.entries(d.mismatches||{}).map(x=>x[0]+': expected '+x[1].expected+', actual '+x[1].actual);
 document.getElementById('tz-result').innerHTML=d.profile_ok?'<span class="nova-tz-ok">✓ Canonical AWG 3.1 profile совпадает</span>':'<span class="nova-tz-bad">⚠ Несовпадения: '+bad.join(' · ')+'</span>';
}catch(e){document.getElementById('tz-result').textContent='Ошибка проверки: '+e}
})();
</script>'''

def apply(nova):
    app=nova.core.app
    @app.route("/awg-toolza")
    def awg_toolza():
        return HTML
    @app.route("/api/nova/toolza-center")
    def api_toolza():
        return jsonify(snapshot())
    return nova
