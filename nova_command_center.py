"""NOVA Command Center dashboard enhancement.

Presentation-only: adds a compact operations strip to the existing dashboard
and uses already available panel endpoints for live health status.
"""

CSS = r'''<style id="nova-command-center-css">
.nova-command-center{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:stretch;margin:0 0 16px}
.nova-ops-card{display:flex;align-items:center;gap:18px;padding:15px 17px;border:1px solid rgba(255,255,255,.075);border-radius:16px;background:linear-gradient(135deg,rgba(18,27,41,.92),rgba(8,14,22,.94));box-shadow:0 18px 55px rgba(0,0,0,.24)}
.nova-health{display:flex;align-items:center;gap:10px;min-width:145px}.nova-health-dot{width:10px;height:10px;border-radius:50%;background:#43d9c0;box-shadow:0 0 15px rgba(67,217,192,.65)}.nova-health-dot.bad{background:#ff7186;box-shadow:0 0 15px rgba(255,113,134,.55)}
.nova-health b{display:block;font-size:12px}.nova-health small{display:block;color:#718095;font-size:10px;margin-top:3px}
.nova-score{margin-left:auto;text-align:right}.nova-score b{font-size:22px;letter-spacing:-.04em}.nova-score small{display:block;color:#718095;font-size:9px;text-transform:uppercase;letter-spacing:.1em}
.nova-quick{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.nova-quick a{min-width:100px;padding:11px 12px;border:1px solid rgba(255,255,255,.07);border-radius:13px;background:rgba(255,255,255,.025);text-decoration:none;transition:.15s ease}.nova-quick a:hover{transform:translateY(-2px);border-color:rgba(123,140,255,.32);background:rgba(123,140,255,.055)}.nova-quick strong{display:block;font-size:11px}.nova-quick span{display:block;color:#6f7d90;font-size:9px;margin-top:4px}
.nova-cc-refresh{font:inherit!important;padding:8px 10px!important;min-height:34px!important;border-radius:9px!important;box-shadow:none!important}
@media(max-width:1050px){.nova-command-center{grid-template-columns:1fr}.nova-quick{grid-template-columns:repeat(4,1fr)}}
@media(max-width:650px){.nova-ops-card{gap:11px;padding:13px}.nova-health{min-width:0}.nova-score{display:none}.nova-quick{grid-template-columns:repeat(2,1fr)}.nova-quick a{min-width:0}.nova-command-center{margin-bottom:13px}}
</style>'''

JS = r'''<script id="nova-command-center-js">
(function(){
'use strict';
function mount(){
 if(location.pathname!=='/' || document.querySelector('.nova-command-center'))return;
 var wrap=document.querySelector('.wrap'); if(!wrap)return;
 var hero=wrap.querySelector('.hero'); if(!hero)return;
 var root=document.createElement('section');root.className='nova-command-center';
 root.innerHTML='<div class="nova-ops-card"><div class="nova-health"><i class="nova-health-dot"></i><div><b id="nova-cc-state">Проверяем систему…</b><small id="nova-cc-detail">NOVA Command Center</small></div></div><div class="nova-score"><b id="nova-cc-score">—</b><small>Health Score</small></div><button type="button" class="btn secondary nova-cc-refresh" id="nova-cc-refresh">↻</button></div><div class="nova-quick"><a href="/clients"><strong>👥 Клиенты</strong><span>Управление VPN</span></a><a href="/traffic"><strong>📈 Traffic</strong><span>Живой трафик</span></a><a href="/doctor"><strong>🩺 Doctor</strong><span>Проверка и ремонт</span></a><a href="/diagnostics"><strong>✓ Диагностика</strong><span>Сеть и AWG</span></a></div>';
 hero.parentNode.insertBefore(root,hero);
 var state=root.querySelector('#nova-cc-state'),detail=root.querySelector('#nova-cc-detail'),score=root.querySelector('#nova-cc-score'),dot=root.querySelector('.nova-health-dot');
 async function refresh(){
  state.textContent='Проверяем систему…';dot.classList.remove('bad');
  try{
   var r=await fetch('/api/doctor',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);
   var d=await r.json();var s=Number(d.score||0);score.textContent=s+'%';
   if(d.ok){state.textContent='Система в норме';detail.textContent='AWG · Panel · Nginx · Network';}
   else{state.textContent='Требуется внимание';detail.textContent=(d.results||[]).filter(function(x){return !x.ok}).length+' проверок требуют внимания';dot.classList.add('bad');}
  }catch(e){state.textContent='Health недоступен';detail.textContent='Открыть NOVA Doctor для проверки';score.textContent='—';dot.classList.add('bad');}
 }
 root.querySelector('#nova-cc-refresh').addEventListener('click',refresh);
 refresh();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
</script>'''

def apply(nova):
    @nova.core.app.after_request
    def _nova_command_center(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html=response.get_data(as_text=True)
                if 'nova-command-center-js' not in html:
                    payload=CSS+JS
                    if '</head>' in html: html=html.replace('</head>',payload+'</head>',1)
                    elif '</body>' in html: html=html.replace('</body>',payload+'</body>',1)
                    else: html+=payload
                    response.set_data(html)
        except Exception:
            pass
        return response
    return nova
