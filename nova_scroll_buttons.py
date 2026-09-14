"""NOVA sidebar arrows: hard-wired scrolling controller.

The controls are deliberately handled at document capture level so they work
with either NOVA arrow implementation and with nested sidebar scroll areas.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
.nova-scroll-controls{position:fixed!important;z-index:2147483647!important;display:flex!important;flex-direction:column!important;gap:6px!important;width:38px!important;pointer-events:auto!important}
.nova-scroll-controls button,.nova16-nav-buttons button{pointer-events:auto!important;touch-action:manipulation!important;user-select:none!important}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function sidebar(){return document.querySelector('.sidebar');}
 function scrollTarget(side){
   if(!side)return null;
   if(side.scrollHeight>side.clientHeight+2)return side;
   var all=side.querySelectorAll('*'),best=null,bestArea=0;
   for(var i=0;i<all.length;i++){
    var e=all[i],s=getComputedStyle(e);
    if(e.scrollHeight>e.clientHeight+2 && /(auto|scroll|overlay)/.test(s.overflowY)){
     var area=e.clientWidth*e.clientHeight;
     if(area>bestArea){best=e;bestArea=area;}
    }
   }
   return best||document.scrollingElement||document.documentElement;
 }
 function doScroll(dir){
   var side=sidebar(),sc=scrollTarget(side);
   if(!sc)return;
   var amount=Math.max(180,Math.round((sc.clientHeight||window.innerHeight)*.68));
   var old=sc.scrollTop;
   sc.scrollTop=Math.max(0,Math.min(sc.scrollHeight-sc.clientHeight,old+dir*amount));
   if(sc.scrollTop===old && sc!==side && side){
    old=side.scrollTop;
    side.scrollTop=Math.max(0,Math.min(side.scrollHeight-side.clientHeight,old+dir*amount));
   }
   if(sc===document.documentElement||sc===document.body){window.scrollBy(0,dir*amount);}
 }
 function arrowDir(el){
   if(!el)return 0;
   var t=((el.getAttribute('aria-label')||'')+' '+(el.title||'')+' '+(el.textContent||'')).toLowerCase();
   if(t.indexOf('вниз')>=0||t.indexOf('down')>=0||t.indexOf('▼')>=0)return 1;
   if(t.indexOf('вверх')>=0||t.indexOf('up')>=0||t.indexOf('▲')>=0)return -1;
   return 0;
 }
 function handle(e){
   var el=e.target&&e.target.closest?e.target.closest('.nova-scroll-controls button,.nova16-nav-buttons button'):null;
   if(!el)return;
   var d=arrowDir(el);if(!d)return;
   e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();
   doScroll(d);
 }
 document.addEventListener('click',handle,true);
 document.addEventListener('pointerup',function(e){
   var el=e.target&&e.target.closest?e.target.closest('.nova-scroll-controls button,.nova16-nav-buttons button'):null;
   if(el){e.preventDefault();e.stopPropagation();}
 },true);
 document.addEventListener('touchend',handle,true);
 function init(){
  var side=sidebar();if(!side)return;
  if(!document.querySelector('.nova-scroll-controls')){
   var box=document.createElement('div');box.className='nova-scroll-controls';box.setAttribute('aria-label','Навигация меню');
   box.innerHTML='<button type="button" title="Вверх" aria-label="Вверх">▲</button><button type="button" title="Вниз" aria-label="Вниз">▼</button>';
   document.body.appendChild(box);
  }
  function place(){
   var r=side.getBoundingClientRect();
   var boxes=document.querySelectorAll('.nova-scroll-controls');
   for(var i=0;i<boxes.length;i++){
    boxes[i].style.display='flex';boxes[i].style.left=Math.max(4,Math.round(r.right-44))+'px';boxes[i].style.top=Math.max(70,Math.round(window.innerHeight-104))+'px';
   }
  }
  place();window.addEventListener('resize',place,{passive:true});setTimeout(place,500);setTimeout(place,1500);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
 setTimeout(init,700);setTimeout(init,1800);
})();
</script>'''

def apply(nova):
    @nova.core.app.after_request
    def _nova_scroll_buttons(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html=response.get_data(as_text=True)
                if 'nova-scroll-buttons-js' not in html:
                    payload=CSS+JS
                    if '</head>' in html: html=html.replace('</head>',payload+'</head>',1)
                    elif '</body>' in html: html=html.replace('</body>',payload+'</body>',1)
                    else: html+=payload
                    response.set_data(html)
        except Exception:
            pass
        return response
    return nova
