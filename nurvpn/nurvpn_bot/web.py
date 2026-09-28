from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from .config import settings
from .db import DB

app = FastAPI(title="NOVA VPN Bot Admin", version="1.0.0")
db = DB(settings.db_path)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    with db.connect() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        subs = c.execute("SELECT COUNT(*) n FROM subscriptions WHERE active=1").fetchone()["n"]
    return f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA VPN</title>
<style>body{{font-family:system-ui;background:#0b1020;color:#fff;margin:0;padding:30px}}.card{{max-width:700px;margin:auto;background:#141b31;border-radius:18px;padding:24px}}.n{{font-size:34px;font-weight:700}}.muted{{color:#aab3ca}}</style></head>
<body><div class="card"><h1>🛡 NOVA VPN</h1><p class="muted">Telegram VPN Bot</p><hr><p>Пользователи</p><div class="n">{users}</div><p>Активные подписки</p><div class="n">{subs}</div></div></body></html>"""

@app.get("/api/stats")
async def stats():
    with db.connect() as c:
        return {"users": c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"], "active_subscriptions": c.execute("SELECT COUNT(*) n FROM subscriptions WHERE active=1").fetchone()["n"], "payments": c.execute("SELECT COUNT(*) n FROM payments").fetchone()["n"]}
