#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
[ -f "$APP" ] || { echo "Не найден $APP"; exit 1; }
mkdir -p "$BASE/backups"
BACKUP="$BASE/backups/app-before-client-ui-$(date +%Y%m%d-%H%M%S).py"
cp -a "$APP" "$BACKUP"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text(encoding='utf-8')
marker='# === CLIENT UI IMPROVEMENTS V1 ==='
if marker in s:
    print('Client UI improvements already installed.')
    raise SystemExit(0)

# Add a visible Delete button to the existing clients table.
old='<a class=btn href="/clients/{{r.id}}/conf">CONF</a> <a class=btn href="/clients/{{r.id}}/qr">QR</a>'
new='<a class=btn href="/clients/{{r.id}}/conf">CONF</a> <a class="btn qrbtn" href="/clients/{{r.id}}/qr" target="_blank" rel="noopener">QR</a> <form method="post" action="/clients/{{r.id}}/delete" style="display:inline" onsubmit="return confirm(\'Удалить клиента {{r.name}}? Это отключит его конфигурацию.\')"><button type="submit" class="btn" style="background:#a83232">Удалить</button></form>'
if old not in s:
    raise SystemExit('Не найден блок кнопок клиентов в app.py')
s=s.replace(old,new,1)

# Install the delete endpoint and an after_request hook immediately before the main block.
needle="if __name__=='__main__':app.run(host='0.0.0.0',port=8080)"
if needle not in s:
    raise SystemExit('Не найден блок запуска Flask в app.py')

extra=r'''# === CLIENT UI IMPROVEMENTS V1 ===
@app.after_request
def _client_qr_inline(response):
    # Browser should open QR in a new tab instead of downloading it.
    if re.fullmatch(r'/clients/\d+/qr', request.path) and response.mimetype == 'image/png':
        cid=request.path.rsplit('/',2)[1]
        response.headers['Content-Disposition']=f'inline; filename="client-{cid}.png"'
    return response

@app.route('/clients/<int:cid>/delete',methods=['POST'])
def _client_delete(cid):
    c=db(); row=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone()
    if not row:
        c.close(); return Response("<script>alert('Клиент не найден.');location='/clients'</script>",status=404)
    pub=(row['public_key'] or '').strip()
    old=CONF.read_text() if CONF.exists() else ''
    bak=CONF.with_name(CONF.name+'.bak-delete-'+time.strftime('%Y%m%d-%H%M%S'))
    try:
        if CONF.exists(): bak.write_text(old); bak.chmod(0o600)
        lines=old.splitlines()
        blocks=[]; cur=[]
        for line in lines:
            if line.strip() == '[Peer]':
                if cur: blocks.append(cur)
                cur=[line]
            else:
                cur.append(line)
        if cur: blocks.append(cur)
        kept=[]; removed=False
        for block in blocks:
            b='\n'.join(block)
            if re.search(r'^\s*PublicKey\s*=\s*'+re.escape(pub)+r'\s*$', b, re.M):
                removed=True
                continue
            kept.append(block)
        if not removed:
            raise RuntimeError('Peer клиента не найден в конфигурации AWG.')
        new='\n'.join('\n'.join(b).rstrip() for b in kept if b) + '\n'
        CONF.write_text(new); CONF.chmod(0o600)
        if cmd('awg-quick','strip','awg0').returncode != 0:
            raise RuntimeError('Новая конфигурация AWG не прошла проверку.')
        rr=cmd('systemctl','restart','awg-quick@awg0')
        if rr.returncode:
            raise RuntimeError((rr.stderr or rr.stdout or 'AWG не запустился').strip())
        c.execute('DELETE FROM clients WHERE id=?',(cid,)); c.commit(); c.close()
        try: bak.unlink()
        except Exception: pass
        return redirect('/clients')
    except Exception as e:
        try:
            if CONF.exists(): CONF.write_text(old); CONF.chmod(0o600)
            cmd('systemctl','restart','awg-quick@awg0')
        except Exception: pass
        c.rollback(); c.close()
        return Response(f"<script>alert({e!r});location='/clients'</script>",status=500)
'''
s=s.replace(needle,extra+'\n'+needle,1)
p.write_text(s,encoding='utf-8')
PY
"$BASE/venv/bin/python" -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
if ! systemctl is-active --quiet awgpanel; then
  echo 'ОШИБКА: awgpanel не запустилась. Восстанавливаю backup.'
  cp -a "$BACKUP" "$APP"
  systemctl restart awgpanel
  exit 1
fi
echo '=== CLIENT UI IMPROVEMENTS INSTALLED ==='
echo "Backup: $BACKUP"
echo 'QR: opens inline in a new tab.'
echo 'Clients: Delete button added.'
