#!/usr/bin/env python3
"""NOVA bridge for the external AWG Toolza CLI.

This bridge is deliberately non-destructive: it only reports whether the
external awg2 command is installed and exposes the pinned install command.
It never launches awg2 from a web request and never edits awg0.conf.
"""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from flask import jsonify

TOOLZA_VERSION = "v0.8.25"
TOOLZA_COMMIT = "ecccafa3094181a6962ff71e54527e4771657698"
TOOLZA_REPO = "https://github.com/pumbaX/awg-multi-script"
TOOLZA_PATH = "/usr/local/bin/awg2"
# Security boundary: the web panel may inspect Toolza, but never execute it.
WEB_EXECUTION_ENABLED = False


def _run_version():
    try:
        p = subprocess.run(
            [TOOLZA_PATH, "--help"],
            capture_output=True, text=True, timeout=4,
        )
        if p.returncode not in (0,):
            return ""
        for line in (p.stdout or "").splitlines():
            if line.startswith("awg2 "):
                return line.strip()
    except Exception:
        pass
    return ""


def status():
    installed = bool(shutil.which("awg2"))
    return {
        "installed": installed,
        "path": TOOLZA_PATH if os.path.exists(TOOLZA_PATH) else None,
        "version": _run_version() if installed else "",
        "expected_version": TOOLZA_VERSION,
        "pinned_commit": TOOLZA_COMMIT,
        "repository": TOOLZA_REPO,
        "install_script": "/opt/awg31-panel/install-awg-toolza.sh",
        "safe_mode": True,
        "web_execution_enabled": WEB_EXECUTION_ENABLED,
    }


def apply(nova):
    app = nova.core.app

    # Read-only bridge by design. No route in this module starts awg2 or passes
    # web-controlled arguments to it. Mutating NOVA operations use the separate
    # localhost daemon with its token + explicit APPLY confirmation.
    @app.route("/api/nova/toolza-external")
    def api_toolza_external():
        return jsonify(status())

    return nova
