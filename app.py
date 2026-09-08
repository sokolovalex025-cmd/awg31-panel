from flask import Flask, request, redirect, session, render_template_string, send_file, jsonify, Response
from pathlib import Path
import base64
import subprocess, sqlite3, secrets, os, re, time, tempfile, shutil, ipaddress, json, struct, zlib

app = Flask(__name__)
app.secret_key = os.environ.get('AWG_PANEL_SECRET', secrets.token_hex(32))
BASE=Path('/opt/awg31-panel'); DB=BASE/'panel.db'
CONF=Path('/etc/amnezia/amneziawg/awg0.conf'); CLIENT_DIR=Path('/etc/amnezia/amneziawg/clients')
WG='awg0'; DEFAULT_PORT=1234

CSS='''<style>''' + '''''' + '''</style>'''
'''
