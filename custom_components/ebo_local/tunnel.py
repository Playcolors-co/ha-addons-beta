"""Transport abstraction for reaching the robot's `:9036` file server.

The robot's HTTP file server is **not** reachable directly on the LAN (all TCP ports scan closed). The
only way in is a Kalay P2P tunnel that maps a local port to the robot's `:9036`. A `KalayTunnel`
hands the rest of the integration a plain `http://host:port` base URL and hides how that mapping is
established.

Two implementations:

* :class:`NativeKalayTunnel` — the direct-from-HA adapter under test. It starts a local helper process
  that loads the user's TUTK/Kalay SDK, connects to the robot, and maps a loopback port to the
  robot's `:9036`. Home Assistant then talks HTTP to that loopback URL. The helper is intentionally a
  separate process because the vendor SDK is native/proprietary and not loadable as a normal HA
  Python dependency. This class is only a process adapter: it does not prove that the helper can run
  on the HA host architecture, complete a tunnel, or cold-start without cloud. Those proofs live in
  `research/STAGE0-RUN-LOG.md` and `research/ZERO-CLOUD-AUDIT.md`.

* :class:`ManualTunnel` — the mapping already exists because something else runs the Kalay client and
  forwards a local port. This is for tests and protocol work only; the integration config flow uses
  :class:`NativeKalayTunnel`.
"""

from __future__ import annotations

import abc
import asyncio
from dataclasses import dataclass
import os
import re

from .const import KALAY_FILESERVER_PORT


class KalayTunnel(abc.ABC):
    """A source of an HTTP base URL that forwards to the robot's `:9036` file server."""

    @abc.abstractmethod
    async def async_open(self) -> str:
        """Establish the tunnel if needed and return its ``http://host:port`` base URL."""

    async def async_close(self) -> None:
        """Tear the tunnel down. Default is a no-op (nothing owned)."""
        return None


@dataclass(slots=True)
class ManualTunnel(KalayTunnel):
    """A tunnel that is already established out-of-band; we just point at ``host:port``.

    Use when a Kalay client running elsewhere maps a local port to the robot's `:9036`. This class
    owns nothing and opens nothing — it only formats the base URL.
    """

    host: str
    port: int

    async def async_open(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass(slots=True)
class NativeKalayTunnel(KalayTunnel):
    """Start the local Kalay helper and return the mapped file-server URL.

    Helper contract:
    - read credentials from the environment below;
    - connect to the robot over Kalay, preferably by first proving LAN discovery/connection;
    - map `EBO_LOCAL_PORT` on 127.0.0.1 to `EBO_REMOTE_PORT` on the robot;
    - print `READY http://127.0.0.1:<port>` on stdout, then stay alive until terminated.
    """

    helper: str
    uid: str
    license_key: str
    identity: str
    token: str
    local_port: int
    remote_port: int = KALAY_FILESERVER_PORT
    startup_timeout: int = 30

    _process: asyncio.subprocess.Process | None = None
    _base_url: str | None = None

    async def async_open(self) -> str:
        if self._base_url is not None and self._process is not None:
            if self._process.returncode is None:
                return self._base_url
            self._base_url = None
            self._process = None

        env = dict(os.environ)
        env.update(
            {
                "EBO_UID": self.uid,
                "EBO_LICENSE": self.license_key,
                "EBO_IDENTITY": self.identity,
                "EBO_TOKEN": self.token,
                "EBO_LOCAL_PORT": str(self.local_port),
                "EBO_REMOTE_PORT": str(self.remote_port),
            }
        )
        self._process = await asyncio.create_subprocess_exec(
            self.helper,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=self.startup_timeout
            )
        except TimeoutError as err:
            await self.async_close()
            raise RuntimeError("Kalay helper did not become ready") from err

        text = line.decode(errors="replace").strip()
        match = re.search(r"READY\s+(http://\S+)", text)
        if not match:
            await self.async_close()
            raise RuntimeError(f"Kalay helper returned unexpected startup line: {text}")
        self._base_url = match.group(1).rstrip("/")
        return self._base_url

    async def async_close(self) -> None:
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None
        self._base_url = None
