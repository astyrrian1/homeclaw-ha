import asyncio
import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponseError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HomeclawClient


class HomeclawCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass,
        client: HomeclawClient,
        *,
        transport_actor: dict[str, str],
        notification_services: dict[str, list[str]],
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name="Homeclaw",
            update_interval=timedelta(seconds=10),
        )
        self.client = client
        self.transport_actor = transport_actor
        self.notification_services = notification_services

    async def _async_update_data(self) -> dict[str, Any]:
        integration_health = "ok"
        try:
            meta = await self.client.get("/v1/meta")
        except ClientResponseError as exc:
            if exc.status != 404:
                raise UpdateFailed(str(exc)) from exc
            meta = {"api_version": "legacy", "features": {}}
            integration_health = "version_skew"
        features = meta.get("features", {})
        if not all(
            features.get(name) is True
            for name in ("house_journal", "signal_summaries", "audit_funnel")
        ):
            integration_health = "version_skew"
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
                world,
                beliefs,
                runs,
                claims,
                clusters,
                coverage,
                scheduled_jobs,
                procedural_proposals,
                resident_profiles,
                forecasts,
                experiments,
            ) = await asyncio.gather(
                self.client.get("/v1/status"),
                self.client.get("/v1/timeline?limit=20"),
                self.client.get("/v1/insights?limit=20"),
                self.client.get("/v1/proposals?limit=20"),
                self.client.post(
                    "/v1/notifications/lease",
                    {"limit": 50, "lease_seconds": 30},
                    actor=self.transport_actor,
                ),
                self.client.get("/v1/cognition/programs"),
                self.client.get("/v1/memory/candidates?limit=50"),
                self.client.get("/v1/standing-intents?limit=50"),
                self.client.get("/v1/journal/entries?limit=20"),
                self.client.get("/v1/world?limit=100"),
                self.client.get("/v1/beliefs?limit=50"),
                self.client.get("/v1/cognition/runs?limit=50"),
                self.client.get("/v1/memory/claims?limit=50"),
                self.client.get("/v1/journal/clusters?limit=50"),
                self.client.get("/v1/catalog/coverage"),
                self.client.get("/v1/scheduled-jobs?limit=50"),
                self.client.get("/v1/procedural-proposals?limit=50"),
                self.client.get("/v1/residents/profiles"),
                self.client.get("/v1/forecasts?limit=50"),
                self.client.get("/v1/experiments?limit=50"),
            )
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
        journal: dict[str, Any] = {"items": []}
        if features.get("house_journal") is True:
            try:
                journal = await self.client.get("/v1/journal/entries?limit=20")
            except ClientResponseError as exc:
                if exc.status != 404:
                    raise UpdateFailed(str(exc)) from exc
                integration_health = "version_skew"
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
            "world": world,
            "beliefs": beliefs.get("items", []),
            "cognition_runs": runs.get("items", []),
            "memory_claims": claims.get("items", []),
            "journal_clusters": clusters.get("items", []),
            "catalog_coverage": coverage,
            "scheduled_jobs": scheduled_jobs.get("items", []),
            "procedural_proposals": procedural_proposals.get("items", []),
            "resident_profiles": resident_profiles.get("items", []),
            "forecasts": forecasts.get("items", []),
            "experiments": experiments.get("items", []),
            "integration_health": integration_health,
            "api_version": meta.get("api_version", "unknown"),
        }

    async def async_deliver_notification(self, item: dict[str, Any]) -> None:
        item_id = str(item["id"])
        services = self.notification_services.get(str(item.get("resident_id", "")), [])
        accepted: list[str] = []
        try:
            for value in services:
                domain, separator, service = value.partition(".")
                if separator != "." or domain != "notify" or not service:
                    raise ValueError("Homeclaw notification services must use notify.<service>")
                await self.hass.services.async_call(
                    domain,
                    service,
                    {
                        "title": item.get("title", "Homeclaw"),
                        "message": item.get("body", ""),
                        "data": {
                            "homeclaw_delivery_id": item_id,
                            "homeclaw_record_type": item.get("record_type"),
                            "homeclaw_record_id": str(item.get("record_id", "")),
                        },
                    },
                    blocking=False,
                )
                accepted.append(value)
            channel = "home_assistant_event" if not accepted else "home_assistant_notify"
            reference = ",".join(accepted) if accepted else f"event:{item_id}"
            await self.client.post(
                f"/v1/notifications/{item_id}/accept",
                {"channel": channel, "transport_reference": reference},
                actor=self.transport_actor,
            )
        except Exception as exc:
            await self.client.post(
                f"/v1/notifications/{item_id}/fail",
                {"channel": "home_assistant", "error": str(exc)[:1000]},
                actor=self.transport_actor,
            )
            raise
