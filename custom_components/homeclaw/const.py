from typing import Final

DOMAIN: Final = "homeclaw"
DEFAULT_URL: Final = "http://homeclaw.lan:8095"
PLATFORMS: Final = ["binary_sensor", "sensor", "select", "button", "event"]
CONF_EXECUTION_SECRET: Final = "execution_hmac_secret"  # noqa: S105 - configuration key
CONF_ACTOR_SECRET: Final = "actor_hmac_secret"  # noqa: S105 - configuration key
CONF_ACTOR_MAPPINGS: Final = "actor_mappings"
CONF_NOTIFICATION_SERVICES: Final = "notification_services"
TRANSPORT_ACTOR: Final = {
    "ha_user_id": "homeclaw-ha-integration",
    "resident_id": "homeclaw-ha-integration",
    "role": "ha_integration",
}
CONF_CAPABILITY_MAPPINGS: Final = "capability_mappings"
CONF_HOUSE_MODE_ENTITY: Final = "house_mode_entity"
