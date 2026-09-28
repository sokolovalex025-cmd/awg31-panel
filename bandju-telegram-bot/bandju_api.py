from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class BandjuResult:
    ok: bool
    data: Any = None
    status_code: int = 0
    error: str = ""


class BandjuAPI:
    """Client for the local Bandju Panel 1.9.x API."""

    def __init__(self) -> None:
        self.base = os.getenv("BANDJU_API_BASE", "http://127.0.0.1:7777").rstrip("/")
        self.token = os.getenv("BANDJU_API_TOKEN", "").strip()
        self.timeout = float(os.getenv("BANDJU_API_TIMEOUT", "15"))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Bandju-Telegram-Bot/1.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def request(self, method: str, path: str, **kwargs: Any) -> BandjuResult:
        if not path.startswith("/"):
            path = "/" + path
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._headers(),
            ) as client:
                response = await client.request(method, self.base + path, **kwargs)
            try:
                data = response.json()
            except Exception:
                data = response.text
            return BandjuResult(
                response.is_success,
                data,
                response.status_code,
                "" if response.is_success else str(data),
            )
        except Exception as exc:
            return BandjuResult(False, None, 0, str(exc))

    async def health(self) -> BandjuResult:
        # Confirmed on Bandju 1.9.0.
        return await self.request("GET", "/api/health")

    async def status(self) -> BandjuResult:
        return await self.request("GET", "/api/status")

    async def list_amnezia_clients(self, container: str = "") -> BandjuResult:
        params = {"container": container} if container else {}
        return await self.request("GET", "/api/amneziawg/clients", params=params)

    async def create_amnezia_client(
        self,
        name: str,
        container: str = "",
        access_icon: str = "",
    ) -> BandjuResult:
        payload: dict[str, Any] = {"name": name}
        if container:
            payload["container"] = container
        if access_icon:
            payload["access_icon"] = access_icon
        return await self.request("POST", "/api/amneziawg/clients", json=payload)

    async def get_amnezia_client(
        self,
        client_name: str,
        container: str = "",
    ) -> BandjuResult:
        result = await self.list_amnezia_clients(container)
        if not result.ok:
            return result

        clients = result.data
        # Bandju normally wraps responses in data. Keep this tolerant because
        # the exact response shape can vary between panel builds.
        if isinstance(clients, dict):
            clients = clients.get("data", clients)
            if isinstance(clients, dict):
                clients = clients.get("clients", clients.get("items", []))

        if isinstance(clients, list):
            for client in clients:
                if not isinstance(client, dict):
                    continue
                name = str(client.get("name", ""))
                if name == client_name:
                    return BandjuResult(True, client, result.status_code)
        return BandjuResult(False, None, 404, f"AmneziaWG client '{client_name}' was not found")

    async def toggle_amnezia_client(
        self,
        client_name: str,
        enabled: bool,
        container: str = "",
    ) -> BandjuResult:
        payload: dict[str, Any] = {"enabled": enabled}
        if container:
            payload["container"] = container
        return await self.request(
            "POST",
            f"/api/amneziawg/clients/{client_name}/toggle",
            json=payload,
        )

    async def delete_amnezia_client(
        self,
        client_name: str,
        container: str = "",
    ) -> BandjuResult:
        payload: dict[str, Any] = {}
        if container:
            payload["container"] = container
        return await self.request(
            "DELETE",
            f"/api/amneziawg/clients/{client_name}",
            json=payload,
        )

    # Compatibility helpers used by the first bot implementation.
    async def list_accesses(self) -> BandjuResult:
        return await self.list_amnezia_clients()

    async def create_access(self, payload: dict[str, Any]) -> BandjuResult:
        name = str(payload.get("name", "")).strip()
        container = str(payload.get("container", "")).strip()
        icon = str(payload.get("access_icon", payload.get("icon", ""))).strip()
        if not name:
            return BandjuResult(False, None, 400, "Client name is required")
        return await self.create_amnezia_client(name, container, icon)

    async def get_access(self, access_id: str) -> BandjuResult:
        # For Bandju AmneziaWG the stable user-facing identifier is the
        # client name, not the generic access_id used by older code.
        return await self.get_amnezia_client(access_id)

    async def enable_access(self, access_id: str, container: str = "") -> BandjuResult:
        return await self.toggle_amnezia_client(access_id, True, container)

    async def disable_access(self, access_id: str, container: str = "") -> BandjuResult:
        return await self.toggle_amnezia_client(access_id, False, container)

    async def renew_access(self, access_id: str, days: int) -> BandjuResult:
        # Bandju 1.9.0 routes inspected so far do not expose a confirmed
        # AmneziaWG client renewal/expiry endpoint. Never guess a mutating route.
        return BandjuResult(
            False,
            None,
            501,
            "Bandju 1.9.0 AmneziaWG renewal endpoint is not confirmed",
        )

    async def discover(self) -> dict[str, Any]:
        # Bandju 1.9.0 does not expose OpenAPI JSON at the standard paths
        # checked by the installer, so return an empty result rather than
        # probing arbitrary endpoints.
        return {}
