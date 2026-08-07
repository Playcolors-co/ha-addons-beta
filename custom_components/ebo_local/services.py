"""Home Assistant services for Stage 0 SD recordings."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import EboLocalCoordinator
from .fileserver import EboFileServerError
from .models import RecordingFile

SERVICE_REFRESH_RECORDINGS = "refresh_recordings"
SERVICE_DOWNLOAD_RECORDING = "download_recording"
SERVICE_DRIVE = "drive"
SERVICE_STOP = "stop"
SERVICE_COMMAND = "command"

ATTR_ENTRY_ID = "entry_id"
ATTR_FILE_NAME = "file_name"
ATTR_TARGET_NAME = "target_name"
ATTR_LX = "lx"
ATTR_LY = "ly"
ATTR_RX = "rx"
ATTR_RY = "ry"
ATTR_OPCODE = "opcode"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register EBO Local services once."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH_RECORDINGS):
        return

    async def refresh(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call.data)
        await coordinator.async_request_refresh()

    async def download(call: ServiceCall) -> None:
        coordinator = _coordinator_from_call(hass, call.data)
        if coordinator.client is None:
            await coordinator.async_request_refresh()
        if coordinator.client is None:
            raise EboFileServerError("File server client is not ready")

        file_name = call.data[ATTR_FILE_NAME]
        target_name = call.data.get(ATTR_TARGET_NAME) or Path(file_name).name
        target_name = _SAFE_NAME.sub("_", target_name).strip("._") or "recording"
        target_dir = Path(hass.config.path("www", DOMAIN, coordinator.entry.entry_id))
        await hass.async_add_executor_job(_prepare_download_target, target_dir, target_name)
        target_path = target_dir / target_name

        async for chunk in coordinator.client.async_stream(
            RecordingFile(
                name=file_name,
                day=None,
                start=None,
                end=None,
                size=None,
                duration=None,
            )
        ):
            await hass.async_add_executor_job(_append_bytes, target_path, chunk)

    async def drive(call: ServiceCall) -> None:
        client = _bridge_client_from_call(hass, call.data)
        await client.async_drive(
            lx=float(call.data.get(ATTR_LX, 0.0)),
            ly=float(call.data.get(ATTR_LY, 0.0)),
            rx=float(call.data.get(ATTR_RX, 0.0)),
            ry=float(call.data.get(ATTR_RY, 0.0)),
        )

    async def stop(call: ServiceCall) -> None:
        await _bridge_client_from_call(hass, call.data).async_stop()

    async def command(call: ServiceCall) -> None:
        await _bridge_client_from_call(hass, call.data).async_command(int(call.data[ATTR_OPCODE]))

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_RECORDINGS,
        refresh,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DOWNLOAD_RECORDING,
        download,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ENTRY_ID): str,
                vol.Required(ATTR_FILE_NAME): str,
                vol.Optional(ATTR_TARGET_NAME): str,
            }
        ),
    )
    _unit = vol.All(vol.Coerce(float), vol.Range(min=-1.0, max=1.0))
    hass.services.async_register(
        DOMAIN,
        SERVICE_DRIVE,
        drive,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_ENTRY_ID): str,
                vol.Optional(ATTR_LX): _unit,
                vol.Optional(ATTR_LY): _unit,
                vol.Optional(ATTR_RX): _unit,
                vol.Optional(ATTR_RY): _unit,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP, stop, schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): str})
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_COMMAND,
        command,
        schema=vol.Schema(
            {vol.Optional(ATTR_ENTRY_ID): str, vol.Required(ATTR_OPCODE): vol.Coerce(int)}
        ),
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove EBO Local services."""
    for name in (
        SERVICE_REFRESH_RECORDINGS,
        SERVICE_DOWNLOAD_RECORDING,
        SERVICE_DRIVE,
        SERVICE_STOP,
        SERVICE_COMMAND,
    ):
        hass.services.async_remove(DOMAIN, name)


def _container_from_call(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    containers: dict[str, dict[str, Any]] = hass.data.get(DOMAIN, {})
    entry_id = data.get(ATTR_ENTRY_ID)
    if entry_id:
        return containers[entry_id]
    if len(containers) != 1:
        raise ValueError("entry_id is required when multiple EBO Local entries exist")
    return next(iter(containers.values()))


def _coordinator_from_call(
    hass: HomeAssistant, data: dict[str, Any]
) -> EboLocalCoordinator:
    return _container_from_call(hass, data)["sd"]


def _bridge_client_from_call(hass: HomeAssistant, data: dict[str, Any]):
    client = _container_from_call(hass, data).get("bridge_client")
    if client is None:
        raise ValueError("No local bridge configured for this robot (set bridge_url)")
    return client


def _append_bytes(path: Path, chunk: bytes) -> None:
    with path.open("ab") as file:
        file.write(chunk)


def _prepare_download_target(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(b"")
