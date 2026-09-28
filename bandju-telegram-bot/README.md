# Bandju Telegram Bot

Telegram bot integration for Bandju Panel 1.9.x.

## Current Bandju 1.9.0 integration

The bot uses Bandju's local HTTP API at `http://127.0.0.1:7777`.

Confirmed routes used by this bot:
- `GET /api/health`
- `GET /api/status`
- `GET /api/amneziawg/clients`
- `POST /api/amneziawg/clients`
- `POST /api/amneziawg/clients/<client_name>/toggle`
- `DELETE /api/amneziawg/clients/<client_name>`

The bot does not modify Bandju's Docker/Xray/AWG files directly.

## Safe mode

Default: `BANDJU_MUTATIONS_ENABLED=0`.

Safe mode permits health/status and reading an associated client. Creation, enable/disable and deletion remain blocked.

Set `BANDJU_MUTATIONS_ENABLED=1` only after the VPS API checks pass. Renewal remains disabled because a confirmed Bandju 1.9.0 AmneziaWG renewal endpoint has not been identified.

## Installation

On the Bandju VPS:

```bash
cd /path/to/awg31-panel/bandju-telegram-bot
sudo bash install.sh
sudo nano /etc/bandju-telegram-bot/.env
```

Minimum configuration:

```env
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_ADMIN_IDS=YOUR_TELEGRAM_ID
BANDJU_API_BASE=http://127.0.0.1:7777
BANDJU_MUTATIONS_ENABLED=0
```

Then:

```bash
sudo bandju-telegram-bot-api-check
sudo systemctl enable --now bandju-telegram-bot
sudo systemctl status bandju-telegram-bot --no-pager
```

After code updates, rerun `install.sh` and:

```bash
sudo systemctl restart bandju-telegram-bot
```

## Live test

1. Install in safe mode.
2. Run `bandju-telegram-bot-api-check`.
3. Start the bot and use `/health`.
4. Only after that, set `BANDJU_MUTATIONS_ENABLED=1`.
5. Create one disposable Telegram test client.
6. Verify it appears in Bandju.
7. Test enable/disable.
8. Test deletion.
9. Check logs after each mutation.

Keep Bandju port 7777 local-only. Never put the Telegram token in GitHub.

## Logs

```bash
sudo journalctl -u bandju-telegram-bot -n 100 --no-pager
sudo systemctl status bandju-telegram-bot --no-pager
```
