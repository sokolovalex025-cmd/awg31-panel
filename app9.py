#!/usr/bin/env python3
import app as core

core.VERSION='10.0'
core.BG_VERSION='NOVA'

# NOVA AWG cluster modules. They register their routes against the same
# Flask application used by awgpanel.service.
try:
    import balancer
except Exception:
    balancer=None
try:
    import balancer_provision
except Exception:
    balancer_provision=None

# Left-side scrollbar for the fixed NOVA navigation panel.
# The inner content remains left-to-right while the native scrollbar is
# rendered on the left edge of the sidebar.
core.CSS = core.CSS.replace(
    '.sidebar{position:fixed;',
    '.sidebar{position:fixed;overflow-y:auto;direction:rtl;padding-bottom:120px;scrollbar-width:thin;scrollbar-color:#33445c transparent;'
)
core.CSS = core.CSS.replace(
    '.brand{display:flex;',
    '.sidebar>*{direction:ltr}.brand{display:flex;'
)
core.CSS = core.CSS.replace(
    '.nav{display:grid;',
    '.nav{display:grid;'
)
core.CSS += '''<style>
.sidebar::-webkit-scrollbar{width:7px}
.sidebar::-webkit-scrollbar-track{background:transparent}
.sidebar::-webkit-scrollbar-thumb{background:#33445c;border-radius:10px;border:2px solid transparent;background-clip:padding-box}
.sidebar::-webkit-scrollbar-thumb:hover{background:#4f8cff;background-clip:padding-box}
</style>'''

# Compatibility endpoint for older NOVA/8.x browser clients that still poll
# /api/traffic92. Keep it backed by the same AWG statistics used by NOVA 10.
@core.app.route('/api/traffic92')
def traffic92_compat():
    clients = core.client_stats()
    return core.jsonify({
        'ok': True,
        'panel_version': core.VERSION,
        'awg_online': core.online(),
        'clients': clients,
        'online_clients': sum(1 for x in clients if x['online']),
        'rx': sum(x['rx'] for x in clients),
        'tx': sum(x['tx'] for x in clients),
    })

if __name__=='__main__':
    core.app.run(host='0.0.0.0',port=8080)
