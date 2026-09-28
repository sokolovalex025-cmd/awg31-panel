# Bandju Telegram Bot

Telegram bot integration for Bandju Panel.

## Architecture

Telegram -> Bot -> Bandju local API (127.0.0.1) -> XRay / AmneziaWG / Hysteria2 / MTProto

The bot is intended to run on the same VPS as Bandju Panel. Bandju's API is local-only, so no panel API port needs to be exposed to the Internet.

## Features

- User registration by Telegram ID
- Create an access profile
- Return subscription/link/config data
- Show current access status
- Show traffic and expiry when available
- Renew access
- Disable access
- Admin commands
- Health check
- systemd service
- Secrets stored in /etc/bandju-telegram-bot/.env

## Installation

1. Create a Telegram bot with BotFather and copy its token.
2. On the Bandju VPS run:

```bash
sudo bash install.sh
```

3. Edit:

```
sudo nano /etc/bandju-telegram-bot/.env
```

4. Set:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_IDS=123456789
BANDJU_API_BASE=http://127.0.0.1:7777
```

5. Start:

```sudo systemctl enable --now bandju-telegram-bot```

## Important

Bandju API route names can change between releases. The adapter contains endpoint discovery and configurable paths. If automatic discovery cannot identify the installed 1.9.0 routes, run:

```sudo bandju-telegram-bot-api-check
```

and use the printed routes to set the corresponding variables in .env.

Do not expose port 7777 publicly.
