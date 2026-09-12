#!/usr/bin/env python3
import app as core

core.VERSION='10.0'
core.BG_VERSION='NOVA'

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
