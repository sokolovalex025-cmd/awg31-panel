#!/usr/bin/env python3
"""NOVA 12 UI compatibility layer.

Presentation-only patch: keeps the existing NOVA 11 routes/layout and exposes
NOVA 12 diagnostics without modifying AWG runtime state.
"""


def apply(nova11):
    core = nova11.core
    if getattr(core, "_nova12_ui_patched", False):
        return True

    original_nav = core.nav

    def nav(path):
        html = original_nav(path)
        marker = '<div class="section">ПАНЕЛЬ</div>'
        item = '<a class="%s" href="/mobile-diagnostics"><i>📱</i>Мобильная диагностика</a>' % (
            'active' if path == '/mobile-diagnostics' else ''
        )
        if marker in html and '/mobile-diagnostics' not in html:
            html = html.replace(marker, item + marker, 1)
        return html

    core.nav = nav
    core.VERSION = '12.0'
    core.BG_VERSION = 'NOVA12'
    core._nova12_ui_patched = True
    return True
