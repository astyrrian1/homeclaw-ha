"""Read-only Homeclaw panel registration and WebSocket boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

PANEL_URL_PATH = "homeclaw"
PANEL_STATIC_PATH = "/homeclaw_static"
DATA_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"
DATA_PANEL_STATIC_REGISTERED = f"{DOMAIN}_panel_static_registered"
DATA_PANEL_WEBSOCKET_REGISTERED = f"{DOMAIN}_panel_websocket_registered"


@callback
@websocket_api.websocket_command({vol.Required("type"): "homeclaw/panel_data"})
def websocket_panel_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return only the bounded, read-only coordinator projection."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        connection.send_error(msg["id"], "not_ready", "Homeclaw is not ready")
        return
    coordinator = next(iter(coordinators.values()))
    if coordinator.data is None:
        connection.send_error(msg["id"], "not_ready", "Homeclaw has no current data")
        return
    connection.send_result(msg["id"], coordinator.data)


async def async_register_homeclaw_panel(hass: HomeAssistant) -> None:
    """Register one local-only resident panel for this HA process."""
    if not hass.data.get(DATA_PANEL_STATIC_REGISTERED):
        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_STATIC_PATH, str(frontend_path), True)]
        )
        hass.data[DATA_PANEL_STATIC_REGISTERED] = True

    if not hass.data.get(DATA_PANEL_WEBSOCKET_REGISTERED):
        websocket_api.async_register_command(hass, websocket_panel_data)
        hass.data[DATA_PANEL_WEBSOCKET_REGISTERED] = True

    if not hass.data.get(DATA_PANEL_REGISTERED):
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="homeclaw-panel",
            sidebar_title="Homeclaw",
            sidebar_icon="mdi:brain",
            module_url=f"{PANEL_STATIC_PATH}/homeclaw-panel.js",
            config={"read_only": True},
            require_admin=False,
        )
        hass.data[DATA_PANEL_REGISTERED] = True


@callback
def async_remove_homeclaw_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel while retaining process-wide registrations."""
    if not hass.data.pop(DATA_PANEL_REGISTERED, False):
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
