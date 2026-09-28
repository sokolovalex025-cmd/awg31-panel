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
    def __init__(self) -> None:
        self.base = os.getenv("BANDJU_API_BASE", "http://127.0.0.1:7777").rstrip("/")
        self.token = os.getenv("BANDJU_API_TOKEN", "").strip()
        self.timeout = float(os.getenv("BANDJU_API_TIMEOUT", "15"))

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "Bandju-Telegram-Bot/1.0"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def request(self, method: str, path: str, **kwargs: Any) -> BandjuResult:
        if not path.startswith("/"):
            path = "/" + path
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers()) as c:
                r = await c.request(method, self.base + path, **kwargs)
            try:
                data = r.json()
            except Exception:
                data = r.text
            return BandjuResult(r.is_success, data, r.status_code, "" if r.is_success else str(data))
        except Exception as exc:
            return BandjuResult(False, None, 0, str(exc))

    async def health(self) -> BandjuResult:
        for path in ("/health", "/api/health", "/api/status", "/status"):
            result = await self.request("GET", path)
            if result.ok:
                return result
        return BandjuResult(False, None, 0, "Bandju API health endpoint was not found")

    async def discover(self) -> dict[str, Any]:
        candidates = (
            "/openapi.json",
            "/api/openapi.json",
            "/docs/openapi.json",
            "/api/docs/openapi.json",
        )
        for path in candidates:
            result = await self.request("GET", path)
            if result.ok and isinstance(result.data, dict):
                return {"path": path, "openapi": result.data}
        return {}

    async def list_accesses(self) -> BandjuResult:
        override = os.getenv("BANDJU_ACCESS_LIST_PATH", "").strip()
        paths = [override] if override else [
            "/api/accesses",
            "/api/access",
            "/api/clients",
            "/api/clients/accesses",
        ]
        for path in paths:
            if not path:
                continue
            result = await self.request("GET", path)
            if result.ok:
                return result
        return BandjuResult(False, None, 0, "Access list endpoint was not detected")

    async def create_access(self, payload: dict[str, Any]) -> BandjuResult:
        override = os.getenv("BANDJU_ACCESS_CREATE_PATH", "").strip()
        paths = [override] if override else [
            "/api/accesses",
            "/api/access",
            "/api/clients",
        ]
        for path in paths:
            if not path:
                continue
            result = await self.request("POST", path, json=payload)
            if result.ok:
                return result
        return BandjuResult(False, None, 0, "Access create endpoint was not detected")

    async def get_access(self, access_id: str) -> BandjuResult:
        override = os.getenv("BANDJU_ACCESS_GET_PATH", "").strip()
        paths = [override.format(id=access_id)] if override else [
            f"/api/accesses/{access_id}",
            f"/api/access/{access_id}",
            f"/api/clients/{access_id}",
        ]
        for path in paths:
            result = await self.request("GET", path)
            if result.ok:
                return result
        return BandjuResult(False, None, 0, "Access endpoint was not detected")

    async def _mutate(self, action: str, access_id: str, days: int | None = None) -> BandjuResult:
        env_name = {
            "renew": "BANDJU_ACCESS_RENEW_PATH",
            "enable": "BANDJU_ACCESS_ENABLE_PATH",
            "disable": "BANDJU_ACCESS_DISABLE_PATH",
        }[action]
        override = os.getenv(env_name, "").strip()
        if override:
            return await self.request(
                "POST",
                override.format(id=access_id),
                json={"days": days} if days is not None else {},
            )

        candidates = {
            "renew": [
                f"/api/accesses/{access_id}/renew",
                f"/api/access/{access_id}/renew",
                f"/api/clients/{access_id}/renew",
            ],
            "enable": [
                f"/api/accesses/{access_id}/enable",
                f"/api/access/{access_id}/enable",
                f"/api/clients/{access_id}/enable",
            ],
            "disable": [
                f"/api/accesses/{access_id}/disable",
                f"/api/access/{access_id}/disable",
                f"/api/clients/{access_id}/disable",
            ],
        }[action]

        for path in candidates:
            result = await self.request(
                "POST",
                path,
                json={"days": days} if days is not None else {},
            )
            if result.ok:
                return result
        return BandjuResult(False, None, 0, f"{action} endpoint was not detected")

    async def renew_access(self, access_id: str, days: int) -> BandjuResult:
        return await self._mutate("renew", access_id, days)

    async def enable_access(self, access_id: str) -> BandjuResult:
        return await self._mutate("enable", access_id)

    async def disable_access(self, access_id: str) -> BandjuResult:
        return await self._mutate("disable", access_id)
