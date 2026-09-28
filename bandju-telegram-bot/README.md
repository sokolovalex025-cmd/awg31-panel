# Bandju Telegram Bot

Telegram bot integration for Bandju Panel.

## Safe mode

The bot starts in **read-only mode** by default:

`BANDJU_MUTATIONS_ENABLED=0`

In this mode the bot can:
- check Bandju API health;
- discover OpenAPI routes when available;
- read an existing access associated with a Telegram user.

It cannot create, renew, enable, or disable Bandju access. The safety check is enforced in the bot code, not only by UI.

After the actual Bandju 1.9.0 API routes are verified, set:

`BANDJU_MUTATIONS_ENABLED=1`

and configure explicit endpoint overrides if necessary.

## Architecture

Telegram -> Bot -> Bandju local API (127.0.0.1) -> XRay / AmneziaWG / Hysteria2 / MTProto

The bot is intended to run on the same VPS as Bandju Panel. Bandju's API is local-only, so no panel API port needs to be exposed to the Internet.

## Installation

1. Create a Telegram bot with BotFather and copy its token.
2. On the Bandju VPS run:

```bash
sudo bash install.sh
```

3. Edit:

```bash
sudo nano /etc/bandju-telegram-bot/.env
```

4. Set:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_IDS=123456789
BANDJU_API_BASE=http://127.0.0.1:7777
BANDJU_MUTATIONS_ENABLED=0
```

5. Start:

```bash
sudo systemctl enable --now bandju-telegram-bot
```

6. Check the API safely:

```bash
sudo bandju-telegram-bot-api-check
```

Do not expose port 7777 publicly and never put the Telegram token in Git.

## Important

Bandju API route names can change between releases. The adapter supports discovery and configurable paths. Do not enable mutations until the installed Bandju 1.9.0 routes and request formats have been verified.
