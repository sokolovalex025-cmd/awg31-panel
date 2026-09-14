"""NOVA 16 UI hotfix: remove the legacy sidebar server status card.

This is presentation-only. It does not modify AWG configuration or runtime state.
"""
import re


def apply(nova):
    app = nova.core.app

    @app.after_request
    def _remove_legacy_server_card(response):
        try:
            if response.content_type and response.content_type.startswith('text/html'):
                html = response.get_data(as_text=True)
                cleaned = re.sub(r'<div class=server>.*?</div>', '', html, count=1, flags=re.S)
                if cleaned != html:
                    response.set_data(cleaned)
        except Exception:
            pass
        return response

    return nova
