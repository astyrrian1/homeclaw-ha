import voluptuous as vol
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import HomeclawClient
from .const import DOMAIN, PLATFORMS
from .coordinator import HomeclawCoordinator
from .execution import CapabilityExecutor


async def _async_reload_entry(hass, entry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass, entry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    client = HomeclawClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_ACCESS_TOKEN]
    )
    coordinator = HomeclawCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    executor = CapabilityExecutor(hass, entry, coordinator)

    async def handle_service(call: ServiceCall) -> None:
        if call.service == "submit_feedback":
            await client.post("/v1/feedback", dict(call.data))
        elif call.service in {"approve_proposal", "reject_proposal"}:
            proposal_id = call.data["proposal_id"]
            operation = "approve" if call.service == "approve_proposal" else "reject"
            await client.post(f"/v1/proposals/{proposal_id}/{operation}", dict(call.data))
        elif call.service == "run_digest":
            await client.post("/v1/digests/run", dict(call.data))
        elif call.service == "forget_memory":
            await client.post("/v1/memory/delete", dict(call.data))
        elif call.service in {"approve_memory", "reject_memory"}:
            candidate_id = call.data["candidate_id"]
            operation = "approve" if call.service == "approve_memory" else "reject"
            await client.post(
                f"/v1/memory/candidates/{candidate_id}/{operation}",
                {key: value for key, value in call.data.items() if key != "candidate_id"},
            )
        elif call.service == "correct_memory":
            claim_id = call.data["claim_id"]
            await client.post(
                f"/v1/memory/claims/{claim_id}/correct",
                {key: value for key, value in call.data.items() if key != "claim_id"},
            )
        elif call.service == "create_standing_intent":
            await client.post("/v1/standing-intents", dict(call.data))
        elif call.service == "cancel_standing_intent":
            intent_id = call.data["intent_id"]
            await client.delete(
                f"/v1/standing-intents/{intent_id}?resident_id={call.data['resident_id']}"
            )
        elif call.service == "set_cognition_program":
            program_id = call.data["program_id"]
            await client.put(
                f"/v1/cognition/programs/{program_id}",
                {key: value for key, value in call.data.items() if key != "program_id"},
            )

    async def execute_capability(call: ServiceCall):
        return await executor.execute(dict(call.data["request"]))

    service_schemas = {
        "submit_feedback": vol.Schema(
            {
                vol.Required("kind"): cv.string,
                vol.Required("resident_id"): cv.string,
                vol.Required("target_id"): cv.string,
                vol.Optional("correction"): cv.string,
            }
        ),
        "approve_proposal": vol.Schema(
            {
                vol.Required("proposal_id"): cv.string,
                vol.Required("resident_id"): cv.string,
                vol.Required("approval_token"): cv.string,
            }
        ),
        "reject_proposal": vol.Schema({vol.Required("proposal_id"): cv.string}),
        "run_digest": vol.Schema({vol.Optional("resident_id"): cv.string}),
        "forget_memory": vol.Schema(
            {
                vol.Required("scope"): cv.string,
                vol.Required("owner_confirmation"): cv.boolean,
                vol.Optional("record_type"): cv.string,
                vol.Optional("record_id"): cv.string,
                vol.Optional("resident_id"): cv.string,
                vol.Optional("before"): cv.string,
            }
        ),
        "approve_memory": vol.Schema(
            {
                vol.Required("candidate_id"): cv.string,
                vol.Required("owner"): cv.string,
                vol.Required("owner_confirmation"): cv.boolean,
                vol.Optional("reason"): cv.string,
            }
        ),
        "reject_memory": vol.Schema(
            {
                vol.Required("candidate_id"): cv.string,
                vol.Required("owner"): cv.string,
                vol.Required("owner_confirmation"): cv.boolean,
                vol.Optional("reason"): cv.string,
            }
        ),
        "correct_memory": vol.Schema(
            {
                vol.Required("claim_id"): cv.string,
                vol.Required("owner"): cv.string,
                vol.Required("owner_confirmation"): cv.boolean,
                vol.Required("value"): object,
                vol.Required("reason"): cv.string,
            }
        ),
        "create_standing_intent": vol.Schema(
            {
                vol.Required("owner_resident_id"): cv.string,
                vol.Required("description"): cv.string,
                vol.Required("trigger_predicates"): dict,
                vol.Required("delivery_target"): cv.string,
                vol.Optional("cooldown_seconds", default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=604800)
                ),
                vol.Required("expires_at"): cv.string,
                vol.Required("resident_confirmation"): cv.boolean,
            }
        ),
        "cancel_standing_intent": vol.Schema(
            {
                vol.Required("intent_id"): cv.string,
                vol.Required("resident_id"): cv.string,
            }
        ),
        "set_cognition_program": vol.Schema(
            {
                vol.Required("program_id"): cv.string,
                vol.Required("mode"): vol.In(["off", "audit", "publish"]),
                vol.Required("sensitivity"): vol.In(["quiet", "normal", "sensitive"]),
                vol.Required("owner"): cv.string,
                vol.Required("owner_confirmation"): cv.boolean,
            }
        ),
    }
    for service, schema in service_schemas.items():
        hass.services.async_register(DOMAIN, service, handle_service, schema=schema)
    hass.services.async_register(
        DOMAIN,
        "execute_capability",
        execute_capability,
        schema=vol.Schema({vol.Required("request"): dict}),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_unload_entry(hass, entry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for service in (
                "submit_feedback",
                "approve_proposal",
                "reject_proposal",
                "run_digest",
                "forget_memory",
                "approve_memory",
                "reject_memory",
                "correct_memory",
                "create_standing_intent",
                "cancel_standing_intent",
                "set_cognition_program",
                "execute_capability",
            ):
                hass.services.async_remove(DOMAIN, service)
    return unloaded
