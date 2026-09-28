# NOVA VPN Telegram Bot

Telegram VPN bot with a simple consumer flow: start → trial/plan → automatic VLESS config → QR code → account.

## Current backend

- Telegram Bot API via aiogram 3
- SQLite
- FastAPI status/admin page
- 3x-ui VLESS backend
- Telegram Stars payments
- Trial period
- QR code delivery

## Install

```bash
git clone https://github.com/sokolovalex025-cmd/awg31-panel.git
cd awg31-panel/nurvpn
bash install.sh
nano /opt/nova-vpn-bot/.env
systemctl restart nova-vpn-bot
journalctl -u nova-vpn-bot -f
```

Required values:

```env
BOT_TOKEN=...
ADMIN_IDS=123456789
XUI_URL=https://127.0.0.1:2053
XUI_USERNAME=admin
XUI_PASSWORD=...
XUI_INBOUND_ID=1
XUI_SUBSCRIPTION_HOST=vpn.example.com
```

The first release intentionally keeps the web service bound to 127.0.0.1. Put it behind nginx/HTTPS if it must be exposed.

## Roadmap

- Multi-server pool and least-loaded node selection
- AmneziaWG 3.1 adapter
- Subscription URL for compatible clients
- Referral system and promo codes
- Full web admin panel
- Automatic expiry/reconciliation and server health monitoring
