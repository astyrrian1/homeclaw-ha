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
            for name in (
                "house_journal",
                "signal_summaries",
                "audit_funnel",
                "cognition_activation",
                "memory_seeds",
                "standing_intent_preview",
                "qualification_evidence_v2",
                "release_certified_auto_activation",
                "coherent_situations",
                "cognition_value_atoms",
                "reflection_objectives",
            )
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
                qualification_checks,
                qualification_campaigns,
                auto_activation,
                release_certifications,
                situations,
                value_funnel,
                reflections,
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
                self.client.get("/v1/qualification/checks?limit=100"),
                self.client.get("/v1/qualification/campaigns?limit=100"),
                self.client.get("/v1/cognition/auto-activation"),
                self.client.get("/v1/cognition/certifications?limit=100"),
                self.client.get("/v1/situations?limit=100"),
                self.client.get("/v1/cognition/value-funnel"),
                self.client.get("/v1/reflections?limit=100"),
            )
        except Exception as exc:
            raise UpdateFailed(str(exc)) from exc
        try:
            (
                activation_funnel,
                memory_seeds,
                memory_reviews,
                memory_backfills,
            ) = await asyncio.gather(
                self.client.get("/v1/activation/funnel"),
                self.client.get("/v1/memory/seeds?limit=50"),
                self.client.get("/v1/memory/reviews?limit=50"),
                self.client.get("/v1/memory/backfills?limit=20"),
            )
            program_readiness = await asyncio.gather(
                *(
                    self.client.get(
                        f"/v1/cognition/programs/{item.get('id') or item.get('program_id')}"
                        "/readiness"
                    )
                    for item in programs.get("items", [])
                )
            )
            readiness_by_program = {
                item["program_id"]: item.get("readiness") for item in program_readiness
            }
            for item in programs.get("items", []):
                program_id = item.get("id") or item.get("program_id")
                item["readiness"] = readiness_by_program.get(program_id)
            review_queues = await asyncio.gather(
                *(
                    self.client.get(
                        f"/v1/qualification/campaigns/{item['id']}/review-queue?limit=50"
                    )
                    for item in qualification_campaigns.get("items", [])
                    if item.get("status")
                    in {"collecting", "coverage_complete", "review_ready"}
                )
            )
            qualification_review_queue = [
                unit for queue in review_queues for unit in queue.get("items", [])
            ]
        except ClientResponseError as exc:
            if exc.status != 404:
                raise UpdateFailed(str(exc)) from exc
            activation_funnel = {"totals": {}, "by_status": []}
            memory_seeds = {"items": []}
            memory_reviews = {"items": []}
            memory_backfills = {"items": []}
            qualification_review_queue = []
            integration_health = "version_skew"
        journal: dict[str, Any] = {"items": []}
        if features.get("house_journal") is True:
            try:
                journal = await self.client.get("/v1/journal/entries?limit=20")
            except ClientResponseError as exc:
                if exc.status != 404:
                    raise UpdateFailed(str(exc)) from exc
                integration_health = "version_skew"
        events = [
            {**item, "record_type": "insight"} for item in insights.get("items", [])
        ] + [
            {**item, "record_type": "action_proposal"}
            for item in proposals.get("items", [])
        ]
        pending_notifications = [
            {**item, "record_type": "notification"}
            for item in notifications.get("items", [])
        ]
        events.extend(pending_notifications)
        pending_candidates = [
            item
            for item in candidates.get("items", [])
            if item.get("status") == "pending"
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
            "qualification_checks": qualification_checks.get("items", []),
            "qualification_campaigns": qualification_campaigns.get("items", []),
            "qualification_review_queue": qualification_review_queue,
            "cognition_auto_activation": auto_activation,
            "release_certifications": release_certifications.get("items", []),
            "activation_funnel": activation_funnel,
            "memory_seeds": memory_seeds.get("items", []),
            "memory_reviews": memory_reviews.get("items", []),
            "memory_backfills": memory_backfills.get("items", []),
            "situations": situations.get("items", []),
            "cognition_value_funnel": value_funnel,
            "reflections": reflections.get("items", []),
        }

    async def async_deliver_notification(self, item: dict[str, Any]) -> None:
        item_id = str(item["id"])
        services = self.notification_services.get(str(item.get("resident_id", "")), [])
        accepted: list[str] = []
        try:
            for value in services:
                domain, separator, service = value.partition(".")
                if separator != "." or domain != "notify" or not service:
                    raise ValueError(
                        "Homeclaw notification services must use notify.<service>"
                    )
                notification_data = {
                    "homeclaw_delivery_id": item_id,
                    "homeclaw_record_type": item.get("record_type"),
                    "homeclaw_record_id": str(item.get("record_id", "")),
                }
                callback_id = str(item.get("callback_id") or "")
                if service.startswith("mobile_app_") and callback_id:
                    notification_data.update(
                        {
                            "tag": f"homeclaw-{item_id}",
                            "actions": [
                                {
                                    "action": f"HOMECLAW_RECEIPT_{callback_id}",
                                    "title": "Acknowledge",
                                }
                            ],
                        }
                    )
                service_payload = {
                    "title": item.get("title", "Homeclaw"),
                    "message": item.get("body", ""),
                }
                if service.startswith("mobile_app_"):
                    service_payload["data"] = notification_data
                await self.hass.services.async_call(
                    domain,
                    service,
                    service_payload,
                    blocking=False,
                )
                accepted.append(value)
            channel = (
                "home_assistant_event"
                if not accepted
                else (
                    "signal"
                    if all(value == "notify.signal" for value in accepted)
                    else "home_assistant_notify"
                )
            )
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
