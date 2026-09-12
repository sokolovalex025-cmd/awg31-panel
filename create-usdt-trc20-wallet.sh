#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
BASE=/opt/awg31-panel
OUT=/etc/awg31-panel/usdt-wallet.env
mkdir -p /etc/awg31-panel
python3 -m pip install -q --disable-pip-version-check tronpy >/dev/null 2>&1 || true
python3 - <<'PY'
from pathlib import Path
import secrets, os
try:
    from tronpy.keys import PrivateKey
except Exception as e:
    raise SystemExit('tronpy installation failed: '+str(e))
path=Path('/etc/awg31-panel/usdt-wallet.env')
if path.exists():
    print('Wallet already exists:', path)
    raise SystemExit(0)
key=PrivateKey(secrets.token_bytes(32))
addr=key.public_key.to_base58check_address()
priv=key.hex()
path.write_text(f'# NOVA USDT TRC20 receiving wallet\nUSDT_NETWORK=TRC20\nUSDT_ADDRESS={addr}\nUSDT_PRIVATE_KEY={priv}\n')
os.chmod(path,0o600)
print('USDT TRC20 wallet created.')
print('Address:', addr)
print('Private key saved ONLY on VPS:', path)
print('BACK UP THE PRIVATE KEY SECURELY. NEVER PUT IT IN GITHUB OR TELEGRAM.')
PY
