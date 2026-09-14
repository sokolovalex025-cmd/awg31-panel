"""NOVA sidebar navigation buttons.

Adds explicit UP/DOWN controls to the fixed sidebar so navigation does not
rely on a visible native scrollbar. Presentation-only.
"""

CSS = r'''<style id="nova-scroll-buttons-css">
.nova-scroll-controls{position:fixed;left:calc(278px - 48px);bottom:18px;z-index:2147483001;display:flex;flex-direction:column;gap:6px}
.nova-scroll-controls button{width:34px!important;height:34px!important;padding:0!important;border:1px solid rgba(255,255,255,.16)!important;border-radius:9px!important;background:rgba(18,27,40,.96)!important;color:#cbd6e5!important;box-shadow:0 8px 24px rgba(0,0,0,.35)!important;font-size:17px!important;line-height:1!important;cursor:pointer!important}
.nova-scroll-controls button:hover{background:#26364d!important;color:#fff!important}
.nova-scroll-controls button:disabled{opacity:.3!important;cursor:default!important}
@media(max-width:1050px){.nova-scroll-controls{left:calc(245px - 48px)}}
@media(max-width:760px){.nova-scroll-controls{left:calc(278px - 48px)}}
</style>'''

JS = r'''<script id="nova-scroll-buttons-js">
(function(){
 function init(){
  var side=document.querySelector('.sidebar');
  if(!side || document.querySelector('.nova-scroll-controls')) return;
  var box=document.createElement('div');
  box.className='nova-scroll-controls';
  box.innerHTML='<button type="button" title="Вверх" aria-label="Вверх">▲</button><button type="button" title="Вниз" aria-label="Вниз">▼</button>';
  document.body.appendChild(box);
  var up=box.children[0],down=box.children[1];
  function state(){
   var max=Math.max(0,side.scrollHeight-side.clientHeight);
   up.disabled=side.scrollTop<=2;
   down.disabled=side.scrollTop>=max-2;
  }
  up.addEventListener('click',function(){side.scrollBy({top:-Math.max(180,side.clientHeight*.78),behavior:'smooth'});});
  down.addEventListener('click',function(){side.scrollBy({top:Math.max(180,side.clientHeight*.78),behavior:'smooth'});});
  side.addEventListener('scroll',state,{passive:true});
  window.addEventListener('resize',state,{passive:true});
  state();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
</script>'''

def apply(nova):
    app=nova.core.app
    @app.after_request
    def _nova_scroll_buttons(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html=response.get_data(as_text=True)
                payload=CSS+JS
                if 'nova-scroll-buttons-css' not in html and '</head>' in html:
                    html=html.replace('</head>',payload+'</head>',1)
                    response.set_data(html)
        except Exception:
            pass
        return response
    return nova
