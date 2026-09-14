"""NOVA sidebar navigation controls.

Adds permanent UP/DOWN buttons to the actual sidebar edge.  The controls
work with the sidebar itself and also detect nested scroll containers, so the
UI does not depend on a visible native scrollbar.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
.nova-scroll-controls{
 position:fixed!important;
 z-index:2147483647!important;
 display:flex!important;
 flex-direction:column!important;
 gap:6px!important;
 width:38px!important;
 pointer-events:auto!important;
}
.nova-scroll-controls button{
 display:flex!important;
 align-items:center!important;
 justify-content:center!important;
 width:38px!important;
 height:38px!important;
 min-width:38px!important;
 min-height:38px!important;
 margin:0!important;
 padding:0!important;
 border:1px solid rgba(255,255,255,.20)!important;
 border-radius:10px!important;
 background:rgba(18,27,40,.98)!important;
 color:#e7edf7!important;
 box-shadow:0 8px 28px rgba(0,0,0,.48)!important;
 font:900 18px/1 Arial,sans-serif!important;
 cursor:pointer!important;
 opacity:1!important;
 visibility:visible!important;
}
.nova-scroll-controls button:hover{background:#2a3b54!important;color:#fff!important;transform:scale(1.04)!important}
.nova-scroll-controls button:active{transform:scale(.97)!important}
.nova-scroll-controls button:disabled{opacity:.45!important;cursor:pointer!important}
@media(max-width:760px){.nova-scroll-controls{z-index:2147483647!important}}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 'use strict';
 function init(){
  var side=document.querySelector('.sidebar');
  if(!side) return;
  var box=document.querySelector('.nova-scroll-controls');
  if(!box){
   box=document.createElement('div');
   box.className='nova-scroll-controls';
   box.setAttribute('aria-label','Навигация меню');
   box.innerHTML='<button type="button" title="Прокрутить меню вверх" aria-label="Вверх">▲</button><button type="button" title="Прокрутить меню вниз" aria-label="Вниз">▼</button>';
   document.body.appendChild(box);
  }
  var up=box.children[0], down=box.children[1];

  function scrollParent(){
   var e=side;
   while(e && e!==document.body){
    if(e.scrollHeight>e.clientHeight+4 && getComputedStyle(e).overflowY!=='hidden') return e;
    e=e.parentElement;
   }
   if(document.documentElement.scrollHeight>document.documentElement.clientHeight+4) return document.documentElement;
   return side;
  }

  function move(dir){
   var sc=scrollParent();
   var amount=Math.max(180,Math.round((sc.clientHeight||window.innerHeight)*.72));
   if(sc===document.documentElement || sc===document.body){
    window.scrollBy({top:dir*amount,behavior:'smooth'});
   }else{
    sc.scrollBy({top:dir*amount,behavior:'smooth'});
   }
   setTimeout(state,350);
  }

  function state(){
   var sc=scrollParent();
   var max=Math.max(0,sc.scrollHeight-sc.clientHeight);
   up.disabled=sc.scrollTop<=2;
   down.disabled=sc.scrollTop>=max-2;
   up.style.visibility='visible';
   down.style.visibility='visible';
   place();
  }

  function place(){
   var r=side.getBoundingClientRect();
   var x=Math.round(r.right-44);
   var y=Math.max(70,Math.round(window.innerHeight-104));
   if(r.width<=0 || r.right<=0 || r.left>=window.innerWidth){
    box.style.display='none';
    return;
   }
   box.style.display='flex';
   box.style.left=Math.max(4,x)+'px';
   box.style.top=y+'px';
  }

  up.onclick=function(e){e.preventDefault();move(-1);};
  down.onclick=function(e){e.preventDefault();move(1);};
  window.addEventListener('resize',place,{passive:true});
  window.addEventListener('scroll',place,{passive:true});
  side.addEventListener('scroll',state,{passive:true});
  place();
  state();
  setTimeout(state,300);
  setTimeout(state,1200);
 }
 if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
 else init();
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
                    if '</head>' in html:
                        html=html.replace('</head>',payload+'</head>',1)
                    elif '</body>' in html:
                        html=html.replace('</body>',payload+'</body>',1)
                    else:
                        html+=payload
                    response.set_data(html)
        except Exception:
            pass
        return response
    return nova
