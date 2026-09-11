#!/usr/bin/env python3
"""Compact slide-out navigation for AWG Panel on phones."""


def register(app):
    original_layout = app.view_functions.get("layout")
    # layout() is a module helper, not a Flask endpoint, so app.view_functions
    # does not contain it. Import the module and wrap the real helper instead.
    import app as core
    original_layout = core.layout
    if getattr(core, "_mobile_nav_93", False):
        return

    css = r'''
/* AWG Panel 9.3 compact slide-out mobile navigation */
.mobile-menu-btn{display:none;position:fixed;top:8px;left:10px;z-index:30;width:38px;height:38px;padding:0;border:1px solid #30beff55;border-radius:10px;background:#061426ee;color:#fff;font-size:21px;line-height:1;box-shadow:0 6px 18px #0007}
.mobile-menu-btn:active{transform:scale(.96)}
.mobile-overlay{display:none}
@media(max-width:760px){
  .mobile-menu-btn{display:grid;place-items:center}
  .top>div:first-child{padding-left:46px}
  .side{position:fixed!important;left:0;top:0;bottom:0;width:min(300px,86vw)!important;height:100vh!important;max-height:none!important;padding:14px 12px!important;z-index:25;transform:translateX(-105%);transition:transform .22s ease;box-shadow:12px 0 32px #0009!important;overflow-y:auto!important}
  body.mobile-menu-open .side{transform:translateX(0)}
  .mobile-overlay{display:block;position:fixed;inset:0;background:#0009;z-index:20;opacity:0;pointer-events:none;transition:opacity .2s ease}
  body.mobile-menu-open .mobile-overlay{opacity:1;pointer-events:auto}
  .menu{max-height:none!important;overflow:visible!important}
  .main{width:100%}
  body.mobile-menu-open{overflow:hidden}
}
'''
    if hasattr(core, "CSS") and "mobile-menu-btn" not in core.CSS:
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
  document.addEventListener('click',function(e){
    if(e.target.closest('.menu a'))closeMobileMenu();
  });
})();
</script>'''
        return html.replace('</body>', script + '</body>') if '</body>' in html else html + script

    core.layout = wrapped_layout
    core._mobile_nav_93 = True
