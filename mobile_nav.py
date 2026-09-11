#!/usr/bin/env python3
"""AWG Panel 9.3 visual refresh and compact mobile navigation."""


def register(app):
    import app as core
    original_layout = core.layout
    if getattr(core, "_mobile_nav_93", False):
        return

    css = r'''
/* =========================================================
   AWG PANEL 9.3 — VISUAL REFRESH
   Clean dark control-center UI, responsive on desktop/mobile
   ========================================================= */
:root{
  --bg:#050b14;--panel:#0b1422;--panel2:#0e1a2b;--panel3:#101f33;
  --line:rgba(148,190,230,.13);--line2:rgba(148,190,230,.22);
  --text:#f2f7fc;--muted:#8fa4ba;--soft:#c3d2e1;
  --accent:#48bfff;--accent2:#7b6cff;--good:#43d39e;--warn:#f4bd61;--bad:#ff647c;
  --radius:16px;--shadow:0 16px 42px rgba(0,0,0,.28)
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;background:var(--bg)}
body{background:radial-gradient(900px 500px at 82% -10%,rgba(72,191,255,.10),transparent 62%),radial-gradient(700px 420px at 10% 20%,rgba(123,108,255,.07),transparent 62%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;letter-spacing:.01em}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.014) 1px,transparent 1px);background-size:32px 32px;mask-image:linear-gradient(to bottom,rgba(0,0,0,.45),transparent 80%);z-index:-1}
::selection{background:rgba(72,191,255,.28);color:#fff}
::-webkit-scrollbar{width:9px;height:9px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:#274058;border-radius:99px}::-webkit-scrollbar-thumb:hover{background:#385a78}
.shell{min-height:100vh;background:transparent}
.side{background:linear-gradient(180deg,rgba(9,20,34,.96),rgba(6,14,25,.96));border-right:1px solid var(--line);backdrop-filter:blur(18px);box-shadow:18px 0 50px rgba(0,0,0,.18);padding:18px 14px}
.brand{padding:7px 8px 18px;border-bottom:1px solid var(--line);margin-bottom:13px}.brand h2{font-weight:750;letter-spacing:-.02em}.brand small{color:#6f879e}
.logo{box-shadow:0 0 0 1px rgba(72,191,255,.22),0 8px 24px rgba(72,191,255,.12)}
.menu{gap:4px}.menu a{position:relative;color:#9eb1c4!important;border:1px solid transparent;transition:background .18s,border-color .18s,color .18s,transform .18s;min-height:40px;display:flex;align-items:center}.menu a:hover{background:rgba(255,255,255,.045);border-color:var(--line);color:#eef7ff!important;transform:translateX(2px)}.menu a.active,.menu a[aria-current="page"]{background:linear-gradient(90deg,rgba(72,191,255,.13),rgba(123,108,255,.07));border-color:rgba(72,191,255,.20);color:#fff!important;box-shadow:inset 3px 0 0 var(--accent)}
.sidebox{background:linear-gradient(145deg,rgba(72,191,255,.07),rgba(123,108,255,.05));border:1px solid var(--line);border-radius:14px;padding:12px!important}
.main{padding-bottom:36px}.top{border-bottom:1px solid var(--line);background:rgba(5,11,20,.58);backdrop-filter:blur(18px);position:sticky;top:0;z-index:8}.top .pill,.pill{border:1px solid var(--line2);background:rgba(14,26,43,.82);box-shadow:0 5px 20px rgba(0,0,0,.15)}
.hero{position:relative;padding:8px 2px 4px}.hero h1{font-weight:780;letter-spacing:-.045em;line-height:1.03;background:linear-gradient(100deg,#fff 15%,#bfeaff 65%,#9c92ff);-webkit-background-clip:text;background-clip:text;color:transparent}.hero p{color:var(--muted)}.eyebrow{color:#67caff!important;letter-spacing:.16em;font-weight:700}
.card{background:linear-gradient(145deg,rgba(15,29,47,.90),rgba(9,19,32,.90));border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);transition:transform .2s,border-color .2s,box-shadow .2s}.card:hover{border-color:rgba(72,191,255,.22);box-shadow:0 18px 48px rgba(0,0,0,.34)}
.progrid>.card{position:relative;overflow:hidden}.progrid>.card:before{content:"";position:absolute;width:130px;height:130px;right:-55px;top:-65px;border-radius:50%;background:rgba(72,191,255,.08);filter:blur(2px)}
.klabel{color:#7189a0;font-size:11px;text-transform:uppercase;letter-spacing:.12em;font-weight:700}.kvalue{font-weight:800;letter-spacing:-.04em}.kvalue.ok,.good{color:var(--good)!important}.kvalue.bad,.bad{color:var(--bad)!important}
.btn,button{border:1px solid rgba(72,191,255,.20)!important;background:linear-gradient(180deg,rgba(27,52,75,.95),rgba(17,34,53,.95))!important;color:#eaf6ff!important;font-weight:650;box-shadow:0 5px 16px rgba(0,0,0,.16);transition:all .16s}.btn:hover,button:hover{border-color:rgba(72,191,255,.45)!important;background:linear-gradient(180deg,rgba(35,72,101,.98),rgba(20,43,66,.98))!important;transform:translateY(-1px)}.btn:active,button:active{transform:translateY(0) scale(.98)}
input,select,textarea{background:#071321!important;color:#edf7ff!important;border:1px solid var(--line2)!important;border-radius:10px!important;outline:none;transition:border-color .15s,box-shadow .15s}input::placeholder,textarea::placeholder{color:#5d7389}input:focus,select:focus,textarea:focus{border-color:rgba(72,191,255,.55)!important;box-shadow:0 0 0 3px rgba(72,191,255,.09)}
label{color:#9db0c3;font-weight:600}
table{border-collapse:separate!important;border-spacing:0!important;width:100%;overflow:hidden;border:1px solid var(--line);border-radius:12px;background:rgba(5,12,21,.30)}th{background:rgba(255,255,255,.035);color:#8ea5bb;text-transform:uppercase;font-size:10px;letter-spacing:.09em;font-weight:750}th,td{border-bottom:1px solid var(--line)!important}tr:last-child td{border-bottom:0!important}tbody tr:hover,table tr:hover td{background:rgba(72,191,255,.025)}
pre{background:#050d17!important;border:1px solid var(--line);border-radius:12px;color:#b8d0e4;overflow:auto}
.metricrow{align-items:center}.bar{background:#07111e!important;border:1px solid var(--line);border-radius:99px;overflow:hidden}.bar i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--accent),var(--accent2));box-shadow:0 0 15px rgba(72,191,255,.28)}
.action{background:linear-gradient(145deg,rgba(18,35,55,.78),rgba(8,18,31,.78))!important;border:1px solid var(--line)!important;border-radius:13px!important;transition:transform .18s,border-color .18s,background .18s}.action:hover{transform:translateY(-2px);border-color:rgba(72,191,255,.28)!important;background:linear-gradient(145deg,rgba(24,48,73,.88),rgba(10,23,39,.88))!important}.action strong{color:#edf6ff}.action .muted{color:#71879c}
.statusrow{border-bottom:1px solid var(--line)!important}.statusrow:last-child{border-bottom:0!important}.muted{color:var(--muted)}
.warn{border-color:rgba(244,189,97,.22)!important;background:linear-gradient(145deg,rgba(73,55,24,.20),rgba(12,23,35,.82))!important}
canvas{display:block;border-radius:12px;background:linear-gradient(180deg,rgba(72,191,255,.025),transparent)}
.footer{color:#60778c;border-top:1px solid var(--line);padding-top:14px}
/* compact mobile drawer */
.mobile-menu-btn{display:none;position:fixed;top:8px;left:10px;z-index:40;width:40px;height:40px;padding:0;border:1px solid rgba(72,191,255,.30)!important;border-radius:11px;background:rgba(7,19,33,.94)!important;color:#fff!important;font-size:20px;line-height:1;box-shadow:0 9px 26px rgba(0,0,0,.38);backdrop-filter:blur(12px)}
.mobile-menu-btn:hover{transform:none!important}.mobile-menu-btn:active{transform:scale(.95)!important}
.mobile-overlay{display:none}
@media(max-width:900px){.hero h1{font-size:32px}.progrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){
 html,body{font-size:14px;overflow-x:hidden}.shell{display:block;min-height:100vh}.main{width:100%;padding:0 10px 26px}
 .mobile-menu-btn{display:grid;place-items:center}.top>div:first-child{padding-left:48px}.top{margin:0 -10px 10px;padding:0 10px;height:54px;background:rgba(5,11,20,.78)}
 .side{position:fixed!important;left:0;top:0;bottom:0;width:min(310px,88vw)!important;height:100vh!important;max-height:none!important;padding:15px 12px!important;z-index:35;transform:translateX(-105%);transition:transform .24s cubic-bezier(.2,.8,.2,1);box-shadow:16px 0 42px rgba(0,0,0,.55)!important;overflow-y:auto!important}
 body.mobile-menu-open .side{transform:translateX(0)}.mobile-overlay{display:block;position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:30;opacity:0;pointer-events:none;backdrop-filter:blur(2px);transition:opacity .2s}.mobile-overlay.open,body.mobile-menu-open .mobile-overlay{opacity:1;pointer-events:auto}body.mobile-menu-open{overflow:hidden}
 .menu{max-height:none!important;overflow:visible!important}.menu a{min-height:42px;padding:9px 11px!important;margin:3px 0;font-size:13px!important}.brand{padding-bottom:14px;margin-bottom:11px}.logo{width:38px;height:38px}
 .hero{padding:2px 0 4px;margin:10px 0 13px}.hero h1{font-size:27px;margin:5px 0}.hero p{font-size:13px;line-height:1.45}.eyebrow{font-size:9px}
 .progrid,.grid,.actions,.two,.awgform{grid-template-columns:1fr!important;gap:9px}.card{padding:13px!important;border-radius:14px}.card:hover{transform:none}.kvalue{font-size:23px}.action{min-height:0;padding:11px!important}.action strong{font-size:14px}
 .metricrow{grid-template-columns:54px 1fr 44px!important;gap:7px!important}.bar{height:7px}.btn,button{font-size:12px;padding:8px 10px}.top .pill{font-size:10px;padding:6px 8px}
 table{display:block;overflow-x:auto;white-space:nowrap;font-size:11px}th,td{padding:8px 7px!important}.clientform{grid-template-columns:1fr!important;gap:6px}.clientform button{width:100%}input,select,textarea{padding:9px!important}.footer{margin-top:18px}
}
@media(max-width:380px){.main{padding-left:8px;padding-right:8px}.top{margin-left:-8px;margin-right:-8px;padding-left:8px;padding-right:8px}.mobile-menu-btn{left:8px;width:38px;height:38px}.menu a{min-height:39px;padding:8px 10px!important;font-size:12px!important}.hero h1{font-size:25px}}
'''
    if hasattr(core, "CSS") and "AWG PANEL 9.3 — VISUAL REFRESH" not in core.CSS:
        core.CSS = core.CSS.replace("</style>", css + "</style>")

    def wrapped_layout(title, body, p):
        html = original_layout(title, body, p)
        marker = '<aside class=side>'
        controls = '''<div class="mobile-overlay" id="mobileOverlay" onclick="closeMobileMenu()"></div><button class="mobile-menu-btn" type="button" aria-label="Открыть меню" aria-expanded="false" onclick="toggleMobileMenu()">☰</button>'''
        if marker in html and 'id="mobileOverlay"' not in html:
            html = html.replace(marker, controls + marker, 1)
        script = '''<script>
(function(){
  window.toggleMobileMenu=function(){
    document.body.classList.toggle('mobile-menu-open');
    var b=document.querySelector('.mobile-menu-btn');
    if(b)b.setAttribute('aria-expanded',document.body.classList.contains('mobile-menu-open')?'true':'false');
  };
  window.closeMobileMenu=function(){
    document.body.classList.remove('mobile-menu-open');
    var b=document.querySelector('.mobile-menu-btn');
    if(b)b.setAttribute('aria-expanded','false');
  };
  document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMobileMenu();});
  document.addEventListener('click',function(e){if(e.target.closest('.menu a'))closeMobileMenu();});
})();
</script>'''
        return html.replace('</body>', script + '</body>') if '</body>' in html else html + script

    core.layout = wrapped_layout
    core._mobile_nav_93 = True
