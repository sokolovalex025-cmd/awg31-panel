#!/usr/bin/env bash
set -euo pipefail
BASE=/opt/awg31-panel
APP="$BASE/app.py"
BACKUP="$APP.bak-balancer-$(date +%Y%m%d-%H%M%S)"
TOKEN_FILE=/etc/awg31-panel/balancer.env

[ -f "$APP" ] || { echo "app.py not found: $APP"; exit 1; }
cp -a "$APP" "$BACKUP"
install -d -m 700 /etc/awg31-panel
if [ ! -f "$TOKEN_FILE" ]; then
  TOKEN=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)
  printf 'BALANCER_TOKEN=%s\n' "$TOKEN" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
fi

python3 - <<'PY'
from pathlib import Path
import re
p=Path('/opt/awg31-panel/app.py')
s=p.read_text()
# Load balancer after all route/function definitions, before app.run.
if 'import balancer as _nova_balancer' not in s:
    marker="if __name__=='__main__':app.run(host='0.0.0.0',port=8080)"
    if marker not in s:
        raise SystemExit('Cannot find app.run marker')
    s=s.replace(marker,"import balancer as _nova_balancer\n\n"+marker,1)
# Add navigation item once.
if "('⚖','Балансировка','/balancer')" not in s:
    needle="('☷','Логи','/logs')])"
    if needle not in s: raise SystemExit('Cannot find navigation marker')
    s=s.replace(needle,"('☷','Логи','/logs'),('⚖','Балансировка','/balancer')])",1)
# Replace client creation with cluster-aware allocation.
start=s.index("@app.route('/clients/create',methods=['POST'])")
end=s.index("@app.route('/clients/<int:cid>/delete',methods=['POST'])", start)
new_create=r'''@app.route('/clients/create',methods=['POST'])
def create_client():
 name=request.form.get('name','').strip(); c=db()
 if not name:c.close();return 'Имя клиента обязательно',400
 if c.execute('SELECT 1 FROM clients WHERE name=?',(name,)).fetchone():c.close();return Response("<script>alert('Клиент с таким именем уже существует.');location='/clients'</script>",status=409)
 used={int(m.group(1)) for r in c.execute('SELECT address FROM clients') for m in [re.search(r'10\.66\.66\.(\d+)',r['address'] or '')] if m};addr=next((f'10.66.66.{n}/32' for n in range(2,255) if n not in used),None)
 if not addr:c.close();return 'Нет свободных адресов',500
 priv=cmd('awg','genkey').stdout.strip();pub=cmd('bash','-lc',f"printf '%s' '{priv}' | awg pubkey").stdout.strip();psk=cmd('awg','genpsk').stdout.strip()
 if not priv or not pub or not psk:c.close();return 'Не удалось сгенерировать ключи AWG',500
 node=None
 try:
  from balancer import choose_node, node_add_client
  node=choose_node()
  if node and not node_add_client(node, pub, psk, addr):
   c.close(); return 'Выбранный AWG узел не принял нового клиента.',502
 except Exception:
  node=None
 if node:
  c.execute('INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)',(name,addr,priv,pub,psk,int(time.time())));cid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  c.execute('INSERT OR REPLACE INTO balancer_assignments(client_id,node_id) VALUES(?,?)',(cid,node['id']));c.commit();c.close();return redirect('/clients')
 c.execute('INSERT INTO clients(name,address,private_key,public_key,psk,created) VALUES(?,?,?,?,?,?)',(name,addr,priv,pub,psk,int(time.time())));c.commit();c.close()
 old=CONF.read_text() if CONF.exists() else '';bak=CONF.with_name(CONF.name+'.bak-client-'+time.strftime('%Y%m%d-%H%M%S'))
 if CONF.exists():bak.write_text(old)
 CONF.write_text(old.rstrip()+f'\n\n[Peer]\nPublicKey = {pub}\nPresharedKey = {psk}\nAllowedIPs = {addr}\n')
 r=cmd('systemctl','restart','awg-quick@awg0')
 if r.returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'AWG не принял клиента; конфиг восстановлен.',500
 return redirect('/clients')

'''
s=s[:start]+new_create+s[end:]
# Replace deletion so assigned remote peers are removed from their node.
start=s.index("@app.route('/clients/<int:cid>/delete',methods=['POST'])")
end=s.index("def server_public():", start)
new_delete=r'''@app.route('/clients/<int:cid>/delete',methods=['POST'])
def delete_client(cid):
 c=db();r=c.execute('SELECT * FROM clients WHERE id=?',(cid,)).fetchone();a=c.execute('SELECT * FROM balancer_assignments WHERE client_id=?',(cid,)).fetchone();c.close()
 if not r:return 'Not found',404
 if a:
  try:
   from balancer import node_delete_client, node_by_id
   n=node_by_id(a['node_id'])
   if n and not node_delete_client(n, r['public_key']): return 'Удалённый AWG узел не подтвердил удаление.',502
  except Exception: return 'Не удалось связаться с AWG узлом.',502
  c=db();c.execute('DELETE FROM balancer_assignments WHERE client_id=?',(cid,));c.execute('DELETE FROM clients WHERE id=?',(cid,));c.commit();c.close();return redirect('/clients')
 old=CONF.read_text() if CONF.exists() else '';bak=CONF.with_name(CONF.name+'.bak-delete-'+time.strftime('%Y%m%d-%H%M%S'))
 if CONF.exists():bak.write_text(old)
 if CONF.exists():
  parts=old.split('[Peer]'); head=parts[0]; kept=[x for x in parts[1:] if f"PublicKey = {r['public_key']}" not in x]
  CONF.write_text(head+''.join('[Peer]'+x for x in kept))
  if cmd('systemctl','restart','awg-quick@awg0').returncode:CONF.write_text(old);cmd('systemctl','restart','awg-quick@awg0');return 'Не удалось применить удаление.',500
 c=db();c.execute('DELETE FROM clients WHERE id=?',(cid,));c.commit();c.close();return redirect('/clients')

'''
s=s[:start]+new_delete+s[end:]
# Make generated client configs use the assigned node's endpoint/public key.
old="def client_config(r):\n it=cfg();ep=setting('endpoint','') or (cmd('hostname','-I').stdout.split() or ['SERVER_IP'])[0]\n dns=setting('dns','10.66.66.1')"
new="def client_config(r):\n it=cfg();ep=setting('endpoint','') or (cmd('hostname','-I').stdout.split() or ['SERVER_IP'])[0]; server_pub=server_public()\n try:\n  from balancer import node_for_client, node_info\n  n=node_for_client(r['id'])\n  if n:\n   ep=n['host']; info=node_info(n)\n   if info.get('public_key'): server_pub=info['public_key']\n except Exception: pass\n dns=setting('dns','10.66.66.1')"
if old not in s: raise SystemExit('Cannot find client_config marker')
s=s.replace(old,new,1).replace("f'PublicKey = {server_public()}'","f'PublicKey = {server_pub}'",1)
p.write_text(s)
PY

systemctl restart awg31-panel 2>/dev/null || systemctl restart awg31-panel.service 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true
systemctl restart awg31-panel 2>/dev/null || systemctl restart awg31-panel.service 2>/dev/null || true

echo "NOVA AWG balancer installed. Backup: $BACKUP"
echo "Open: /balancer"
