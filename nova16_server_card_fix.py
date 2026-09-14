"""NOVA 16 final UI hotfix: remove legacy server card and force page/sidebar scrollbars.

Presentation-only. Does not modify AWG configuration or runtime state.
"""
import re

CSS = r"""
<style id="nova16-final-ui">
/* Keep a native document scrollbar where the browser supports it. */
html{
  min-height:100%!important;
  height:auto!important;
  overflow-y:scroll!important;
  overflow-x:hidden!important;
  scrollbar-gutter:stable!important;
  scrollbar-width:auto!important;
  scrollbar-color:#687994 #080c13!important;
}
body{
  min-height:100vh!important;
  height:auto!important;
  overflow-y:scroll!important;
  overflow-x:hidden!important;
  scrollbar-gutter:stable!important;
  scrollbar-width:auto!important;
  scrollbar-color:#687994 #080c13!important;
}
html::-webkit-scrollbar,
body::-webkit-scrollbar{width:13px!important;display:block!important}
html::-webkit-scrollbar-track,
body::-webkit-scrollbar-track{background:#080c13!important;border-left:1px solid rgba(255,255,255,.05)!important}
html::-webkit-scrollbar-thumb,
body::-webkit-scrollbar-thumb{background:#687994!important;border:3px solid #080c13!important;border-radius:10px!important;min-height:55px!important}
html::-webkit-scrollbar-thumb:hover,
body::-webkit-scrollbar-thumb:hover{background:#8293b1!important}

/* Sidebar: reserve a clearly visible scrollbar column at the exact right edge. */
.sidebar{
  height:100vh!important;
  max-height:100vh!important;
  overflow-y:scroll!important;
  overflow-x:hidden!important;
  scrollbar-gutter:stable!important;
  scrollbar-width:auto!important;
  scrollbar-color:#687994 #080c13!important;
}
.sidebar::-webkit-scrollbar{width:13px!important;display:block!important}
.sidebar::-webkit-scrollbar-track{background:#080c13!important;border-left:1px solid rgba(255,255,255,.05)!important}
.sidebar::-webkit-scrollbar-thumb{background:#687994!important;border:3px solid #080c13!important;border-radius:10px!important;min-height:55px!important}
.sidebar::-webkit-scrollbar-thumb:hover{background:#8293b1!important}

/* Fallback visual scrollbar: used when Chromium/Windows hides native overlay scrollbars. */
.nova16-scrollbar{
  position:fixed!important;
  width:12px!important;
  z-index:2147483000!important;
  pointer-events:none!important;
  background:#080c13!important;
  border-left:1px solid rgba(255,255,255,.08)!important;
}
.nova16-scrollbar-thumb{
  position:absolute!important;
  left:2px!important;
  top:0!important;
  width:8px!important;
  min-height:42px!important;
  border-radius:8px!important;
  background:#687994!important;
  box-shadow:0 0 0 1px rgba(255,255,255,.08),0 2px 8px rgba(0,0,0,.35)!important;
  pointer-events:auto!important;
  cursor:grab!important;
}
.nova16-scrollbar-thumb:hover{background:#8293b1!important}
.nova16-scrollbar-thumb.dragging{cursor:grabbing!important;background:#91a1bf!important}
</style>
<script id="nova16-scrollbar-script">
(function(){
  function init(){
    var side=document.querySelector('.sidebar');
    if(!side || side.dataset.nova16ScrollbarReady==='1') return;
    side.dataset.nova16ScrollbarReady='1';

    var bar=document.createElement('div');
    bar.className='nova16-scrollbar';
    var thumb=document.createElement('div');
    thumb.className='nova16-scrollbar-thumb';
    bar.appendChild(thumb);
    document.body.appendChild(bar);

    function layout(){
      var r=side.getBoundingClientRect();
      var h=side.clientHeight;
      var sh=side.scrollHeight;
      var visible=r.width>0 && r.right>0 && r.left<window.innerWidth && sh>h+2;
      bar.style.display=visible?'block':'none';
      if(!visible) return;
      var top=Math.max(0,r.top);
      var height=Math.min(h,window.innerHeight-top);
      bar.style.left=Math.max(0,Math.round(r.right-12))+'px';
      bar.style.top=top+'px';
      bar.style.height=height+'px';
      var th=Math.max(42,Math.round(height*h/sh));
      th=Math.min(th,height);
      thumb.style.height=th+'px';
      var maxTop=height-th;
      var maxScroll=Math.max(1,sh-h);
      thumb.style.top=Math.round((side.scrollTop/maxScroll)*maxTop)+'px';
    }

    side.addEventListener('scroll',layout,{passive:true});
    window.addEventListener('resize',layout,{passive:true});
    window.addEventListener('scroll',layout,{passive:true});

    var dragging=false,startY=0,startScroll=0;
    thumb.addEventListener('pointerdown',function(e){
      dragging=true; startY=e.clientY; startScroll=side.scrollTop;
      thumb.classList.add('dragging');
      thumb.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    thumb.addEventListener('pointermove',function(e){
      if(!dragging) return;
      var h=bar.clientHeight;
      var th=thumb.offsetHeight;
      var maxTop=Math.max(1,h-th);
      var maxScroll=Math.max(0,side.scrollHeight-side.clientHeight);
      side.scrollTop=startScroll+(e.clientY-startY)*(maxScroll/maxTop);
      layout();
    });
    thumb.addEventListener('pointerup',function(){dragging=false;thumb.classList.remove('dragging');});
    thumb.addEventListener('pointercancel',function(){dragging=false;thumb.classList.remove('dragging');});

    bar.addEventListener('pointerdown',function(e){
      if(e.target===thumb) return;
      var rect=bar.getBoundingClientRect();
      var h=bar.clientHeight, th=thumb.offsetHeight;
      var maxTop=Math.max(1,h-th);
      var maxScroll=Math.max(0,side.scrollHeight-side.clientHeight);
      var target=Math.max(0,Math.min(maxTop,e.clientY-rect.top-th/2));
      side.scrollTop=(target/maxTop)*maxScroll;
      layout();
    });
    layout();
    setTimeout(layout,250);
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);
  else init();
})();
</script>
"""


def apply(nova):
    app = nova.core.app
    nova.NOVA_CSS += CSS

    @app.after_request
    def _nova16_final_ui(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html = response.get_data(as_text=True)
                # Remove the legacy bottom-left server status card regardless of theme order.
                cleaned = re.sub(r'<div class=server>.*?</div>', '', html, count=1, flags=re.S)
                # Final CSS/JS is injected immediately before </head>, after all theme CSS.
                if '</head>' in cleaned and 'nova16-final-ui' not in cleaned:
                    cleaned = cleaned.replace('</head>', CSS + '</head>', 1)
                if cleaned != html:
                    response.set_data(cleaned)
        except Exception:
            pass
        return response

    return nova
