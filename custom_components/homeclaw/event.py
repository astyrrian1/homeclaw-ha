from homeassistant.components.event import EventEntity

from .const import DOMAIN
from .entity import HomeclawEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            HomeclawEvent(coordinator, "insight", "Insight", "insight"),
            HomeclawEvent(coordinator, "action_proposal", "Action proposal", "action_proposal"),
        ]
    )


class HomeclawEvent(HomeclawEntity, EventEntity):
    _attr_event_types = ["created"]

    def __init__(self, coordinator, key: str, name: str, record_type: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._record_type = record_type
        self._seen: set[str] = set()

    def _handle_coordinator_update(self) -> None:
        for item in self.coordinator.data.get("events", []):
            item_id = str(item.get("id", ""))
            if item.get("record_type") == self._record_type and item_id not in self._seen:
                self._seen.add(item_id)
                if self.hass is not None:
                    self._trigger_event("created", item)
        super()._handle_coordinator_update()
