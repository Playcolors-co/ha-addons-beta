"""Async client for the EBO robot's local "Rola" file server (`httpAction/*` on `:9036`).

Reached through a :class:`~.tunnel.KalayTunnel` (the robot exposes this over the Kalay P2P tunnel
only). Every request carries the `EBO-SID` and `VERSION` headers the firmware expects. Endpoints and
their shapes come from the APK decompilation (memory `ebo-lan-http-api`); responses are parsed by
:mod:`.models`, which keeps the raw payload so unmodelled fields survive.

This layer is transport-independent: give it an aiohttp session and a base URL and it works, whether
that URL comes from a manual forward or a future native tunnel. It touches no Home Assistant API, so
it can be exercised against a mock aiohttp server in tests.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

from .models import (
    RecordingDay,
    RecordingFile,
    StorageDetails,
    parse_recording_days,
    parse_recording_files,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15  # seconds; the tunnel adds latency, so keep this generous
DOWNLOAD_CHUNK = 64 * 1024


class EboFileServerError(Exception):
    """Raised when the robot's file server errors or returns an unexpected shape."""


class EboFileServer:
    """Talk to one robot's local file server over an already-open tunnel base URL."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        *,
        sid: str = "",
        version: str = "1",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._base = base_url.rstrip("/")
        self._headers = {"EBO-SID": sid, "VERSION": version}
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    # -- low-level ---------------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    async def _get_json(self, path: str, **params: Any) -> dict[str, Any]:
        try:
            async with self._session.get(
                self._url(path),
                params={k: v for k, v in params.items() if v is not None},
                headers=self._headers,
                timeout=self._timeout,
            ) as resp:
                return await self._read_json(path, resp)
        except aiohttp.ClientError as err:
            raise EboFileServerError(f"GET {path} failed: {err}") from err

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._session.post(
                self._url(path),
                json=body,
                headers=self._headers,
                timeout=self._timeout,
            ) as resp:
                return await self._read_json(path, resp)
        except aiohttp.ClientError as err:
            raise EboFileServerError(f"POST {path} failed: {err}") from err

    @staticmethod
    async def _read_json(path: str, resp: aiohttp.ClientResponse) -> dict[str, Any]:
        if resp.status != 200:
            raise EboFileServerError(f"{path} -> HTTP {resp.status}")
        # The firmware is careless with Content-Type; parse regardless of the header.
        data = await resp.json(content_type=None)
        if not isinstance(data, dict):
            raise EboFileServerError(f"{path} -> expected an object, got {type(data).__name__}")
        return data

    # -- connectivity ------------------------------------------------------------------------

    async def async_probe(self) -> bool:
        """Cheap reachability check: the file server answers ``GET /`` with an index page.

        Returns True on any HTTP response (even 401/404 means the tunnel is up and something is
        listening); raises :class:`EboFileServerError` only when the socket itself fails.
        """
        try:
            async with self._session.get(
                self._url("/"), headers=self._headers, timeout=self._timeout
            ) as resp:
                _LOGGER.debug("EBO file server probe: GET / -> %s", resp.status)
                return True
        except aiohttp.ClientError as err:
            raise EboFileServerError(f"probe failed: {err}") from err

    # -- high-level endpoints ----------------------------------------------------------------

    async def async_storage_details(self) -> StorageDetails:
        return StorageDetails.parse(await self._get_json("httpAction/getStorageDetails"))

    async def async_recording_days(self, tag: int = 0) -> list[RecordingDay]:
        return parse_recording_days(
            await self._get_json("httpAction/getRecordingDays", tag=tag)
        )

    async def async_recording_files(
        self,
        day: str,
        *,
        tag: int = 0,
        count: int = 200,
        direction: int = 0,
        index: int = 0,
    ) -> list[RecordingFile]:
        """List recordings for one day.

        ``count``/``direction``/``index`` mirror the firmware's pagination cursor (memory
        `ebo-lan-http-api`); the defaults ask for a first page of up to 200 items.
        """
        payload = await self._post_json(
            "httpAction/getRecordingAllFiles",
            {
                "day": day,
                "count": count,
                "direction": direction,
                "index": index,
                "tag": tag,
            },
        )
        return parse_recording_files(payload, day=day)

    # -- download ----------------------------------------------------------------------------

    def download_url(self, file: RecordingFile) -> str:
        """Build the download URL for a recording.

        The name may already be a server-relative path (under ``/EBO/Family/``) or a bare filename;
        either way we resolve it against the tunnel base.
        """
        name = file.name
        if name.startswith("http://") or name.startswith("https://"):
            return name
        return self._url(name)

    async def async_stream(
        self, file: RecordingFile, *, start: int | None = None, chunk: int = DOWNLOAD_CHUNK
    ) -> AsyncIterator[bytes]:
        """Stream a recording's bytes, honouring a Range start offset when given.

        Yields chunks; the caller is responsible for consuming the whole iterator so the underlying
        response is released.
        """
        headers = dict(self._headers)
        if start:
            headers["Range"] = f"bytes={start}-"
        url = self.download_url(file)
        try:
            async with self._session.get(url, headers=headers, timeout=None) as resp:
                if resp.status not in (200, 206):
                    raise EboFileServerError(f"download {file.name} -> HTTP {resp.status}")
                async for data in resp.content.iter_chunked(chunk):
                    yield data
        except aiohttp.ClientError as err:
            raise EboFileServerError(f"download {file.name} failed: {err}") from err
