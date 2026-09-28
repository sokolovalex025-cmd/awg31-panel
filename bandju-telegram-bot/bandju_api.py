from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx


@dataclass
class BandjuResult:
    ok: bool
    data: Any = None
    status_code: int = 0
    error: str = ""


class BandjuAPI:
    """Client for the confirmed Bandju Panel 1.9.x local API."""

    def __init__(self) -> None:
        self.base = os.getenv("BANDJU_API_BASE", "http://127.0.0.1:7777").rstrip("/")
        self.token = os.getenv("BANDJU_API_TOKEN", "").strip()
        self.timeout = float(os.getenv("BANDJU_API_TIMEOUT", "15"))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Bandju-Telegram-Bot/1.2",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _client_path(client_name: str) -> str:
        # Keep slashes and other reserved characters out of the path segment.
        return quote(str(client_name), safe="")

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
        # Confirmed Bandju 1.9.0 request: {"name": "...", optional "container": "..."}.
        payload: dict[str, Any] = {"name": name}
        if container:
            payload["container"] = container
        # access_icon is intentionally not sent: it is not part of the confirmed
        # Bandju 1.9.0 AmneziaWG create schema.
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
        if isinstance(clients, dict):
            clients = clients.get("data", clients)
            if isinstance(clients, dict):
                if str(clients.get("name", "")) == client_name:
                    return BandjuResult(True, clients, result.status_code)
                clients = clients.get("clients", clients.get("items", []))

        if isinstance(clients, list):
            for client in clients:
                if isinstance(client, dict) and str(client.get("name", "")) == client_name:
                    return BandjuResult(True, client, result.status_code)

        return BandjuResult(
            False, None, 404, f"AmneziaWG client '{client_name}' was not found"
        )

    async def toggle_amnezia_client(
        self,
        client_name: str,
        enabled: bool,
        container: str = "",
    ) -> BandjuResult:
        # Confirmed Bandju 1.9.0 request: {"enabled": true|false}.
        payload: dict[str, Any] = {"enabled": enabled}
        if container:
            payload["container"] = container
        return await self.request(
            "POST",
            f"/api/amneziawg/clients/{self._client_path(client_name)}/toggle",
            json=payload,
        )

    async def delete_amnezia_client(
        self,
        client_name: str,
        container: str = "",
    ) -> BandjuResult:
        # Confirmed route. Container is optional.
        payload: dict[str, Any] = {"container": container} if container else {}
        kwargs: dict[str, Any] = {"json": payload} if payload else {}
        return await self.request(
            "DELETE",
            f"/api/amneziawg/clients/{self._client_path(client_name)}",
            **kwargs,
        )

    async def list_accesses(self) -> BandjuResult:
        return await self.list_amnezia_clients()

    async def create_access(self, payload: dict[str, Any]) -> BandjuResult:
        name = str(payload.get("name", "")).strip()
        container = str(payload.get("container", "")).strip()
        if not name:
            return BandjuResult(False, None, 400, "Client name is required")
        return await self.create_amnezia_client(name, container)

    async def get_access(self, access_id: str) -> BandjuResult:
        return await self.get_amnezia_client(access_id)

    async def enable_access(self, access_id: str, container: str = "") -> BandjuResult:
        return await self.toggle_amnezia_client(access_id, True, container)

    async def disable_access(self, access_id: str, container: str = "") -> BandjuResult:
        return await self.toggle_amnezia_client(access_id, False, container)

    async def renew_access(self, access_id: str, days: int) -> BandjuResult:
        return BandjuResult(
            False,
            None,
            501,
            "Bandju 1.9.0 AmneziaWG renewal endpoint is not confirmed",
        )

    async def discover(self) -> dict[str, Any]:
        return {}
