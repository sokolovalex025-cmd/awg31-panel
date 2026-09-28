#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# 3X-UI automatic VPN configuration generator
# Creates VLESS Reality/XHTTP/gRPC, Trojan and Shadowsocks in 3x-ui.
# Generated configs are saved under /root/3xui-auto/configs.

die(){ echo "ERROR: $*" >&2; exit 1; }
command -v curl >/dev/null || die "curl is required"
command -v python3 >/dev/null || die "python3 is required"

OUT="/root/3xui-auto/configs"
mkdir -p "$OUT"
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT

read -rp "3x-ui URL [http://127.0.0.1:2053]: " PANEL
PANEL="${PANEL:-http://127.0.0.1:2053}"; PANEL="${PANEL%/}"

echo "1) API Token"
echo "2) Username/password"
read -rp "Auth [1]: " AUTH; AUTH="${AUTH:-1}"
ARGS=()
if [[ "$AUTH" == 1 ]]; then
  read -rsp "API Token: " TOKEN; echo
  [[ -n "$TOKEN" ]] || die "Empty token"
  ARGS=(-H "Authorization: Bearer $TOKEN")
else
  read -rp "Username: " USER
  read -rsp "Password: " PASS; echo
  BODY=$(python3 - "$USER" "$PASS" <<'PY'
import json,sys
print(json.dumps({"username":sys.argv[1],"password":sys.argv[2]}))
PY
)
  LOGIN=$(curl -ksS --fail-with-body -c "$COOKIE" -H 'Content-Type: application/json' -X POST "$PANEL/login" --data "$BODY") || die "Login failed"
  python3 - "$LOGIN" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if not d.get("success",False): raise SystemExit(d.get("msg","login failed"))
PY
  ARGS=(-b "$COOKIE")
fi

api(){ curl -ksS --fail-with-body "${ARGS[@]}" "$@"; }
LIST=$(api "$PANEL/panel/api/inbounds/list") || die "3x-ui API unavailable"
python3 - "$LIST" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if d.get("success") is False: raise SystemExit(d.get("msg","API error"))
PY

IP=$(curl -4 -ksS --max-time 5 https://api.ipify.org || true)
read -rp "Server address [${IP:-127.0.0.1}]: " ADDRESS
ADDRESS="${ADDRESS:-${IP:-127.0.0.1}}"

echo "1) VLESS Reality"
echo "2) VLESS XHTTP + TLS"
echo "3) VLESS gRPC + TLS"
echo "4) Trojan"
echo "5) Shadowsocks"
echo "6) VLESS XHTTP + Reality"
read -rp "Protocol [1]: " CHOICE; CHOICE="${CHOICE:-1}"
[[ "$CHOICE" =~ ^[1-6]$ ]] || die "Invalid protocol"

read -rp "Client name [client-$(date +%s)]: " EMAIL
EMAIL="${EMAIL:-client-$(date +%s)}"
read -rp "Port [443]: " PORT; PORT="${PORT:-443}"
[[ "$PORT" =~ ^[0-9]+$ ]] || die "Invalid port"

UUID=$(python3 - <<'PY'
import uuid; print(uuid.uuid4())
PY
)
SID=$(python3 - <<'PY'
import secrets; print(secrets.token_hex(8))
PY
)

SNI="www.microsoft.com"
if [[ "$CHOICE" =~ ^(1|2|3|6)$ ]]; then
  read -rp "SNI [$SNI]: " X; SNI="${X:-$SNI}"
fi

RPRIV=""; RPUB=""
if [[ "$CHOICE" == 1 || "$CHOICE" == 6 ]]; then
  if command -v xray >/dev/null 2>&1; then
    X=$(xray x25519 2>/dev/null || true)
    RPRIV=$(printf '%s\n' "$X" | awk -F': *' 'tolower($1) ~ /private/ {print $2;exit}')
    RPUB=$(printf '%s\n' "$X" | awk -F': *' 'tolower($1) ~ /password|public/ {print $2;exit}')
  fi
  [[ -n "$RPRIV" && -n "$RPUB" ]] || {
    read -rsp "Reality private key: " RPRIV; echo
    read -rp "Reality public key: " RPUB
  }
fi

PASSWORD=""
[[ "$CHOICE" == 4 || "$CHOICE" == 5 ]] && PASSWORD=$(python3 - <<'PY'
import secrets; print(secrets.token_urlsafe(24))
PY
)

PAYLOAD=$(python3 - "$CHOICE" "$UUID" "$EMAIL" "$PORT" "$SNI" "$SID" "$RPRIV" "$RPUB" "$PASSWORD" <<'PY'
import json,sys
c,uid,email,port,sni,sid,priv,pub,pwd=sys.argv[1:]; port=int(port)
x={"enable":True,"remark":email,"listen":"","port":port,"expiryTime":0,"total":0}
if c in ("1","2","3","6"):
 x["protocol"]="vless"; x["settings"]={"clients":[{"id":uid,"flow":"xtls-rprx-vision" if c=="1" else "","email":email,"enable":True,"limitIp":0,"totalGB":0,"expiryTime":0,"tgId":"","subId":"","comment":"","reset":0}],"decryption":"none","fallbacks":[]}
 if c=="1":
  x["streamSettings"]={"network":"tcp","security":"reality","realitySettings":{"show":False,"xver":0,"dest":f"{sni}:443","serverNames":[sni],"privateKey":priv,"shortIds":[sid],"settings":{"fingerprint":"chrome","serverName":sni,"spiderX":"/"}}}
 elif c=="6":
  x["streamSettings"]={"network":"xhttp","security":"reality","xhttpSettings":{"path":"/xhttp","host":"","mode":"auto"},"realitySettings":{"show":False,"xver":0,"dest":f"{sni}:443","serverNames":[sni],"privateKey":priv,"shortIds":[sid],"settings":{"fingerprint":"chrome","serverName":sni,"spiderX":"/"}}}
 elif c=="2":
  x["streamSettings"]={"network":"xhttp","security":"tls","xhttpSettings":{"path":"/xhttp","host":"","mode":"auto"},"tlsSettings":{"serverName":sni,"minVersion":"1.2","maxVersion":"1.3"}}
 else:
  x["streamSettings"]={"network":"grpc","security":"tls","grpcSettings":{"serviceName":"grpc","multiMode":False},"tlsSettings":{"serverName":sni,"minVersion":"1.2","maxVersion":"1.3"}}
elif c=="4":
 x["protocol"]="trojan"; x["settings"]={"clients":[{"password":pwd,"email":email,"flow":"","enable":True,"limitIp":0,"totalGB":0,"expiryTime":0,"tgId":"","subId":"","comment":"","reset":0}],"fallbacks":[]}
 x["streamSettings"]={"network":"tcp","security":"none","tcpSettings":{"acceptProxyProtocol":False,"header":{"type":"none"}}}
else:
 x["protocol"]="shadowsocks"; x["settings"]={"clients":[{"method":"aes-128-gcm","password":pwd,"email":email,"enable":True,"limitIp":0,"totalGB":0,"expiryTime":0,"tgId":"","subId":"","comment":"","reset":0}],"method":"aes-128-gcm","password":pwd,"network":"tcp,udp"}
 x["streamSettings"]={"network":"tcp","security":"none","tcpSettings":{"acceptProxyProtocol":False,"header":{"type":"none"}}}
x["sniffing"]={"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False,"routeOnly":False}
print(json.dumps(x,separators=(",",":")))
PY
)

STAMP=$(date +%Y%m%d-%H%M%S)
printf '%s\n' "$PAYLOAD" > "$OUT/$STAMP-$EMAIL-payload.json"

RESP=$(curl -ksS --fail-with-body "${ARGS[@]}" -H 'Content-Type: application/json' -X POST "$PANEL/panel/api/inbounds/add" --data "$PAYLOAD") || die "Inbound creation failed: $RESP"
printf '%s\n' "$RESP" > "$OUT/$STAMP-$EMAIL-response.json"

python3 - "$RESP" <<'PY'
import json,sys
d=json.loads(sys.argv[1])
if not d.get("success",False): raise SystemExit(d.get("msg","3x-ui rejected request"))
print("Inbound created:", (d.get("obj") or {}).get("id",""))
PY

LINKS=$(api "$PANEL/panel/api/inbounds/allLinks" 2>/dev/null || true)
LINK=$(python3 - "$LINKS" "$EMAIL" <<'PY'
import json,sys
try:
 d=json.loads(sys.argv[1]); xs=d.get("obj") or []
except: xs=[]
for x in xs:
 if isinstance(x,str) and ("#"+sys.argv[2]) in x: print(x)
PY
)
[[ -n "$LINK" ]] && printf '%s\n' "$LINK" > "$OUT/$STAMP-$EMAIL-link.txt"

echo
echo "Created successfully."
echo "Protocol: $CHOICE"
echo "Address: $ADDRESS"
echo "Port: $PORT"
echo "Client: $EMAIL"
[[ -n "$LINK" ]] && { echo "Link:"; echo "$LINK"; }
[[ -n "$PASSWORD" ]] && echo "Client password: $PASSWORD"
echo "Saved to: $OUT"
