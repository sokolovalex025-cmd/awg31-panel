"""NOVA sidebar navigation controls.

Reliable UP/DOWN controls for the fixed NOVA sidebar. The sidebar is the
actual scroll container in the NOVA 11 layout, so the controls change its
scrollTop directly instead of relying on scrollIntoView or browser heuristics.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
.nova-scroll-controls{position:fixed!important;z-index:2147483647!important;display:flex!important;flex-direction:column!important;gap:6px!important;width:38px!important;pointer-events:auto!important}
.nova-scroll-controls button{display:flex!important;align-items:center!important;justify-content:center!important;width:38px!important;height:38px!important;min-width:38px!important;min-height:38px!important;margin:0!important;padding:0!important;border:1px solid rgba(255,255,255,.20)!important;border-radius:10px!important;background:rgba(18,27,40,.98)!important;color:#e7edf7!important;box-shadow:0 8px 28px rgba(0,0,0,.48)!important;font:900 18px/1 Arial,sans-serif!important;cursor:pointer!important;opacity:1!important;visibility:visible!important;pointer-events:auto!important;touch-action:manipulation!important;user-select:none!important;-webkit-user-select:none!important}
.nova-scroll-controls button:hover{background:#2a3b54!important;color:#fff!important;transform:scale(1.04)!important}
.nova-scroll-controls button:active{transform:scale(.97)!important}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function init(){
  var side=document.querySelector('.sidebar');
  if(!side) return;
  var old=document.querySelector('.nova-scroll-controls');
  if(old) old.remove();

  var box=document.createElement('div');
  box.className='nova-scroll-controls';
  box.setAttribute('aria-label','Навигация меню');
  box.innerHTML='<button type="button" title="Вверх" aria-label="Вверх">▲</button><button type="button" title="Вниз" aria-label="Вниз">▼</button>';
  document.body.appendChild(box);
  var up=box.children[0],down=box.children[1];

  function maxScroll(){ return Math.max(0,side.scrollHeight-side.clientHeight); }
  function refresh(){
   var r=side.getBoundingClientRect();
   var visible=r.width>0 && r.right>0 && r.left<window.innerWidth && side.scrollHeight>side.clientHeight+2;
   box.style.display=visible?'flex':'none';
   if(!visible) return;
   box.style.left=Math.max(4,Math.round(r.right-44))+'px';
   box.style.top=Math.max(70,Math.round(window.innerHeight-104))+'px';
   var m=maxScroll();
   up.disabled=side.scrollTop<=1;
   down.disabled=side.scrollTop>=m-1;
  }

  function move(dir){
   var m=maxScroll();
   if(m<=0) return;
   var step=Math.max(120,Math.round(side.clientHeight*0.72));
   var from=side.scrollTop;
   var to=Math.max(0,Math.min(m,from+dir*step));

   /* Direct assignment is intentional: .sidebar is position:fixed and
      overflow:auto in NOVA 11, so this bypasses nested-scroll ambiguity. */
   side.scrollTop=to;
   if(Math.abs(side.scrollTop-to)>1){
    side.scrollTop=to;
    try{side.scrollTo(0,to)}catch(_){}
   }
   refresh();
  }

  function activate(e,dir){
   if(e){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();}
   move(dir);
   return false;
  }

  up.addEventListener('pointerdown',function(e){activate(e,-1)},{capture:true,passive:false});
  down.addEventListener('pointerdown',function(e){activate(e,1)},{capture:true,passive:false});
  up.addEventListener('click',function(e){activate(e,-1)},{capture:true,passive:false});
  down.addEventListener('click',function(e){activate(e,1)},{capture:true,passive:false});
  up.addEventListener('touchstart',function(e){activate(e,-1)},{capture:true,passive:false});
  down.addEventListener('touchstart',function(e){activate(e,1)},{capture:true,passive:false});

  side.addEventListener('scroll',refresh,{passive:true});
  window.addEventListener('resize',refresh,{passive:true});
  refresh();
  setTimeout(refresh,300);
  setTimeout(refresh,1000);
 }

 function boot(){
  if(document.body) init();
 }
 if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot,{once:true});
 else boot();
 setTimeout(boot,800);
 setTimeout(boot,2000);
})();
</script>'''

def apply(nova):
    app=nova.core.app
    @app.after_request
    def _nova_scroll_buttons(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html=response.get_data(as_text=True)
                if 'nova-scroll-buttons-css' not in html:
                    payload=CSS+JS
                    if '</head>' in html: html=html.replace('</head>',payload+'</head>',1)
                    elif '</body>' in html: html=html.replace('</body>',payload+'</body>',1)
                    else: html+=payload
                    response.set_data(html)
        except Exception:
            pass
        return response
    return nova
