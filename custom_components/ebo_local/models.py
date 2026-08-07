"""Data models and parsers for the EBO robot's local "Rola" file server.

Pure Python — no Home Assistant, no aiohttp — so it is trivially unit-testable and reusable by any
transport. These parse the JSON the robot returns on its `httpAction/*` endpoints (reachable only
through the Kalay tunnel to `:9036`; see ../../ROADMAP.md and memory `ebo-lan-http-api`).

Field names below are defensive: the exact keys the Air 2 firmware emits were only partially observed
during the reverse-engineering phase, so every parser keeps the untouched `raw` payload and reads
known keys with fallbacks. When a real capture pins a field name down, tighten the corresponding
`_first(...)` list — don't drop `raw`, other code may rely on a key we haven't modelled yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _first(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the first present, non-None value among ``keys`` in ``d``."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class StorageDetails:
    """Result of ``GET httpAction/getStorageDetails``.

    Counts are number-of-items; ``used``/``total`` are bytes (unverified unit — the firmware may
    report KiB; treat as opaque capacity numbers until a real capture confirms).
    """

    pic: int | None
    video: int | None
    task: int | None
    used: int | None
    total: int | None
    status: int | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def parse(cls, payload: dict[str, Any]) -> "StorageDetails":
        return cls(
            pic=_int(_first(payload, "pic", "picNum")),
            video=_int(_first(payload, "video", "videoNum")),
            task=_int(_first(payload, "task", "taskNum")),
            used=_int(_first(payload, "used", "usedSize", "use")),
            total=_int(_first(payload, "total", "totalSize")),
            status=_int(_first(payload, "status", "code")),
            raw=payload,
        )


@dataclass(slots=True)
class RecordingDay:
    """One entry from ``GET httpAction/getRecordingDays``.

    ``day`` is the raw day token the firmware uses (e.g. ``"20260801"`` or ``"2026-08-01"``); pass it
    back verbatim to ``getRecordingAllFiles`` — do not reformat it.
    """

    day: str
    count: int | None
    raw: Any = field(default=None, repr=False)

    @classmethod
    def parse_one(cls, item: Any) -> "RecordingDay | None":
        # The list may hold plain day strings, or dicts with a day + a per-day file count.
        if isinstance(item, str):
            return cls(day=item, count=None, raw=item)
        if isinstance(item, dict):
            day = _first(item, "day", "date", "dayStr", "name")
            if day is None:
                return None
            return cls(
                day=str(day),
                count=_int(_first(item, "count", "num", "fileNum", "videoNum")),
                raw=item,
            )
        return None


def parse_recording_days(payload: dict[str, Any]) -> list[RecordingDay]:
    """Parse a ``getRecordingDays`` payload into a list of days (order preserved)."""
    raw_list = _first(payload, "list", "days", "dayList", default=[]) or []
    out: list[RecordingDay] = []
    for item in raw_list:
        day = RecordingDay.parse_one(item)
        if day is not None:
            out.append(day)
    return out


@dataclass(slots=True)
class RecordingFile:
    """One recording, from ``getRecordingAllFiles`` / ``getMedialFiles``.

    ``name`` is the identifier the download endpoint expects (a filename or server-relative path,
    typically under ``/EBO/Family/``). ``start``/``end`` are epoch seconds when present; ``size`` is
    bytes. Everything stays in ``raw`` for fields we haven't modelled.
    """

    name: str
    day: str | None
    start: int | None
    end: int | None
    size: int | None
    duration: int | None
    raw: Any = field(default=None, repr=False)

    @classmethod
    def parse_one(cls, item: Any, *, day: str | None = None) -> "RecordingFile | None":
        if not isinstance(item, dict):
            return None
        name = _first(item, "name", "fileName", "file", "path", "url")
        if name is None:
            return None
        return cls(
            name=str(name),
            day=_first(item, "day", "date", default=day),
            start=_int(_first(item, "start", "startTime", "beginTime", "time")),
            end=_int(_first(item, "end", "endTime", "stopTime")),
            size=_int(_first(item, "size", "fileSize", "length")),
            duration=_int(_first(item, "duration", "durationTime", "len")),
            raw=item,
        )


def parse_recording_files(
    payload: dict[str, Any], *, day: str | None = None
) -> list[RecordingFile]:
    """Parse a ``getRecordingAllFiles`` payload into a list of files (order preserved)."""
    raw_list = _first(payload, "list", "files", "fileList", "data", default=[]) or []
    out: list[RecordingFile] = []
    for item in raw_list:
        rec = RecordingFile.parse_one(item, day=day)
        if rec is not None:
            out.append(rec)
    return out
