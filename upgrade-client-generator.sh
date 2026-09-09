#!/usr/bin/env bash
set -Eeuo pipefail

# AWG Panel 8.1 -> Client Generator v2
# Patches the running Flask app without replacing the rest of app.py.
# The new generator derives the client profile from the live server config.

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
APP="$BASE/app.py"
BACKUP="$BASE/backups/app-before-client-generator-$(date +%Y%m%d-%H%M%S).py"

[ -f "$APP" ] || { echo "Не найден $APP"; exit 1; }
mkdir -p "$BASE/backups"
cp -a "$APP" "$BACKUP"

python3 - "$APP" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text(encoding='utf-8')

if 'AWG CLIENT GENERATOR V2' in s:
    print('Client Generator v2 уже установлен.')
    raise SystemExit(0)

patch=r'''

# === AWG CLIENT GENERATOR V2 ===
# Generates client profiles from the actual live AWG 3.1 server configuration.
def _awg_cfg_full():
    out=[]
    if CONF.exists():
        for line in CONF.read_text(errors='replace').splitlines():
            st=line.strip()
            if st.startswith('[Peer]'):
                break
            if '=' in st and not st.startswith('#'):
                k,v=st.split('=',1); out.append((k.strip(),v.strip()))
    return dict(out)

def _awg_server_public_key():
    r=cmd('awg','show','awg0','public-key')
    if r.returncode==0 and r.stdout.strip():
        return r.stdout.strip()
    c=_awg_cfg_full(); priv=c.get('PrivateKey','')
    if priv:
        r=subprocess.run(['awg','pubkey'],input=priv+'\n',text=True,capture_output=True,timeout=10)
        if r.returncode==0:return r.stdout.strip()
    raise RuntimeError('Не удалось получить публичный ключ сервера AWG.')

def _awg_endpoint():
    explicit=(setting('endpoint','') or '').strip()
    if explicit:
        host=explicit
    else:
        host=''
        try:
            r=cmd('curl','-4','-fsS','--max-time','4','https://api.ipify.org')
            if r.returncode==0: host=r.stdout.strip()
        except Exception: pass
        if not host:
            r=cmd('bash','-lc',"ip -4 route get 1.1.1.1 2>/dev/null | awk 'NR==1{for(i=1;i<=NF;i++)if($i==\"src\"){print $(i+1);exit}}'")
            host=r.stdout.strip()
        if not host:
            raise RuntimeError('Не удалось определить внешний IPv4. Укажите Endpoint в Настройках панели.')
    if host.startswith('['):
        return host
    return host

def _awg_client_config(row):
    c=_awg_cfg_full()
    port=c.get('ListenPort','443')
    server_pub=_awg_server_public_key()
    endpoint=_awg_endpoint()
    if ':' in endpoint and not endpoint.replace(':','').isdigit() and not endpoint.startswith('['):
        # Domain/IPv4 with an accidental port: keep it only when it is already numeric.
        pass
    if ':' in endpoint and endpoint.count(':')>1 and not endpoint.startswith('['):
        endpoint='['+endpoint+']'
    if endpoint.startswith('['): ep=f'{endpoint}:{port}'
    elif endpoint.rsplit(':',1)[-1].isdigit() and endpoint.count(':')==1: ep=endpoint
    else: ep=f'{endpoint}:{port}'

    lines=['[Interface]',f'PrivateKey = {row["private_key"]}',f'Address = {row["address"]}','DNS = 1.1.1.1']
    # Copy supported AWG 3.1 transport/obfuscation parameters exactly from server.
    skip={'Address','PrivateKey','ListenPort','PostUp','PostDown','Table','SaveConfig'}
    for k,v in c.items():
        if k not in skip:
            lines.append(f'{k} = {v}')
    lines += ['', '[Peer]', f'PublicKey = {server_pub}', f'PresharedKey = {row["psk"]}', 'AllowedIPs = 0.0.0.0/0, ::/0', f'Endpoint = {ep}', 'PersistentKeepalive = 25', '']
    return '\n'.join(lines)

def _awg_validate_client(text):
    import tempfile
    fd,path=tempfile.mkstemp(prefix='awg-client-',suffix='.conf')
    os.close(fd)
    try:
        Path(path).write_text(text,encoding='utf-8')
        r=cmd('awg-quick','strip',path)
        if r.returncode!=0:
            raise RuntimeError('Клиентский конфиг AWG не прошёл проверку: '+(r.stderr or r.stdout or 'unknown error'))
    finally:
        try:os.unlink(path)
        except OSError:pass

def _awg_install_peer(row):
    old=CONF.read_text() if CONF.exists() else ''
    if not old: raise RuntimeError('Конфигурация AWG сервера не найдена.')
    peer='\n[Peer]\n# Client = '+row['name']+'\nPublicKey = '+row['public_key']+'\nPresharedKey = '+row['psk']+'\nAllowedIPs = '+row['address']+'\n'
    # Avoid duplicate public keys.
    if re.search(r'^PublicKey\s*=\s*'+re.escape(row['public_key'])+r'\s*$',old,re.M):
        return old
    new=old.rstrip()+peer+'\n'
    bak=CONF.with_name(CONF.name+'.bak-generator-v2-'+time.strftime('%Y%m%d-%H%M%S'))
    bak.write_text(old); bak.chmod(0o600)
    CONF.write_text(new); CONF.chmod(0o600)
    if cmd('awg-quick','strip','awg0').returncode!=0:
        CONF.write_text(old); CONF.chmod(0o600)
        raise RuntimeError('Серверная конфигурация не прошла awg-quick validation; изменения отменены.')
    r=cmd('systemctl','restart','awg-quick@awg0')
    if r.returncode!=0 or not online():
        CONF.write_text(old); CONF.chmod(0o600)
        cmd('systemctl','restart','awg-quick@awg0')
        raise RuntimeError('AWG не запустился после добавления клиента; конфигурация восстановлена.')
    return old

def _generator_create_client():
    name=request.form.get('name','').strip()
    if not name:return 'Имя клиента обязательно',400
    c=db()
    try:
        if c.execute('SELECT 1 FROM clients WHERE name=?',(name,)).fetchone():
            return Response("<script>alert('Клиент с таким именем уже существует.');location='/clients'</script>",status=409)
        used=set()
        for r in c.execute('SELECT address FROM clients'):
            m=re.search(r'10\\.66\\.66\\.(\\d+)',r['address'] or '')
            if m: used.add(int(m.group(1)))
        addr=next((f'10.66.66.{n}/32' for n in range(2,255) if n not in used),None)
        if not addr:return 'Нет свободных адресов',500
        priv=cmd('awg','genkey').stdout.strip()
        r=subprocess.run(['awg','pubkey'],input=priv+'\n',text=True,capture_output=True,timeout=10)
        pub=r.stdout.strip() if r.returncode==0 else ''
        psk=cmd('awg','genpsk').stdout.strip()
        if not priv or not pub or not psk:return 'Не удалось сгенерировать ключи AWG',500
        row={'name':name,'address':addr,'private_key':priv,'public_key':pub,'psk':psk}
        client_text=_awg_client_config(row)
        _awg_validate_client(client_text)
        old=_awg_install_peer(row)
        try:
            c.execute('INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)',(name,addr,priv,pub,psk,int(time.time())))
            c.commit()
        except Exception:
            CONF.write_text(old); CONF.chmod(0o600); cmd('systemctl','restart','awg-quick@awg0'); raise
    except Exception as e:
        c.rollback()
        return 'Ошибка генератора: '+str(e),500
    finally:
        c.close()
    return redirect('/clients')

def _generator_conf(cid):
    c=db(); row=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone(); c.close()
    if not row:return 'Клиент не найден',404
    text=_awg_client_config(row)
    _awg_validate_client(text)
    return Response(text, mimetype='text/plain', headers={'Content-Disposition':f'attachment; filename="{row["name"]}.conf"'})

def _generator_qr(cid):
    c=db(); row=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone(); c.close()
    if not row:return 'Клиент не найден',404
    text=_awg_client_config(row); _awg_validate_client(text)
    img=qrcode.make(text); bio=io.BytesIO(); img.save(bio,format='PNG'); bio.seek(0)
    return send_file(bio,mimetype='image/png',download_name=f'{row["name"]}.png',as_attachment=True)

def _install_generator_v2_routes():
    # Replace existing endpoint functions after all original routes are registered.
    app.view_functions['create_client']=_generator_create_client
    for rule in list(app.url_map.iter_rules()):
        path=str(rule)
        if path.startswith('/clients/') and path.endswith('/conf'):
            app.view_functions[rule.endpoint]=_generator_conf
        elif path.startswith('/clients/') and path.endswith('/qr'):
            app.view_functions[rule.endpoint]=_generator_qr

_install_generator_v2_routes()
# === END AWG CLIENT GENERATOR V2 ===
'''

marker="if __name__=='__main__':"
if marker not in s:
    marker='if __name__ == "__main__":'
if marker not in s:
    raise SystemExit('Не найден блок запуска Flask-приложения.')

s=s.replace(marker,patch+'\n'+marker,1)
p.write_text(s,encoding='utf-8')
PY

"$BASE/venv/bin/python" -m py_compile "$APP"
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel || { echo 'ОШИБКА: awgpanel не запустилась. Восстанавливаю backup.'; cp -a "$BACKUP" "$APP"; systemctl restart awgpanel; exit 1; }

echo '=== CLIENT GENERATOR V2 INSTALLED ==='
echo "Backup: $BACKUP"
echo 'Порт и AWG 3.1 параметры теперь берутся из живого awg0.conf.'
echo 'Endpoint: panel setting -> public IPv4 -> default route source IP.'
echo 'Client config и QR проходят awg-quick validation.'
