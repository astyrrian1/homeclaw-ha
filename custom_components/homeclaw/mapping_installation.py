"""Deterministic proof that an exact capability mapping is installed in HA."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_MAPPING_VERSION = re.compile(r"^homeclaw-[a-z0-9_]+-[a-z0-9_]+-v[1-9][0-9]*$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SCRIPT = re.compile(r"^script\.homeclaw_[a-z0-9_]+$")
_STATE_COLLECTIONS = (
    "required_states",
    "postconditions",
    "rollback_postconditions",
)


def mapping_installation_records(
    mappings: dict[str, Any], *, available_entities: set[str]
) -> list[dict[str, str]]:
    """Return hash-bound installation records or reject an incomplete HA contract."""

    records: list[dict[str, str]] = []
    for capability in sorted(mappings):
        roles = mappings[capability]
        if not _IDENTIFIER.fullmatch(capability) or not isinstance(roles, dict):
            raise ValueError("capability mappings must use bounded identifiers and objects")
        for semantic_role in sorted(roles):
            mapping = roles[semantic_role]
            if not _IDENTIFIER.fullmatch(semantic_role) or not isinstance(mapping, dict):
                raise ValueError("semantic role mappings must use bounded identifiers and objects")
            mapping_version = str(mapping.get("mapping_version", ""))
            mapping_sha256 = str(mapping.get("mapping_sha256", ""))
            if not _MAPPING_VERSION.fullmatch(mapping_version):
                raise ValueError("mapping_version is missing or malformed")
            if not _SHA256.fullmatch(mapping_sha256):
                raise ValueError("mapping_sha256 is missing or malformed")

            handler = str(mapping.get("handler_script", ""))
            rollback = str(mapping.get("rollback_script", ""))
            if not _SCRIPT.fullmatch(handler) or not _SCRIPT.fullmatch(rollback):
                raise ValueError("mapping scripts must use the Homeclaw script allowlist")
            referenced_entities = {handler, rollback}
            for collection_name in _STATE_COLLECTIONS:
                collection = mapping.get(collection_name, {})
                if not isinstance(collection, dict):
                    raise ValueError(f"{collection_name} must be an object")
                for entity_id, allowed_states in collection.items():
                    if (
                        not isinstance(entity_id, str)
                        or "." not in entity_id
                        or not isinstance(allowed_states, list)
                        or not allowed_states
                    ):
                        raise ValueError(f"{collection_name} contains a malformed state contract")
                    referenced_entities.add(entity_id)

            missing = sorted(referenced_entities - available_entities)
            if missing:
                raise ValueError(f"capability mapping entities are not installed: {missing}")
            evidence = {
                "schema_version": "1",
                "capability": capability,
                "semantic_role": semantic_role,
                "mapping_version": mapping_version,
                "mapping_sha256": mapping_sha256,
                "handler_script": handler,
                "rollback_script": rollback,
                "referenced_entities": sorted(referenced_entities),
            }
            evidence_sha256 = hashlib.sha256(
                json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            records.append(
                {
                    "capability": capability,
                    "semantic_role": semantic_role,
                    "mapping_version": mapping_version,
                    "mapping_sha256": mapping_sha256,
                    "evidence_sha256": evidence_sha256,
                }
            )
    return records
