from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import HomeclawEntity

OPTIONS = ["Off", "Observe", "Suggest", "Bounded Auto"]


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([HomeclawAuthoritySelect(hass.data[DOMAIN][entry.entry_id])])


class HomeclawAuthoritySelect(HomeclawEntity, SelectEntity):
    _attr_name = "Authority mode"
    _attr_options = OPTIONS

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "authority_mode")

    @property
    def current_option(self) -> str:
        current = self.coordinator.data.get("authority_mode", "observe")
        return str(current).replace("_", " ").title()

    async def async_select_option(self, option: str) -> None:
        # This requests a desired mode; Homeclaw remains the authority and may reject it.
        await self.coordinator.client.put(
            "/v1/preferences",
            {"desired_authority_mode": option.casefold().replace(" ", "_")},
        )
        await self.coordinator.async_request_refresh()
