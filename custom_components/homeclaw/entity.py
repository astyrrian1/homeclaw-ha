from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class HomeclawEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"homeclaw_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "homeclaw")},
            name="Homeclaw",
            manufacturer="Homeclaw",
            model="Local household intelligence",
        )
