from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .entity import HomeclawEntity

SENSORS = {
    "active_episode": "Active episode",
    "open_insights": "Open insights",
    "pending_proposals": "Pending proposals",
    "last_decision": "Last decision",
    "decision_latency": "Decision latency",
    "shadow_precision": "Shadow precision",
}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HomeclawSensor(coordinator, key, name) for key, name in SENSORS.items()])


class HomeclawSensor(HomeclawEntity, SensorEntity):
    def __init__(self, coordinator, key: str, name: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
