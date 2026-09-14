"""NOVA sidebar arrows - direct, self-contained controller.

The controls live inside the sidebar so no overlay can steal their pointer
 events. Scrolling is performed directly on the sidebar element.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
/* Disable the older duplicate controller. */
.nova16-nav-buttons{display:none!important;pointer-events:none!important}
.nova-scroll-controls{position:fixed!important;left:0;bottom:18px;z-index:2147483647!important;display:flex!important;flex-direction:column!important;gap:7px!important;width:278px!important;padding:0 14px!important;pointer-events:none!important}
.nova-scroll-controls button{pointer-events:auto!important;display:flex!important;align-items:center!important;justify-content:center!important;width:44px!important;height:38px!important;margin-left:210px!important;padding:0!important;border:1px solid rgba(255,255,255,.22)!important;border-radius:10px!important;background:#121b28!important;color:#fff!important;font:900 20px/1 Arial,sans-serif!important;cursor:pointer!important;touch-action:manipulation!important;user-select:none!important;-webkit-tap-highlight-color:transparent!important;box-shadow:0 6px 20px rgba(0,0,0,.55)!important;opacity:1!important;visibility:visible!important}
.nova-scroll-controls button:hover{background:#2a3b54!important}
.nova-scroll-controls button:active{background:#405674!important;transform:scale(.96)!important}
@media(max-width:760px){.nova-scroll-controls{width:278px!important}.nova-scroll-controls button{margin-left:210px!important}}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function findSide(){return document.querySelector('.sidebar');}
 function getScroller(side){
   if(!side)return null;
   if(side.scrollHeight-side.clientHeight>2)return side;
   var nodes=side.querySelectorAll('*');
   for(var i=0;i<nodes.length;i++){
     var n=nodes[i],s=getComputedStyle(n);
     if(n.scrollHeight-n.clientHeight>2 && /(auto|scroll|overlay)/.test(s.overflowY))return n;
   }
   return side;
 }
 function scrollMenu(dir){
   var side=findSide(),sc=getScroller(side);
   if(!sc)return false;
   var max=Math.max(0,sc.scrollHeight-sc.clientHeight);
   var step=Math.max(180,Math.floor((sc.clientHeight||window.innerHeight)*0.70));
   var old=sc.scrollTop;
   var next=Math.max(0,Math.min(max,old+dir*step));
   sc.scrollTop=next;
   /* Force the browser to apply the position even when smooth scrolling was
      configured elsewhere in the stylesheet. */
   if(sc.scrollTop===old){
     sc.style.scrollBehavior='auto';
     sc.scrollTop=next;
   }
   return sc.scrollTop!==old || next===old;
 }
 function make(){
   var side=findSide();
   if(!side)return;
   /* Remove every previous instance, including the legacy NOVA16 one. */
   document.querySelectorAll('.nova-scroll-controls').forEach(function(x){x.remove();});
   document.querySelectorAll('.nova16-nav-buttons').forEach(function(x){x.remove();});
   var box=document.createElement('div');box.className='nova-scroll-controls';
   var up=document.createElement('button'),down=document.createElement('button');
   up.type='button';down.type='button';up.textContent='▲';down.textContent='▼';
   up.setAttribute('aria-label','Меню вверх');down.setAttribute('aria-label','Меню вниз');
   up.title='Прокрутить меню вверх';down.title='Прокрутить меню вниз';
   box.appendChild(up);box.appendChild(down);
   document.body.appendChild(box);
   function go(dir,e){
     if(e){e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();}
     scrollMenu(dir);
     return false;
   }
   up.onclick=function(e){return go(-1,e);};
   down.onclick=function(e){return go(1,e);};
   up.onpointerdown=function(e){e.preventDefault();};
   down.onpointerdown=function(e){e.preventDefault();};
   up.ontouchstart=function(e){e.preventDefault();scrollMenu(-1);};
   down.ontouchstart=function(e){e.preventDefault();scrollMenu(1);};
 }
 function start(){setTimeout(make,50);setTimeout(make,500);setTimeout(make,1500);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
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
