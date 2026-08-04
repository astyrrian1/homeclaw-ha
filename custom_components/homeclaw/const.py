from typing import Final

DOMAIN: Final = "homeclaw"
DEFAULT_URL: Final = "http://homeclaw.lan:8095"
PLATFORMS: Final = ["binary_sensor", "sensor", "select", "button", "event"]
CONF_EXECUTION_SECRET: Final = "execution_hmac_secret"  # noqa: S105 - configuration key
CONF_CAPABILITY_MAPPINGS: Final = "capability_mappings"
CONF_HOUSE_MODE_ENTITY: Final = "house_mode_entity"
