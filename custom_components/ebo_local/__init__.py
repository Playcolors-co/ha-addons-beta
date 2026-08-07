"""EBO Local — a local-first Home Assistant integration for the Enabot EBO Air 2.

Two local surfaces, no cloud:
  * SD recordings over the Kalay tunnel (Stage 0) — the `EboLocalCoordinator` + file server.
  * Live control/telemetry/video over the TUTK bridge appliance (`ebo_bridge_air2` + `bridge_host`,
    running on the LAN, e.g. the Proxmox CT under qemu) — the `EboBridgeCoordinator` + HTTP/RTSP.

The bridge is optional: if `bridge_url` is not configured, only the SD surface is set up.
SECRETS: all credentials come from the config entry / the bridge appliance — never hardcoded here.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .bridge_client import EboBridgeClient, EboBridgeCoordinator
from .const import (
    CONF_BRIDGE_RTSP,
    CONF_BRIDGE_URL,
    CONF_TUNNEL_HELPER,
    CONF_TUNNEL_LOCAL_PORT,
    CONF_TUTK_IDENTITY,
    CONF_TUTK_LICENSE,
    CONF_TUTK_TOKEN,
    CONF_TUTK_UID,
    DOMAIN,
)
from .coordinator import EboLocalCoordinator
from .services import async_setup_services, async_unload_services
from .tunnel import NativeKalayTunnel

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CAMERA]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one robot from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # --- SD recordings (Stage 0) ---
    tunnel = NativeKalayTunnel(
        helper=entry.data[CONF_TUNNEL_HELPER],
        uid=entry.data[CONF_TUTK_UID],
        license_key=entry.data[CONF_TUTK_LICENSE],
        identity=entry.data[CONF_TUTK_IDENTITY],
        token=entry.data[CONF_TUTK_TOKEN],
        local_port=entry.data[CONF_TUNNEL_LOCAL_PORT],
    )
    sd = EboLocalCoordinator(hass, entry, tunnel)
    await sd.async_config_entry_first_refresh()

    # --- local bridge (control / telemetry / video) — optional ---
    bridge_coord: EboBridgeCoordinator | None = None
    bridge_client: EboBridgeClient | None = None
    if entry.data.get(CONF_BRIDGE_URL):
        bridge_client = EboBridgeClient(hass, entry.data[CONF_BRIDGE_URL])
        bridge_coord = EboBridgeCoordinator(hass, entry, bridge_client)
        await bridge_coord.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "sd": sd,
        "bridge_coord": bridge_coord,
        "bridge_client": bridge_client,
        "rtsp": entry.data.get(CONF_BRIDGE_RTSP),
    }

    await async_setup_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Tear down a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data is not None:
            sd = data.get("sd")
            if sd is not None:
                await sd.async_close()
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
    return ok
