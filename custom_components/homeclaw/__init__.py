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
                "execute_capability",
            ):
                hass.services.async_remove(DOMAIN, service)
    return unloaded
