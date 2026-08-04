import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HomeclawClient


class HomeclawCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass, client: HomeclawClient) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name="Homeclaw",
            update_interval=timedelta(seconds=10),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status, timeline, insights, proposals = await asyncio.gather(
                self.client.get("/v1/status"),
                self.client.get("/v1/timeline?limit=20"),
                self.client.get("/v1/insights?limit=20"),
                self.client.get("/v1/proposals?limit=20"),
            )
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
        events = [{"record_type": "insight", **item} for item in insights.get("items", [])] + [
            {"record_type": "action_proposal", **item} for item in proposals.get("items", [])
        ]
        return {**status, "timeline": timeline.get("items", []), "events": events}
