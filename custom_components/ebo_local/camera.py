"""Camera entity — live video from the local bridge (RTSP served by the appliance's mediamtx)."""
from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BRIDGE_RTSP, CONF_NAME, CONF_ROBOT_ID, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    rtsp = entry.data.get(CONF_BRIDGE_RTSP)
    if rtsp:
        async_add_entities([EboLocalCamera(entry, rtsp)])


class EboLocalCamera(Camera):
    """Live H.264/H.265 stream from the robot over the local TUTK bridge (no cloud)."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_has_entity_name = True
    _attr_name = "Live"

    def __init__(self, entry: ConfigEntry, rtsp_url: str) -> None:
        super().__init__()
        self._rtsp = rtsp_url
        self._attr_unique_id = f"{entry.entry_id}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data.get(CONF_ROBOT_ID, entry.entry_id)))},
            name=entry.data.get(CONF_NAME, "EBO"),
            manufacturer="Enabot (unofficial)",
            model="EBO Air 2",
        )

    async def stream_source(self) -> str | None:
        return self._rtsp
