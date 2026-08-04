from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import HomeclawEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HomeclawModeButton(coordinator, "pause", "Pause", "off"),
            HomeclawModeButton(coordinator, "resume", "Resume", "observe"),
        ]
    )


class HomeclawModeButton(HomeclawEntity, ButtonEntity):
    def __init__(self, coordinator, key: str, name: str, requested_mode: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._requested_mode = requested_mode

    async def async_press(self) -> None:
        await self.coordinator.client.put(
            "/v1/preferences", {"desired_authority_mode": self._requested_mode}
        )
        await self.coordinator.async_request_refresh()
