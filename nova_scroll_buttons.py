"""NOVA sidebar navigation - dedicated scroll viewport.

Creates a real inner scrolling viewport inside the existing sidebar. The
navigation links are moved into that viewport and the arrow buttons control
that viewport directly. The outer sidebar itself never scrolls.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
/* One real scroll owner: the inner viewport. */
.sidebar{overflow:hidden!important;height:100vh!important;max-height:100vh!important;}
.nova-sidebar-viewport{position:absolute!important;left:0!important;right:0!important;top:0!important;bottom:0!important;overflow-y:auto!important;overflow-x:hidden!important;padding:18px 14px 90px!important;scroll-behavior:auto!important;-webkit-overflow-scrolling:touch!important;scrollbar-width:thin!important;}
.nova-sidebar-viewport::-webkit-scrollbar{width:10px!important;display:block!important}
.nova-sidebar-viewport::-webkit-scrollbar-track{background:transparent!important}
.nova-sidebar-viewport::-webkit-scrollbar-thumb{background:#687994!important;border-radius:8px!important;border:2px solid transparent!important;background-clip:padding-box!important}
.nova-sidebar-viewport > .nova-sidebar-content{min-height:min-content!important}
.nova-scroll-controls{position:absolute!important;right:14px!important;bottom:18px!important;z-index:2147483647!important;display:flex!important;flex-direction:column!important;gap:7px!important;width:44px!important;pointer-events:none!important}
.nova-scroll-controls button{pointer-events:auto!important;display:flex!important;align-items:center!important;justify-content:center!important;width:44px!important;height:38px!important;min-width:44px!important;min-height:38px!important;padding:0!important;margin:0!important;border:1px solid rgba(255,255,255,.25)!important;border-radius:10px!important;background:#121b28!important;color:#fff!important;font:900 20px/1 Arial,sans-serif!important;cursor:pointer!important;touch-action:manipulation!important;user-select:none!important;-webkit-tap-highlight-color:transparent!important;box-shadow:0 6px 20px rgba(0,0,0,.55)!important}
.nova-scroll-controls button:hover{background:#2a3b54!important}
.nova-scroll-controls button:active{background:#405674!important;transform:scale(.96)!important}
.nova-scroll-controls button:disabled{opacity:.35!important;cursor:default!important}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function build(){
   var side=document.querySelector('.sidebar');
   if(!side)return;
   if(side.dataset.novaDedicatedScroll==='1')return;
   side.dataset.novaDedicatedScroll='1';

   /* Capture the existing sidebar children before inserting the viewport. */
   var viewport=document.createElement('div');
   viewport.className='nova-sidebar-viewport';
   var content=document.createElement('div');
   content.className='nova-sidebar-content';
   while(side.firstChild)content.appendChild(side.firstChild);
   viewport.appendChild(content);
   side.appendChild(viewport);

   /* Remove all previous arrow implementations. */
   document.querySelectorAll('.nova-scroll-controls,.nova16-nav-buttons,.nova16-scrollbar').forEach(function(x){x.remove();});

   var controls=document.createElement('div');
   controls.className='nova-scroll-controls';
   var up=document.createElement('button'),down=document.createElement('button');
   up.type='button';down.type='button';
   up.textContent='▲';down.textContent='▼';
   up.title='Прокрутить меню вверх';down.title='Прокрутить меню вниз';
   up.setAttribute('aria-label','Прокрутить меню вверх');down.setAttribute('aria-label','Прокрутить меню вниз');
   controls.appendChild(up);controls.appendChild(down);side.appendChild(controls);

   function update(){
     var max=Math.max(0,viewport.scrollHeight-viewport.clientHeight);
     up.disabled=viewport.scrollTop<=1;
     down.disabled=viewport.scrollTop>=max-1;
   }
   function move(dir){
     var max=Math.max(0,viewport.scrollHeight-viewport.clientHeight);
     var step=Math.max(160,Math.floor(viewport.clientHeight*.72));
     var next=Math.max(0,Math.min(max,viewport.scrollTop+dir*step));
     viewport.scrollTop=next;
     update();
   }
   function stop(e){e.preventDefault();e.stopPropagation();if(e.stopImmediatePropagation)e.stopImmediatePropagation();}
   up.addEventListener('click',function(e){stop(e);move(-1);},false);
   down.addEventListener('click',function(e){stop(e);move(1);},false);
   up.addEventListener('touchend',function(e){stop(e);move(-1);},false);
   down.addEventListener('touchend',function(e){stop(e);move(1);},false);
   viewport.addEventListener('scroll',update,{passive:true});
   window.addEventListener('resize',update,{passive:true});
   update();
   setTimeout(update,300);setTimeout(update,1000);
 }
 function start(){build();}
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
