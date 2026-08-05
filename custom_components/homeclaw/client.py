from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession


class HomeclawClient:
    def __init__(self, session: ClientSession, url: str, token: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def get(self, path: str) -> dict[str, Any]:
        async with self._session.get(
            f"{self._url}{path}", headers=self._headers, timeout=10
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._session.post(
            f"{self._url}{path}",
            headers=self._headers,
            json=payload or {},
            timeout=15,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._session.put(
            f"{self._url}{path}", headers=self._headers, json=payload, timeout=10
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def delete(self, path: str) -> dict[str, Any]:
        async with self._session.delete(
            f"{self._url}{path}", headers=self._headers, timeout=10
        ) as response:
            response.raise_for_status()
            return await response.json()

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
