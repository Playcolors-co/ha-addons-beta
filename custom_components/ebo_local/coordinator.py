"""Coordinator for Stage 0 SD-recording data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .fileserver import EboFileServer, EboFileServerError
from .models import RecordingDay, StorageDetails
from .tunnel import KalayTunnel

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EboLocalData:
    """Latest SD-card metadata from the file server."""

    storage: StorageDetails
    days: list[RecordingDay]


class EboLocalCoordinator(DataUpdateCoordinator[EboLocalData]):
    """Poll the local SD-card file server through a Kalay tunnel."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, tunnel: KalayTunnel
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} SD recordings",
            update_interval=timedelta(minutes=5),
        )
        self.entry = entry
        self._tunnel = tunnel
        self.client: EboFileServer | None = None

    async def _async_update_data(self) -> EboLocalData:
        try:
            base_url = await self._tunnel.async_open()
            self.client = EboFileServer(
                async_get_clientsession(self.hass), base_url
            )
            storage = await self.client.async_storage_details()
            days = await self.client.async_recording_days()
        except (EboFileServerError, OSError, RuntimeError) as err:
            raise UpdateFailed(str(err)) from err
        return EboLocalData(storage=storage, days=days)

    async def async_close(self) -> None:
        """Close owned transport resources."""
        await self._tunnel.async_close()
