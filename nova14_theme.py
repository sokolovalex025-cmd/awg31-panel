#!/usr/bin/env python3
"""NOVA 14 visual layer: Telegram, Domains and robust sidebar layout fix."""
CSS = r'''<style>
.telegram-nav{background:linear-gradient(100deg,rgba(39,143,220,.22),rgba(70,160,255,.08))!important;border-color:rgba(72,169,238,.30)!important;color:#d8f0ff!important}
.telegram-nav.active{box-shadow:inset 3px 0 #46a7ff,0 8px 24px rgba(30,120,210,.12)!important}
.telegram-card{background:linear-gradient(145deg,rgba(15,34,52,.92),rgba(8,16,25,.96))!important;border-color:rgba(72,169,238,.20)!important}
.telegram-status{display:inline-flex;align-items:center;gap:8px;padding:7px 11px;border-radius:999px;background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.22);color:#67e3b8;font-size:11px;font-weight:800}
.telegram-dot{width:8px;height:8px;border-radius:50%;background:#45dfb0;box-shadow:0 0 14px rgba(69,223,176,.65)}
.sidebar{overflow-y:scroll!important;overflow-x:hidden!important;scrollbar-width:auto!important;scrollbar-color:#687994 #080c13!important;padding-bottom:22px!important}
.sidebar::-webkit-scrollbar{width:13px!important;display:block!important}.sidebar::-webkit-scrollbar-track{background:#080c13!important;border-left:1px solid rgba(255,255,255,.05)!important}.sidebar::-webkit-scrollbar-thumb{background:#687994!important;border:3px solid #080c13!important;border-radius:10px!important;min-height:55px!important}.sidebar::-webkit-scrollbar-thumb:hover{background:#8293b1!important}
.server{position:relative!important;left:auto!important;right:auto!important;bottom:auto!important;top:auto!important;margin:22px 2px 6px!important;flex:0 0 auto!important}.sidebar .server{width:auto!important}.nav{padding-bottom:2px!important}
</style>'''
def apply(nova):
    nova.NOVA_CSS += CSS
    old=nova.nova_nav
    def nav(path):
        html=old(path); marker='<div class="section">СИСТЕМА</div>'
        items=[
          '<a class="telegram-nav %s" href="/telegram"><i>✈</i>Telegram</a>' % ('active' if path.startswith('/telegram') else ''),
          '<a class="telegram-nav %s" href="/domains"><i>🌐</i>Домены</a>' % ('active' if path.startswith('/domains') else '')
        ]
        for item in items:
            if item not in html: html=html.replace(marker,item+marker,1)
        return html
    nova.core.nav=nav
    return nova
