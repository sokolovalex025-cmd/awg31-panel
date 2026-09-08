#!/usr/bin/env python3
"""Adds the Sweden 🇸🇪 marker to generated AWG client configurations."""

def register(app):
    try:
        import app as main
        if getattr(main, '_sweden_flag_patched', False):
            return app
        original = main.client_config
        def client_config(r):
            return '# 🇸🇪 Sweden\n' + original(r)
        main.client_config = client_config
        main._sweden_flag_patched = True
    except Exception:
        pass
    return app
