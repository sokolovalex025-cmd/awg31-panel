#!/usr/bin/env python3
"""Runtime bootstrap for a clean NOVA installation."""
from pathlib import Path
import sqlite3

BASE=Path('/opt/awg31-panel')
DB=BASE/'panel.db'

DB.parent.mkdir(parents=True,exist_ok=True)
con=sqlite3.connect(DB)
con.execute('CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)')
con.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, address TEXT NOT NULL, private_key TEXT NOT NULL, public_key TEXT NOT NULL, psk TEXT NOT NULL, created INTEGER NOT NULL)')
con.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')")
con.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('password','change-me')")
con.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('endpoint','')")
con.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('dns','10.66.66.1')")
con.commit(); con.close()

import nova11
nova11.core.app.run(host='0.0.0.0',port=8080)
