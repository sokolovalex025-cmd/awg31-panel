"""NOVA sidebar navigation controls.

The buttons navigate the actual sidebar menu instead of assuming that the
sidebar itself is the scroll container. They use visible menu items as anchors
and scroll the nearest usable container into view.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
.nova-scroll-controls{position:fixed!important;z-index:2147483647!important;display:flex!important;flex-direction:column!important;gap:6px!important;width:38px!important;pointer-events:auto!important}
.nova-scroll-controls button{display:flex!important;align-items:center!important;justify-content:center!important;width:38px!important;height:38px!important;min-width:38px!important;min-height:38px!important;margin:0!important;padding:0!important;border:1px solid rgba(255,255,255,.20)!important;border-radius:10px!important;background:rgba(18,27,40,.98)!important;color:#e7edf7!important;box-shadow:0 8px 28px rgba(0,0,0,.48)!important;font:900 18px/1 Arial,sans-serif!important;cursor:pointer!important;opacity:1!important;visibility:visible!important;pointer-events:auto!important}
.nova-scroll-controls button:hover{background:#2a3b54!important;color:#fff!important;transform:scale(1.04)!important}
.nova-scroll-controls button:active{transform:scale(.97)!important}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function init(){
  var side=document.querySelector('.sidebar');
  if(!side || document.querySelector('.nova-scroll-controls')) return;
  var box=document.createElement('div');
  box.className='nova-scroll-controls';
  box.setAttribute('aria-label','Навигация меню');
  box.innerHTML='<button type="button" title="Вверх" aria-label="Вверх">▲</button><button type="button" title="Вниз" aria-label="Вниз">▼</button>';
  document.body.appendChild(box);
  var up=box.children[0],down=box.children[1];

  function menuItems(){
   return Array.prototype.slice.call(side.querySelectorAll('a,button')).filter(function(el){
    if(el===up||el===down) return false;
    var r=el.getBoundingClientRect(),s=getComputedStyle(el);
    return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';
   });
  }
  function nearestScroller(el){
   var e=el;
   while(e&&e!==document.body){
    var s=getComputedStyle(e);
    if(e.scrollHeight>e.clientHeight+4&&s.overflowY!=='hidden'&&s.overflowY!=='visible') return e;
    e=e.parentElement;
   }
   return document.scrollingElement||document.documentElement;
  }
  function jump(dir){
   var list=menuItems();
   if(!list.length) return;
   var sr=side.getBoundingClientRect(),target=null,i;
   if(dir>0){
    for(i=0;i<list.length;i++){
     if(list[i].getBoundingClientRect().top>sr.bottom-8){target=list[i];break;}
    }
    if(!target) target=list[list.length-1];
   }else{
    for(i=list.length-1;i>=0;i--){
     if(list[i].getBoundingClientRect().bottom<sr.top+8){target=list[i];break;}
    }
    if(!target) target=list[0];
   }
   var before=target.getBoundingClientRect().top;
   target.scrollIntoView({behavior:'smooth',block:'center',inline:'nearest'});
   setTimeout(function(){
    if(Math.abs(target.getBoundingClientRect().top-before)<3){
     var sc=nearestScroller(side),amount=Math.max(220,Math.round((sc.clientHeight||window.innerHeight)*.65));
     if(sc===document.documentElement||sc===document.body) window.scrollBy({top:dir*amount,behavior:'smooth'});
     else sc.scrollBy({top:dir*amount,behavior:'smooth'});
    }
   },80);
  }
  function place(){
   var r=side.getBoundingClientRect();
   if(r.width<=0||r.right<=0||r.left>=window.innerWidth){box.style.display='none';return;}
   box.style.display='flex';
   box.style.left=Math.max(4,Math.round(r.right-44))+'px';
   box.style.top=Math.max(70,Math.round(window.innerHeight-104))+'px';
  }
  up.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();jump(-1);});
  down.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();jump(1);});
  window.addEventListener('resize',place,{passive:true});
  place();
  setTimeout(place,300);
  setTimeout(place,1200);
 }
 if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
 setTimeout(init,800);
 setTimeout(init,2000);
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
