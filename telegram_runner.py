#!/usr/bin/env python3
"""Run the NOVA Telegram bot using settings saved by the web panel."""
import sqlite3
from pathlib import Path
import telegram_bot

DB = Path('/opt/awg31-panel/panel.db')

def panel_env():
    values = {}
    try:
        con = sqlite3.connect(DB)
        for key, value in con.execute("SELECT k,v FROM settings WHERE k IN ('telegram_token','telegram_admins','telegram_notify','telegram_default_days')"):
            values[key] = value or ''
        con.close()
    except Exception:
        pass
    return values

def env_bridge():
    values = panel_env()
    current = telegram_bot.env()
    if values.get('telegram_token'):
        current['TELEGRAM_BOT_TOKEN'] = values['telegram_token']
    if values.get('telegram_admins'):
        current['TELEGRAM_ADMIN_IDS'] = values['telegram_admins']
    if values.get('telegram_default_days'):
        current['VPN_DEFAULT_DAYS'] = values['telegram_default_days']
    return current

telegram_bot.env = env_bridge
telegram_bot.loop()
