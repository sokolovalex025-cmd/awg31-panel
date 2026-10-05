import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

class DB:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    def init(self):
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              telegram_id INTEGER UNIQUE NOT NULL,
              username TEXT,
              first_name TEXT,
              created_at TEXT NOT NULL,
              trial_used INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              telegram_id INTEGER NOT NULL,
              client_uuid TEXT UNIQUE NOT NULL,
              email TEXT NOT NULL,
              protocol TEXT NOT NULL DEFAULT 'vless',
              config TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              active INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
            );
            CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(telegram_id);
            CREATE TABLE IF NOT EXISTS payments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              telegram_id INTEGER NOT NULL,
              plan_days INTEGER NOT NULL,
              stars INTEGER NOT NULL,
              telegram_charge_id TEXT UNIQUE,
              created_at TEXT NOT NULL
            );
            """)

    def upsert_user(self, tg):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as c:
            c.execute("""INSERT INTO users(telegram_id,username,first_name,created_at)
                         VALUES(?,?,?,?)
                         ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name""",
                      (tg.id, tg.username, tg.first_name, now))

    def get_user(self, telegram_id):
        with self.connect() as c:
            return c.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)).fetchone()

    def mark_trial(self, telegram_id):
        with self.connect() as c:
            c.execute("UPDATE users SET trial_used=1 WHERE telegram_id=?", (telegram_id,))

    def trial_used(self, telegram_id):
        row = self.get_user(telegram_id)
        return bool(row and row["trial_used"])

    def add_subscription(self, telegram_id, client_uuid, email, config, expires_at, protocol="vless"):
        with self.connect() as c:
            c.execute("INSERT INTO subscriptions(telegram_id,client_uuid,email,protocol,config,expires_at,created_at) VALUES(?,?,?,?,?,?,?)",
                      (telegram_id, client_uuid, email, protocol, config, expires_at, datetime.now(timezone.utc).isoformat()))

    def extend(self, telegram_id, days):
        with self.connect() as c:
            row = c.execute("SELECT * FROM subscriptions WHERE telegram_id=? AND active=1 ORDER BY expires_at DESC LIMIT 1", (telegram_id,)).fetchone()
            now = datetime.now(timezone.utc)
            if row:
                current = datetime.fromisoformat(row["expires_at"])
                exp = max(current, now) + timedelta(days=days)
                c.execute("UPDATE subscriptions SET expires_at=? WHERE id=?", (exp.isoformat(), row["id"]))
                return exp
            return None

    def latest_subscription(self, telegram_id):
        with self.connect() as c:
            return c.execute("SELECT * FROM subscriptions WHERE telegram_id=? AND active=1 ORDER BY expires_at DESC LIMIT 1", (telegram_id,)).fetchone()

    def add_payment(self, telegram_id, days, stars, charge_id):
        with self.connect() as c:
            c.execute("INSERT OR IGNORE INTO payments(telegram_id,plan_days,stars,telegram_charge_id,created_at) VALUES(?,?,?,?,?)",
                      (telegram_id, days, stars, charge_id, datetime.now(timezone.utc).isoformat()))
