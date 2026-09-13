#!/usr/bin/env python3
"""Minimal health/metrics agent for an AWG 3.1 node.
Run on each worker VPS on a private/admin-only port (default 9090)."""
from flask import Flask, jsonify
import subprocess, time, os

app = Flask(__name__)
PORT = int(os.getenv('BALANCER_NODE_PORT','9090'))


def run(*args):
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=3)
    except Exception:
        return None


def metrics():
    r = run('awg','show','awg0','dump')
    clients = rx = tx = 0
    if r and r.returncode == 0:
        lines = r.stdout.strip().splitlines()
        clients = max(0, len(lines)-1)
        for line in lines[1:]:
            p = line.split('\t')
            if len(p) >= 7:
                try: rx += int(p[5])
                except ValueError: pass
                try: tx += int(p[6])
                except ValueError: pass
    return clients, rx, tx


@app.get('/health')
def health():
    r = run('systemctl','is-active','--quiet','awg-quick@awg0')
    if not r or r.returncode != 0:
        return jsonify({'ok':False,'status':'down'}), 503
    clients, rx, tx = metrics()
    return jsonify({'ok':True,'status':'online','clients':clients,'rx':rx,'tx':tx,'ts':int(time.time())})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
