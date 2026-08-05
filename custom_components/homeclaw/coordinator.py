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
            (
                status,
                timeline,
                insights,
                proposals,
                notifications,
                programs,
                candidates,
                intents,
                journal,
            ) = await asyncio.gather(
                self.client.get("/v1/status"),
                self.client.get("/v1/timeline?limit=20"),
                self.client.get("/v1/insights?limit=20"),
                self.client.get("/v1/proposals?limit=20"),
                self.client.get("/v1/notifications?limit=50"),
                self.client.get("/v1/cognition/programs"),
                self.client.get("/v1/memory/candidates?limit=50"),
                self.client.get("/v1/standing-intents?limit=50"),
                self.client.get("/v1/journal/entries?limit=20"),
            )
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
        events = [{"record_type": "insight", **item} for item in insights.get("items", [])] + [
            {"record_type": "action_proposal", **item} for item in proposals.get("items", [])
        ]
        pending_notifications = [
            {"record_type": "notification", **item} for item in notifications.get("items", [])
        ]
        events.extend(pending_notifications)
        pending_candidates = [
            item for item in candidates.get("items", []) if item.get("status") == "pending"
        ]
        return {
            **status,
            "timeline": timeline.get("items", []),
            "events": events,
            "cognition_programs": programs.get("items", []),
            "memory_candidates": candidates.get("items", []),
            "pending_memory_candidates": len(pending_candidates),
            "standing_intents": intents.get("items", []),
            "journal_entries": journal.get("items", []),
        }
