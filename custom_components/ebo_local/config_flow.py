"""Config flow for EBO Local.

Collects what the local surfaces need: the robot id and the TUTK/Kalay credentials (which the user
reads from their own vendor account — this project does not ship them). Skeleton: it stores the input
and creates one device per robot; it does not yet reach the robot.

SECRETS RULE: credentials are stored by Home Assistant in the config entry — never committed here.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_BRIDGE_RTSP,
    CONF_BRIDGE_URL,
    CONF_NAME,
    CONF_ROBOT_ID,
    CONF_TUNNEL_HELPER,
    CONF_TUNNEL_LOCAL_PORT,
    CONF_TUTK_IDENTITY,
    CONF_TUTK_LICENSE,
    CONF_TUTK_TOKEN,
    CONF_TUTK_UID,
    DEFAULT_TUNNEL_HELPER,
    DEFAULT_TUNNEL_LOCAL_PORT,
    DOMAIN,
)


class EboLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a local EBO robot."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(str(user_input[CONF_ROBOT_ID]).strip())
            self._abort_if_unique_id_configured()
            # TODO(Stage 0): before creating the entry, open the Kalay tunnel and confirm :9036
            # answers, so bad credentials fail here instead of silently later.
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or "EBO", data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="EBO"): str,
                vol.Required(CONF_ROBOT_ID): str,
                vol.Required(CONF_TUTK_UID): str,
                vol.Required(CONF_TUTK_LICENSE): str,
                vol.Required(CONF_TUTK_IDENTITY): str,
                vol.Required(CONF_TUTK_TOKEN): str,
                vol.Required(CONF_TUNNEL_HELPER, default=DEFAULT_TUNNEL_HELPER): str,
                vol.Required(
                    CONF_TUNNEL_LOCAL_PORT, default=DEFAULT_TUNNEL_LOCAL_PORT
                ): int,
                # Optional: the local bridge appliance (control / telemetry / video). Leave blank
                # for SD-only. e.g. http://192.168.30.9:8099 and rtsp://192.168.30.9:8554/ebo
                vol.Optional(CONF_BRIDGE_URL): str,
                vol.Optional(CONF_BRIDGE_RTSP): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
