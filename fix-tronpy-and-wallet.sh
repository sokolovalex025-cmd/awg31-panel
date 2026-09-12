#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/awg31-panel
VENV="$BASE/venv"
ENV_FILE=/etc/awg31-panel/telegram.env
WALLET_FILE=/etc/awg31-panel/usdt-wallet.env

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "ERROR: $VENV/bin/python not found. Install the NOVA panel first."
  exit 1
fi

PYVER="$($VENV/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYMAJOR="${PYVER%%.*}"
PYMINOR="${PYVER##*.}"
if (( PYMAJOR < 3 || (PYMAJOR == 3 && PYMINOR < 8) )); then
  echo "ERROR: Python $PYVER is too old for current tronpy. Python 3.8+ is required."
  echo "Current interpreter: $VENV/bin/python"
  exit 2
fi

echo "== NOVA / TRON SETUP =="
echo "Python: $PYVER"

"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV/bin/python" -m pip install --upgrade tronpy

"$VENV/bin/python" - <<'PY'
import tronpy
print('tronpy OK:', getattr(tronpy, '__version__', 'installed'))
PY

install -d -m 700 /etc/awg31-panel

if [[ ! -f "$WALLET_FILE" ]]; then
  umask 077
  "$VENV/bin/python" - <<'PY'
from pathlib import Path
from tronpy.keys import PrivateKey

out = Path('/etc/awg31-panel/usdt-wallet.env')
key = PrivateKey.random()
address = key.public_key.to_base58check_address()
private_key = key.hex()
out.write_text(
    '# NOVA USDT TRC20 wallet - KEEP THIS FILE PRIVATE\n'
    'CRYPTO_NETWORK=USDT TRC20\n'
    f'CRYPTO_WALLET_ADDRESS={address}\n'
    f'CRYPTO_WALLET_PRIVATE_KEY={private_key}\n'
)
out.chmod(0o600)
print('Wallet created successfully.')
print('Network: USDT TRC20')
print('Address:', address)
print('Private key: stored only in /etc/awg31-panel/usdt-wallet.env')
PY
else
  chmod 600 "$WALLET_FILE"
  echo "Wallet already exists; it was NOT replaced."
  "$VENV/bin/python" - <<'PY'
from pathlib import Path
p=Path('/etc/awg31-panel/usdt-wallet.env')
vals={}
for line in p.read_text(errors='replace').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        k,v=line.split('=',1); vals[k]=v.strip()
print('Network:', vals.get('CRYPTO_NETWORK','USDT TRC20'))
print('Address:', vals.get('CRYPTO_WALLET_ADDRESS','not set'))
PY
fi

# Add the public address/network to the bot environment without touching secrets already present.
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
ADDRESS="$($VENV/bin/python -c "from pathlib import Path; p=Path('$WALLET_FILE'); print([x.split('=',1)[1].strip() for x in p.read_text().splitlines() if x.startswith('CRYPTO_WALLET_ADDRESS=')][0])")"
if grep -q '^CRYPTO_WALLET_ADDRESS=' "$ENV_FILE"; then
  sed -i "s#^CRYPTO_WALLET_ADDRESS=.*#CRYPTO_WALLET_ADDRESS=$ADDRESS#" "$ENV_FILE"
else
  printf '\nCRYPTO_NETWORK=USDT TRC20\nCRYPTO_WALLET_ADDRESS=%s\n' "$ADDRESS" >> "$ENV_FILE"
fi

chmod 600 "$ENV_FILE" "$WALLET_FILE"

echo
echo "DONE. Public USDT TRC20 address: $ADDRESS"
echo "Private key is stored only in: $WALLET_FILE"
echo "IMPORTANT: back up the private key offline before accepting real payments."
