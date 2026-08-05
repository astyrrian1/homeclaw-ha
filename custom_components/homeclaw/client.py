import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession


class HomeclawClient:
    def __init__(
        self,
        session: ClientSession,
        url: str,
        token: str,
        *,
        actor_secret: str = "",
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._actor_secret = actor_secret.encode()

    async def get(self, path: str) -> dict[str, Any]:
        async with self._session.get(
            f"{self._url}{path}", headers=self._headers, timeout=10
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def post(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        actor: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = _canonical_body(payload or {})
        async with self._session.post(
            f"{self._url}{path}",
            headers=self._mutation_headers("POST", path, body, actor),
            data=body,
            timeout=15,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def put(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        actor: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = _canonical_body(payload)
        async with self._session.put(
            f"{self._url}{path}",
            headers=self._mutation_headers("PUT", path, body, actor),
            data=body,
            timeout=10,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete(self, path: str, *, actor: dict[str, str] | None = None) -> dict[str, Any]:
        body = b""
        async with self._session.delete(
            f"{self._url}{path}",
            headers=self._mutation_headers("DELETE", path.split("?", 1)[0], body, actor),
            timeout=10,
        ) as response:
            response.raise_for_status()
            return await response.json()

    def _mutation_headers(
        self,
        method: str,
        path: str,
        body: bytes,
        actor: dict[str, str] | None,
    ) -> dict[str, str]:
        headers = {**self._headers, "Content-Type": "application/json"}
        if not self._actor_secret or actor is None:
            return headers
        issued_at = int(time.time())
        expires_at = issued_at + 30
        nonce = secrets.token_urlsafe(24)
        digest = hashlib.sha256(body).hexdigest()
        role = actor["role"]
        material = "\n".join(
            (
                "1",
                actor["ha_user_id"],
                actor["resident_id"],
                role,
                method,
                path,
                digest,
                str(issued_at),
                str(expires_at),
                nonce,
            )
        ).encode()
        signature = "v1=" + hmac.new(self._actor_secret, material, hashlib.sha256).hexdigest()
        headers.update(
            {
                "X-Homeclaw-Actor-Version": "1",
                "X-Homeclaw-HA-User": actor["ha_user_id"],
                "X-Homeclaw-Resident": actor["resident_id"],
                "X-Homeclaw-Actor-Role": role,
                "X-Homeclaw-Issued-At": str(issued_at),
                "X-Homeclaw-Expires-At": str(expires_at),
                "X-Homeclaw-Nonce": nonce,
                "X-Homeclaw-Body-SHA256": digest,
                "X-Homeclaw-Actor-Signature": signature,
            }
        )
        return headers

    async def validate(self) -> None:
        try:
            await self.get("/v1/status")
        except ClientResponseError as exc:
            if exc.status == 401:
                raise InvalidAuth from exc
            raise CannotConnect from exc
        except (ClientError, TimeoutError) as exc:
            raise CannotConnect from exc


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass


def _canonical_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
