"""NOVA 16 final UI hotfix: remove legacy server card and force page/sidebar scrollbars.

Presentation-only. Does not modify AWG configuration or runtime state.
"""
import re

CSS = r"""
<style id="nova16-final-ui">
html{min-height:100%!important;height:auto!important;overflow-y:scroll!important;overflow-x:hidden!important;scrollbar-gutter:stable!important;scrollbar-width:auto!important;scrollbar-color:#687994 #080c13!important}
body{min-height:100vh!important;height:auto!important;overflow-y:scroll!important;overflow-x:hidden!important;scrollbar-gutter:stable!important;scrollbar-width:auto!important;scrollbar-color:#687994 #080c13!important}
html::-webkit-scrollbar,body::-webkit-scrollbar{width:13px!important;display:block!important}
html::-webkit-scrollbar-track,body::-webkit-scrollbar-track{background:#080c13!important;border-left:1px solid rgba(255,255,255,.05)!important}
html::-webkit-scrollbar-thumb,body::-webkit-scrollbar-thumb{background:#687994!important;border:3px solid #080c13!important;border-radius:10px!important;min-height:55px!important}
html::-webkit-scrollbar-thumb:hover,body::-webkit-scrollbar-thumb:hover{background:#8293b1!important}
.sidebar{height:100vh!important;max-height:100vh!important;overflow-y:scroll!important;overflow-x:hidden!important;scrollbar-gutter:stable!important;scrollbar-width:auto!important;scrollbar-color:#687994 #080c13!important}
.sidebar::-webkit-scrollbar{width:13px!important;display:block!important}
.sidebar::-webkit-scrollbar-track{background:#080c13!important;border-left:1px solid rgba(255,255,255,.05)!important}
.sidebar::-webkit-scrollbar-thumb{background:#687994!important;border:3px solid #080c13!important;border-radius:10px!important;min-height:55px!important}
.sidebar::-webkit-scrollbar-thumb:hover{background:#8293b1!important}
.nova16-scrollbar{position:fixed!important;width:12px!important;z-index:2147483000!important;pointer-events:auto!important;background:#080c13!important;border-left:1px solid rgba(255,255,255,.08)!important;display:none}
.nova16-scrollbar-thumb{position:absolute!important;left:2px!important;top:0;width:8px!important;min-height:42px!important;border-radius:8px!important;background:#687994!important;box-shadow:0 0 0 1px rgba(255,255,255,.08),0 2px 8px rgba(0,0,0,.35)!important;cursor:grab!important}
.nova16-scrollbar-thumb:hover{background:#8293b1!important}
.nova16-scrollbar-thumb.dragging{cursor:grabbing!important;background:#91a1bf!important}
</style>
<script id="nova16-scrollbar-script">
(function(){
function init(){
 var side=document.querySelector('.sidebar');
 if(!side||side.dataset.nova16ScrollbarReady==='1')return;
 side.dataset.nova16ScrollbarReady='1';
 var bar=document.createElement('div');bar.className='nova16-scrollbar';
 var thumb=document.createElement('div');thumb.className='nova16-scrollbar-thumb';bar.appendChild(thumb);document.body.appendChild(bar);
 function layout(){
  var r=side.getBoundingClientRect(),h=side.clientHeight,sh=side.scrollHeight;
  var visible=r.width>0&&r.right>0&&r.left<window.innerWidth&&sh>h+2;
  bar.style.display=visible?'block':'none';if(!visible)return;
  var top=Math.max(0,r.top),height=Math.min(h,window.innerHeight-top);
  bar.style.left=Math.max(0,Math.round(r.right-12))+'px';bar.style.top=top+'px';bar.style.height=height+'px';
  var th=Math.max(42,Math.round(height*h/sh));th=Math.min(th,height);thumb.style.height=th+'px';
  var maxTop=Math.max(1,height-th),maxScroll=Math.max(1,sh-h);
  thumb.style.top=Math.round((side.scrollTop/maxScroll)*maxTop)+'px';
 }
 side.addEventListener('scroll',layout,{passive:true});window.addEventListener('resize',layout,{passive:true});
 var dragging=false,startY=0,startScroll=0;
 thumb.addEventListener('pointerdown',function(e){dragging=true;startY=e.clientY;startScroll=side.scrollTop;thumb.classList.add('dragging');try{thumb.setPointerCapture(e.pointerId)}catch(_){}e.preventDefault()});
 thumb.addEventListener('pointermove',function(e){if(!dragging)return;var maxTop=Math.max(1,bar.clientHeight-thumb.offsetHeight),maxScroll=Math.max(0,side.scrollHeight-side.clientHeight);side.scrollTop=startScroll+(e.clientY-startY)*(maxScroll/maxTop);layout()});
 thumb.addEventListener('pointerup',function(){dragging=false;thumb.classList.remove('dragging')});thumb.addEventListener('pointercancel',function(){dragging=false;thumb.classList.remove('dragging')});
 bar.addEventListener('pointerdown',function(e){if(e.target===thumb)return;var rect=bar.getBoundingClientRect(),h=bar.clientHeight,th=thumb.offsetHeight,maxTop=Math.max(1,h-th),maxScroll=Math.max(0,side.scrollHeight-side.clientHeight),target=Math.max(0,Math.min(maxTop,e.clientY-rect.top-th/2));side.scrollTop=(target/maxTop)*maxScroll;layout()});
 layout();setTimeout(layout,250);setTimeout(layout,1000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
</script>
"""

def apply(nova):
    app=nova.core.app
    if 'id="nova16-final-ui"' not in nova.NOVA_CSS:
        nova.NOVA_CSS += CSS
    @app.after_request
    def _nova16_final_ui(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html=response.get_data(as_text=True)
                cleaned=re.sub(r'<div class=server>.*?</div>','',html,count=1,flags=re.S)
                # IMPORTANT: inject even when the legacy server card is absent.
                # The previous version only injected when HTML changed, so the
                # scrollbar hotfix could silently be skipped on normal pages.
                if '</head>' in cleaned and 'id="nova16-final-ui"' not in cleaned:
                    cleaned=cleaned.replace('</head>',CSS+'</head>',1)
                if cleaned!=html:
                    response.set_data(cleaned)
        except Exception:
            pass
        return response
    return nova
