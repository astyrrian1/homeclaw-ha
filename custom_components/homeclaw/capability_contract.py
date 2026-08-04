"""Pure-Python second validation for named capability parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")


@dataclass(frozen=True)
class CapabilitySpec:
    role_key: str
    required: frozenset[str]
    optional: frozenset[str] = frozenset()


CAPABILITY_SPECS = {
    "ambient_lighting": CapabilitySpec(
        "area_role",
        frozenset({"area_role", "brightness_pct", "duration_minutes"}),
        frozenset({"color_temperature_kelvin"}),
    ),
    "short_recirculation": CapabilitySpec(
        "loop_role", frozenset({"loop_role", "duration_minutes"})
    ),
    "bounded_shade": CapabilitySpec("area_role", frozenset({"area_role", "position_pct"})),
    "adjust_hvac": CapabilitySpec(
        "zone_role", frozenset({"zone_role", "delta_f", "duration_minutes"})
    ),
    "adjust_erv": CapabilitySpec("erv_role", frozenset({"erv_role", "level", "duration_minutes"})),
    "irrigation": CapabilitySpec("zone_role", frozenset({"zone_role", "duration_minutes"})),
    "load_scheduling": CapabilitySpec(
        "load_role",
        frozenset({"load_role", "delay_minutes", "maximum_runtime_minutes"}),
    ),
    "unlock_exterior": CapabilitySpec("access_role", frozenset({"access_role", "reason"})),
    "disarm_alarm": CapabilitySpec("access_role", frozenset({"access_role", "reason"})),
    "open_exterior": CapabilitySpec("access_role", frozenset({"access_role", "reason"})),
    "camera_privacy": CapabilitySpec("access_role", frozenset({"access_role", "reason"})),
    "network_security_change": CapabilitySpec("policy_role", frozenset({"policy_role", "reason"})),
    "emergency_shutdown": CapabilitySpec("playbook_role", frozenset({"playbook_role", "reason"})),
}


def validate_capability_parameters(capability: str, parameters: dict[str, Any]) -> str:
    """Validate an exact normalized schema and return its semantic role."""

    try:
        spec = CAPABILITY_SPECS[capability]
    except KeyError as exc:
        raise ValueError("unsupported capability") from exc
    keys = frozenset(parameters)
    if not spec.required.issubset(keys) or not keys.issubset(spec.required | spec.optional):
        raise ValueError("parameters do not match the exact capability schema")
    role = parameters.get(spec.role_key)
    if not isinstance(role, str) or _ROLE.fullmatch(role) is None:
        raise ValueError("invalid semantic role")

    if capability == "ambient_lighting":
        _integer(parameters, "brightness_pct", 1, 100)
        _integer(parameters, "duration_minutes", 1, 120)
        if "color_temperature_kelvin" in parameters:
            _integer(parameters, "color_temperature_kelvin", 2000, 6500)
    elif capability == "short_recirculation":
        _integer(parameters, "duration_minutes", 1, 20)
    elif capability == "bounded_shade":
        _integer(parameters, "position_pct", 0, 100)
    elif capability == "adjust_hvac":
        _number(parameters, "delta_f", -2.0, 2.0)
        _integer(parameters, "duration_minutes", 5, 120)
    elif capability == "adjust_erv":
        if parameters.get("level") not in {"low", "normal", "high"}:
            raise ValueError("invalid ERV level")
        _integer(parameters, "duration_minutes", 5, 120)
    elif capability == "irrigation":
        _integer(parameters, "duration_minutes", 1, 30)
    elif capability == "load_scheduling":
        _integer(parameters, "delay_minutes", 0, 720)
        _integer(parameters, "maximum_runtime_minutes", 1, 240)
    else:
        reason = parameters.get("reason")
        if not isinstance(reason, str) or not 1 <= len(reason) <= 300:
            raise ValueError("invalid capability reason")
    return role


def _integer(parameters: dict[str, Any], key: str, minimum: int, maximum: int) -> None:
    value = parameters.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{key} exceeds the mechanical capability bound")


def _number(parameters: dict[str, Any], key: str, minimum: float, maximum: float) -> None:
    value = parameters.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} is not numeric")
    if not minimum <= float(value) <= maximum:
        raise ValueError(f"{key} exceeds the mechanical capability bound")
