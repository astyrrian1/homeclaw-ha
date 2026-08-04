from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN
from .entity import HomeclawEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HomeclawBinarySensor(coordinator, "ready", "Ready"),
            HomeclawBinarySensor(coordinator, "inference_available", "Inference available"),
        ]
    )


class HomeclawBinarySensor(HomeclawEntity, BinarySensorEntity):
    def __init__(self, coordinator, key: str, name: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get(self._key, False))
