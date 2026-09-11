#!/usr/bin/env python3
"""AWG Panel security hardening: login throttling, audit trail and HTTP headers."""
from collections import defaultdict, deque
from pathlib import Path
import sqlite3
import time

BASE = Path('/opt/awg31-panel')
DB = BASE / 'panel.db'
WINDOW = 600
MAX_FAILURES = 8
_BUCKETS = defaultdict(deque)


def _db():
    c = sqlite3.connect(DB)
    c.execute('''CREATE TABLE IF NOT EXISTS security_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts INTEGER NOT NULL,
        ip TEXT NOT NULL,
        event TEXT NOT NULL,
        detail TEXT DEFAULT ''
    )''')
    c.commit()
    return c


def _audit(ip, event, detail=''):
    try:
        c = _db()
        c.execute('INSERT INTO security_audit(ts,ip,event,detail) VALUES(?,?,?,?)',
                  (int(time.time()), ip[:80], event[:80], detail[:500]))
        c.commit()
        c.close()
    except Exception:
        pass


def _ip(request):
    # Do not trust X-Forwarded-For: the panel is intended to sit behind a
    # trusted local/reverse-proxy setup only when explicitly configured there.
    return request.remote_addr or 'unknown'


def register(app):
    if getattr(app, '_security_hardening_93', False):
        return

    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config.setdefault('SESSION_COOKIE_SECURE', False)  # panel may run on HTTP:8080
    app.config.setdefault('PERMANENT_SESSION_LIFETIME', 3600)

    try:
        _db().close()
    except Exception:
        pass

    @app.before_request
    def _security_before():
        if request.path == '/login' and request.method == 'POST':
            ip = _ip(request)
            now = time.time()
            q = _BUCKETS[ip]
            while q and now - q[0] > WINDOW:
                q.popleft()
            if len(q) >= MAX_FAILURES:
                _audit(ip, 'login_blocked', 'rate limit')
                from flask import abort
                abort(429, description='Слишком много попыток входа. Повторите позже.')

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if request.path != '/login':
            response.headers.setdefault('Cache-Control', 'no-store')
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    original_login = app.view_functions.get('login')
    if original_login:
        def secure_login(*args, **kwargs):
            from flask import request, session
            ip = _ip(request)
            if request.method == 'POST':
                now = time.time()
                q = _BUCKETS[ip]
                while q and now - q[0] > WINDOW:
                    q.popleft()
                result = original_login(*args, **kwargs)
                if session.get('logged'):
                    q.clear()
                    _audit(ip, 'login_success')
                else:
                    q.append(now)
                    _audit(ip, 'login_failed')
                return result
            return original_login(*args, **kwargs)
        app.view_functions['login'] = secure_login

    original_logout = app.view_functions.get('logout')
    if original_logout:
        def secure_logout(*args, **kwargs):
            _audit(_ip(request), 'logout')
            return original_logout(*args, **kwargs)
        app.view_functions['logout'] = secure_logout

    @app.route('/api/security/status')
    def security_status():
        from flask import jsonify
        c = _db()
        rows = c.execute('SELECT event, COUNT(*) FROM security_audit GROUP BY event').fetchall()
        c.close()
        counts = {r[0]: r[1] for r in rows}
        return jsonify(ok=True, login_throttle=True, max_failures=MAX_FAILURES,
                       window_seconds=WINDOW, audit=True, counts=counts)

    @app.route('/security/audit')
    def security_audit():
        from flask import render_template_string
        c = _db()
        rows = c.execute('SELECT ts,ip,event,detail FROM security_audit ORDER BY id DESC LIMIT 100').fetchall()
        c.close()
        body = render_template_string('''
        <div class=hero><div><div class=eyebrow>SECURITY AUDIT</div><h1>Журнал безопасности</h1><p>Последние события авторизации панели.</p></div></div>
        <div class=card><table><tr><th>Время</th><th>IP</th><th>Событие</th><th>Детали</th></tr>
        {% for r in rows %}<tr><td>{{r[0]|int}}</td><td>{{r[1]}}</td><td>{{r[2]}}</td><td class=muted>{{r[3]}}</td></tr>{% else %}<tr><td colspan=4 class=muted>Событий пока нет</td></tr>{% endfor %}</table></div>
        ''', rows=rows)
        return app.layout('Security Audit', body, '/security/audit') if hasattr(app, 'layout') else body

    # Make the login UI identify the current hardened release without changing
    # the authentication semantics or default credentials.
    app._security_hardening_93 = True
