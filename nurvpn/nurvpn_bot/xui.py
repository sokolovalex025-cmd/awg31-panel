import json
import uuid
import aiohttp

class XUIError(RuntimeError):
    pass

class XUIClient:
    def __init__(self, settings):
        self.s = settings
        self.session = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=self.s.xui_verify_tls)
        self.session = aiohttp.ClientSession(connector=connector)
        await self.login()
        return self

    async def __aexit__(self, *exc):
        if self.session:
            await self.session.close()

    async def login(self):
        if not self.s.xui_url:
            raise XUIError("XUI_URL is not configured")
        async with self.session.post(self.s.xui_url + "/login", data={"username": self.s.xui_username, "password": self.s.xui_password}) as r:
            if r.status >= 400:
                raise XUIError(f"3x-ui login HTTP {r.status}")
            data = await r.json(content_type=None)
            if not data.get("success", True):
                raise XUIError(data.get("msg", "3x-ui login failed"))

    async def add_vless_client(self, email: str, expiry_ms: int = 0):
        cid = str(uuid.uuid4())
        client = {"id": cid, "flow": "xtls-rprx-vision", "email": email, "limitIp": 0, "totalGB": 0, "expiryTime": expiry_ms, "enable": True, "tgId": "", "subId": "", "reset": 0}
        payload = {"id": self.s.xui_inbound_id, "settings": json.dumps({"clients": [client]})}
        async with self.session.post(self.s.xui_url + "/panel/api/inbounds/addClient", data=payload) as r:
            data = await r.json(content_type=None)
            if r.status >= 400 or not data.get("success", False):
                raise XUIError(data.get("msg", f"addClient HTTP {r.status}"))
        return cid

    async def get_inbound(self):
        async with self.session.get(self.s.xui_url + f"/panel/api/inbounds/get/{self.s.xui_inbound_id}") as r:
            data = await r.json(content_type=None)
            if r.status >= 400 or not data.get("success", False):
                raise XUIError(data.get("msg", f"get inbound HTTP {r.status}"))
            return data["obj"]

    async def create_config(self, client_uuid: str):
        inbound = await self.get_inbound()
        stream = inbound.get("streamSettings") or {}
        port = inbound.get("port")
        settings = json.loads(inbound.get("settings") or "{}")
        client = next((x for x in settings.get("clients", []) if x.get("id") == client_uuid), None)
        if not client:
            raise XUIError("Client was created but not found in inbound")
        network = stream.get("network", "tcp")
        security = stream.get("security", "none")
        reality = stream.get("realitySettings") or {}
        host = self.s.xui_subscription_host or inbound.get("remark") or "vpn"
        if security == "reality":
            rs = reality.get("settings", {}) if isinstance(reality, dict) else {}
            pbk = rs.get("publicKey", "")
            sid = (reality.get("shortIds") or [""])[0]
            sni = (reality.get("serverNames") or ["www.microsoft.com"])[0]
            params = f"type={network}&security=reality&pbk={pbk}&fp=chrome&sni={sni}&sid={sid}&spx=%2F"
        else:
            params = f"type={network}&security={security}"
        return f"vless://{client_uuid}@{host}:{port}?{params}#{client.get('email','VPN')}"
