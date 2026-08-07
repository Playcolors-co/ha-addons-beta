"""Async client + coordinator for the local bridge appliance (ebo_bridge_air2 + bridge_host).

The bridge host runs on the LAN (e.g. the Proxmox CT under qemu) and exposes:
    GET  /telemetry           -> {"battery": {...}, "ts": int}
    POST /drive   {lx,ly,rx,ry,buttons}
    POST /stop
    POST /command {opcode}
Video is a separate RTSP URL (mediamtx) consumed by the camera entity.

No credentials here: the bridge host holds them (from HA config, passed to the appliance).
"""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import TELEMETRY_INTERVAL_S

_LOGGER = logging.getLogger(__name__)


class EboBridgeClient:
    """Thin HTTP client to the bridge host."""

    def __init__(self, hass: HomeAssistant, base_url: str) -> None:
        self._session = async_get_clientsession(hass)
        self._base = base_url.rstrip("/")

    async def async_telemetry(self) -> dict:
        async with self._session.get(f"{self._base}/telemetry", timeout=10) as r:
            r.raise_for_status()
            return await r.json(content_type=None)

    async def async_drive(self, lx=0.0, ly=0.0, rx=0.0, ry=0.0, buttons=0) -> None:
        body = {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "buttons": buttons}
        async with self._session.post(f"{self._base}/drive", json=body, timeout=10) as r:
            r.raise_for_status()

    async def async_stop(self) -> None:
        async with self._session.post(f"{self._base}/stop", timeout=10) as r:
            r.raise_for_status()

    async def async_command(self, opcode: int) -> None:
        async with self._session.post(f"{self._base}/command", json={"opcode": opcode}, timeout=10) as r:
            r.raise_for_status()


class EboBridgeCoordinator(DataUpdateCoordinator[dict]):
    """Poll the bridge host for telemetry (battery, status)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: EboBridgeClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} telemetry",
            update_interval=timedelta(seconds=TELEMETRY_INTERVAL_S),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_telemetry()
        except Exception as err:  # noqa: BLE001 - surface as UpdateFailed
            raise UpdateFailed(f"bridge telemetry failed: {err}") from err
