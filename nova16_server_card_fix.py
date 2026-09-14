"""NOVA 16 final UI hotfix: remove legacy server card and force page/sidebar scrollbars.

Presentation-only. Does not modify AWG configuration or runtime state.
"""
import re

CSS = r"""
<style id="nova16-final-ui">
/* Always keep a real document scrollbar on desktop and mobile browsers. */
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
</style>
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
                # Final CSS is injected immediately before </head>, after all theme CSS.
                if '</head>' in cleaned and 'nova16-final-ui' not in cleaned:
                    cleaned = cleaned.replace('</head>', CSS + '</head>', 1)
                if cleaned != html:
                    response.set_data(cleaned)
        except Exception:
            pass
        return response

    return nova
