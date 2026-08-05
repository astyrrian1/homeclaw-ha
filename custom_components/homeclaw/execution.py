"""Independent Home Assistant validation for signed named capabilities."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from .capability_contract import CAPABILITY_SPECS, validate_capability_parameters
from .const import (
    CONF_CAPABILITY_MAPPINGS,
    CONF_EXECUTION_SECRET,
    CONF_HOUSE_MODE_ENTITY,
)

CAPABILITY_RISK = {
    "ambient_lighting": "R1",
    "short_recirculation": "R1",
    "bounded_shade": "R1",
    "adjust_hvac": "R2",
    "adjust_erv": "R2",
    "irrigation": "R2",
    "load_scheduling": "R2",
    "unlock_exterior": "R3",
    "disarm_alarm": "R3",
    "open_exterior": "R3",
    "camera_privacy": "R3",
    "network_security_change": "R3",
    "emergency_shutdown": "R4",
}

FORBIDDEN_KEYS = {"service", "service_name", "entity_id", "device_id", "area_id", "target"}


class CapabilityExecutor:
    def __init__(self, hass, entry, coordinator) -> None:
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._seen_nonces: set[str] = set()
        self._last_execution: dict[tuple[str, str], datetime] = {}

    async def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        self._validate_envelope(request)
        capability = request["capability"]
        parameters = request["parameters"]
        role = str(parameters[CAPABILITY_SPECS[capability].role_key])
        mapping = self._mapping(capability, role)
        self._validate_context(request, mapping, role)
        handler = str(mapping.get("handler_script", ""))
        if not handler.startswith("script.") or self._hass.states.get(handler) is None:
            raise HomeAssistantError("capability handler is not an available allowlisted script")

        nonce = request["nonce"]
        self._seen_nonces.add(nonce)
        self._last_execution[(capability, role)] = datetime.now(UTC)
        variables = {
            "homeclaw_proposal_id": request["proposal_id"],
            "homeclaw_capability": capability,
            "homeclaw_parameters": parameters,
        }
        postconditions = mapping.get("postconditions", {})
        if not isinstance(postconditions, dict):
            raise HomeAssistantError("capability postconditions must be an object")
        before_states = self._state_snapshot({*postconditions, *mapping.get("required_states", {})})
        try:
            await self._hass.services.async_call(
                "script",
                "turn_on",
                {"entity_id": handler, "variables": variables},
                blocking=True,
            )
        except Exception as exc:
            rollback_result = await self._run_rollback(mapping, variables)
            if rollback_result is not None:
                return {
                    "status": "reverted" if rollback_result["succeeded"] else "failed",
                    "error": str(exc),
                    "mapping_version": mapping["mapping_version"],
                    "before_states": before_states,
                    "resulting_states": rollback_result["states"],
                    "postconditions_met": False,
                    "rollback": rollback_result,
                }
            raise
        timeout = max(1, min(int(mapping.get("outcome_timeout_seconds", 30)), 300))
        if postconditions and not await self._wait_for_states(postconditions, timeout):
            rollback_result = await self._run_rollback(mapping, variables)
            return {
                "status": (
                    "reverted"
                    if rollback_result is not None and rollback_result["succeeded"]
                    else "failed"
                ),
                "error": "capability postconditions timed out",
                "mapping_version": mapping["mapping_version"],
                "before_states": before_states,
                "resulting_states": self._state_snapshot(postconditions),
                "postconditions_met": False,
                "timed_out": True,
                "rollback": rollback_result,
            }
        return {
            "status": "achieved",
            "mapping_version": mapping["mapping_version"],
            "before_states": before_states,
            "resulting_states": self._state_snapshot(postconditions)
            or {handler: self._hass.states.get(handler).state},
            "postconditions_met": True,
        }

    def _validate_envelope(self, request: dict[str, Any]) -> None:
        expected = {
            "schema_version",
            "proposal_id",
            "nonce",
            "capability",
            "risk",
            "parameters",
            "issued_at",
            "expires_at",
            "confirmed",
            "mapping_version",
            "signature",
        }
        if set(request) != expected or request.get("schema_version") != "2":
            raise HomeAssistantError("malformed capability envelope")
        secret = str(self._entry.options.get(CONF_EXECUTION_SECRET, ""))
        if len(secret) < 32 or not _verify_signature(request, secret.encode()):
            raise HomeAssistantError("invalid capability signature")
        now = datetime.now(UTC)
        issued_at = datetime.fromisoformat(str(request["issued_at"]))
        expires_at = datetime.fromisoformat(str(request["expires_at"]))
        if issued_at.tzinfo is None or expires_at.tzinfo is None:
            raise HomeAssistantError("capability timestamps must be timezone-aware")
        if issued_at > now or expires_at <= now or (expires_at - issued_at).total_seconds() > 3600:
            raise HomeAssistantError("capability request is expired or has an invalid lifetime")
        nonce = str(request["nonce"])
        if nonce in self._seen_nonces:
            raise HomeAssistantError("capability nonce was already used")
        capability = str(request["capability"])
        if capability not in CAPABILITY_RISK or request["risk"] != CAPABILITY_RISK[capability]:
            raise HomeAssistantError("capability risk does not match the code-owned classification")
        if request["risk"] == "R4":
            raise HomeAssistantError("R4 actions belong exclusively to deterministic HA logic")
        if request["risk"] == "R3" and request["confirmed"] is not True:
            raise HomeAssistantError("R3 action requires one-time confirmation")
        if not isinstance(request["parameters"], dict):
            raise HomeAssistantError("capability parameters must be an object")
        if _contains_forbidden_key(request["parameters"]):
            raise HomeAssistantError("capability parameters contain a forbidden HA target")
        try:
            validate_capability_parameters(capability, request["parameters"])
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc

    def _mapping(self, capability: str, role: str) -> dict[str, Any]:
        mappings = self._entry.options.get(CONF_CAPABILITY_MAPPINGS, {})
        mapping = mappings.get(capability, {}).get(role)
        if not isinstance(mapping, dict):
            raise HomeAssistantError("semantic capability role is not owner-allowlisted")
        return mapping

    def _validate_context(
        self, request: dict[str, Any], mapping: dict[str, Any], role: str
    ) -> None:
        mode = str(self._coordinator.data.get("authority_mode", "off"))
        mapping_version = str(mapping.get("mapping_version", ""))
        if not mapping_version or request["mapping_version"] != mapping_version:
            raise HomeAssistantError("capability mapping version does not match")
        if request["confirmed"]:
            if mode not in {"suggest", "bounded_auto"}:
                raise HomeAssistantError(
                    "current Homeclaw mode does not permit confirmed execution"
                )
        elif mode != "bounded_auto":
            raise HomeAssistantError("autonomous execution requires Bounded Auto")

        house_mode_entity = str(self._entry.options.get(CONF_HOUSE_MODE_ENTITY, ""))
        allowed_modes = mapping.get("allowed_house_modes", [])
        if allowed_modes:
            state = self._hass.states.get(house_mode_entity)
            if state is None or state.state not in allowed_modes:
                raise HomeAssistantError("current house mode violates capability preconditions")
        required_states = mapping.get("required_states", {})
        if not isinstance(required_states, dict):
            raise HomeAssistantError("capability required_states must be an object")
        for entity_id, allowed_states in required_states.items():
            if not isinstance(entity_id, str) or not isinstance(allowed_states, list):
                raise HomeAssistantError("capability state precondition is malformed")
            state = self._hass.states.get(entity_id)
            if state is None or state.state not in {str(item) for item in allowed_states}:
                raise HomeAssistantError(
                    f"current state of {entity_id} violates capability preconditions"
                )
        cooldown = max(0, min(int(mapping.get("cooldown_seconds", 60)), 86400))
        previous = self._last_execution.get((request["capability"], role))
        if previous is not None and (datetime.now(UTC) - previous).total_seconds() < cooldown:
            raise HomeAssistantError("capability cooldown is active")

    def _state_snapshot(self, entity_ids) -> dict[str, str | None]:
        return {
            str(entity_id): (
                self._hass.states.get(str(entity_id)).state
                if self._hass.states.get(str(entity_id)) is not None
                else None
            )
            for entity_id in entity_ids
        }

    def _states_match(self, expected: dict[str, Any]) -> bool:
        for entity_id, allowed_states in expected.items():
            if not isinstance(entity_id, str) or not isinstance(allowed_states, list):
                raise HomeAssistantError("capability postcondition is malformed")
            state = self._hass.states.get(entity_id)
            if state is None or state.state not in {str(item) for item in allowed_states}:
                return False
        return True

    async def _wait_for_states(self, expected: dict[str, Any], timeout_seconds: int) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            if self._states_match(expected):
                return True
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(0.5)

    async def _run_rollback(
        self, mapping: dict[str, Any], variables: dict[str, Any]
    ) -> dict[str, Any] | None:
        rollback = str(mapping.get("rollback_script", ""))
        if not rollback.startswith("script.") or self._hass.states.get(rollback) is None:
            return None
        try:
            await self._hass.services.async_call(
                "script",
                "turn_on",
                {"entity_id": rollback, "variables": variables},
                blocking=True,
            )
            expected = mapping.get("rollback_postconditions", {})
            if not isinstance(expected, dict):
                raise HomeAssistantError("rollback postconditions must be an object")
            succeeded = not expected or await self._wait_for_states(expected, 30)
            return {"succeeded": succeeded, "states": self._state_snapshot(expected)}
        except Exception as exc:
            return {"succeeded": False, "states": {}, "error": str(exc)}


def _canonical_payload(request: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in request.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode()


def _verify_signature(request: dict[str, Any], secret: bytes) -> bool:
    supplied = str(request.get("signature", ""))
    expected = hmac.new(secret, _canonical_payload(request), hashlib.sha256).hexdigest()
    return bool(supplied) and hmac.compare_digest(supplied, expected)


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in FORBIDDEN_KEYS or _contains_forbidden_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(child) for child in value)
    return False
