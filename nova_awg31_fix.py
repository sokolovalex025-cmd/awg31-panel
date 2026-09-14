#!/usr/bin/env python3
"""NOVA AWG 3.1 consistency and migration guard.

Keeps one shared HeaderProtectionKey on awg0 and makes generated client
configs inherit the exact live server parameters through app.cfg().
"""
from pathlib import Path
import subprocess
import time

CONF_CANDIDATES = (
    Path('/etc/amnezia/amneziawg/awg0.conf'),
    Path('/etc/wireguard/awg0.conf'),
)
BACKUP_DIR = Path('/opt/awg31-panel/backups')

PARAMS = {
    'Jc': '4', 'Jmin': '40', 'Jmax': '120',
    # With RandomTrailers enabled, keep S1-S4 identical as recommended by upstream.
    # S4=16 also keeps outer UDP packets conservative for mobile paths.
    'S1': '16', 'S2': '16', 'S3': '16', 'S4': '16',
    'H1': '1', 'H2': '2', 'H3': '3', 'H4': '4',
    'ContentPaddingAddition': '0-64',
    'RekeyAfterTime': '120-180', 'RekeyTimeout': '3-8',
    'RejectAfterTime': '150-210', 'KeepaliveTimeout': '8-15',
    'MaxHandshakeAttempts': '8-15',
    'RandomTrailers': 'on', 'DisableCookies': 'on',
}


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, timeout=30)


def conf_path():
    for p in CONF_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError('awg0.conf not found')


def genkey():
    r = run('awg', 'genkey')
    if r.returncode or not r.stdout.strip():
        raise RuntimeError((r.stderr or 'awg genkey failed').strip())
    return r.stdout.strip()


def parse_interface(text):
    cfg = {}
    for line in text.split('[Peer]', 1)[0].splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    return cfg


def set_interface_params(text, values):
    head, sep, peers = text.partition('[Peer]')
    lines = head.splitlines()
    out, seen = [], set()
    for line in lines:
        stripped = line.strip()
        if '=' not in stripped or stripped.startswith('#'):
            out.append(line)
            continue
        key = stripped.split('=', 1)[0].strip()
        if key in values:
            if key in seen:
                continue
            out.append(f'{key} = {values[key]}')
            seen.add(key)
        else:
            out.append(line)
    for key, value in values.items():
        if key not in seen:
            out.append(f'{key} = {value}')
    new_head = '\n'.join(out).rstrip() + '\n'
    return new_head + (sep + peers if sep else '')


def migrate():
    path = conf_path()
    original = path.read_text(errors='replace')
    existing = parse_interface(original)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup = BACKUP_DIR / f'awg0-pre-31-{stamp}.conf'
    backup.write_text(original)

    values = dict(PARAMS)
    values['ListenPort'] = existing.get('ListenPort', '1234')
    values['MTU'] = existing.get('MTU', '1280')
    values['HeaderProtectionKey'] = existing.get('HeaderProtectionKey') or genkey()

    candidate = set_interface_params(original, values)
    path.write_text(candidate)
    restart = run('systemctl', 'restart', 'awg-quick@awg0')
    if restart.returncode:
        path.write_text(original)
        run('systemctl', 'restart', 'awg-quick@awg0')
        raise RuntimeError('AWG 3.1 migration was rejected; original config restored.\n' + (restart.stderr or restart.stdout).strip())

    if run('awg', 'show', 'awg0').returncode:
        path.write_text(original)
        run('systemctl', 'restart', 'awg-quick@awg0')
        raise RuntimeError('awg0 did not come back after migration; original config restored.')
    return path, backup, values


def check():
    path = conf_path()
    cfg = parse_interface(path.read_text(errors='replace'))
    required = ['HeaderProtectionKey', 'Jc', 'Jmin', 'Jmax', 'S1', 'S2', 'S3', 'S4', 'H1', 'H2', 'H3', 'H4', 'RandomTrailers']
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise RuntimeError('Missing AWG 3.1 parameters: ' + ', '.join(missing))
    if cfg.get('RandomTrailers', '').lower() != 'on':
        raise RuntimeError('RandomTrailers must be on for the NOVA 3.1 profile')
    if len({cfg[k] for k in ('S1', 'S2', 'S3', 'S4')}) != 1:
        raise RuntimeError('S1-S4 must match for the NOVA RandomTrailers profile')
    if any(int(cfg[k]) < 12 for k in ('S1', 'S2', 'S3', 'S4')):
        raise RuntimeError('S1-S4 must be >= 12 when HeaderProtectionKey is enabled')
    show = run('awg', 'show', 'awg0')
    if show.returncode:
        raise RuntimeError('awg show awg0 failed')
    live = show.stdout.lower()
    for key in ('jc:', 'jmin:', 'jmax:', 's1:', 's2:', 's3:', 's4:', 'random trailers:'):
        if key not in live:
            raise RuntimeError(f'Live awg0 output does not expose {key}')
    return cfg


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        check()
        print('NOVA AWG 3.1 check: PASS')
    else:
        path, backup, values = migrate()
        check()
        print('NOVA AWG 3.1 migration: PASS')
        print(f'Config: {path}')
        print(f'Backup: {backup}')
        print('HeaderProtectionKey: present')
        print('RandomTrailers: on')
        print('S1/S2/S3/S4: ' + '/'.join(values[k] for k in ('S1', 'S2', 'S3', 'S4')))
