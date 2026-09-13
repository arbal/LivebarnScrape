"""Generic, dependency-light JSON schedule ingestion.

The provider accepts a local JSON file or HTTP URL.  It deliberately requires
timezone-aware ISO-8601 timestamps and explicit/configured surface mappings;
ambiguous venue names are never guessed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

from .base_provider import ScheduleEvent, ScheduleProvider

logger = logging.getLogger(__name__)


def _normal_name(value: str) -> str:
    return " ".join(value.casefold().split())


def parse_schedule_datetime(value: str) -> datetime:
    """Parse an aware ISO-8601 timestamp; reject ambiguous naive values."""
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed


class GenericJsonScheduleProvider(ScheduleProvider):
    """Load generic event records from a JSON file or HTTP endpoint."""

    def __init__(
        self,
        source: str | Path,
        mappings: Optional[Dict[str, int]] = None,
        timeout: float = 15.0,
        max_bytes: int = 2_000_000,
        name: str = "Generic JSON schedule",
    ) -> None:
        self.source = str(source)
        self.timeout = timeout
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("timeout and max_bytes must be positive")
        self.max_bytes = max_bytes
        self._name = name
        self._mappings = {_normal_name(k): int(v) for k, v in (mappings or {}).items()}
        self.unmapped_events: List[ScheduleEvent] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def surface_mappings(self) -> Dict[str, int]:
        return dict(self._mappings)

    def _read(self) -> object:
        parsed = urlparse(self.source)
        if parsed.scheme in {"http", "https"}:
            response = requests.get(self.source, timeout=self.timeout)
            response.raise_for_status()
            payload = response.content
            if len(payload) > self.max_bytes:
                raise ValueError("schedule response exceeds configured size limit")
            return json.loads(payload.decode("utf-8"))
        if parsed.scheme:
            raise ValueError("schedule source must be a local path or HTTP(S) URL")
        path = Path(self.source)
        payload = path.read_bytes()
        if len(payload) > self.max_bytes:
            raise ValueError("schedule file exceeds configured size limit")
        return json.loads(payload.decode("utf-8"))

    def fetch_schedule(self, start_date: datetime, end_date: datetime) -> List[ScheduleEvent]:
        payload = self._read()
        records = payload.get("events") if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            raise ValueError("schedule JSON must be an array or an object with events")
        if start_date.tzinfo is None or end_date.tzinfo is None:
            raise ValueError("schedule query bounds must include a timezone")

        output: List[ScheduleEvent] = []
        self.unmapped_events = []
        seen_ids = set()
        seen_semantic = set()
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("each schedule event must be an object")
            start = parse_schedule_datetime(record["start"])
            end = parse_schedule_datetime(record["end"])
            if end <= start:
                raise ValueError("event end must be after start")
            event_id = str(record["id"]) if record.get("id") is not None else None
            semantic_key = (start, end, str(record.get("title") or "Untitled event"), record.get("venue"), record.get("surface"))
            if event_id and event_id in seen_ids:
                raise ValueError(f"duplicate event id: {event_id}")
            if semantic_key in seen_semantic:
                raise ValueError("duplicate equivalent schedule event")
            if event_id:
                seen_ids.add(event_id)
            seen_semantic.add(semantic_key)
            if end <= start_date or start >= end_date:
                continue
            explicit = record.get("surface_id")
            venue = record.get("venue")
            surface = record.get("surface")
            mapping_keys = []
            if venue and surface:
                mapping_keys.append(_normal_name(f"{venue} {surface}"))
            if surface:
                mapping_keys.append(_normal_name(str(surface)))
            if venue:
                mapping_keys.append(_normal_name(str(venue)))
            surface_id = int(explicit) if explicit is not None else next((self._mappings[key] for key in mapping_keys if key in self._mappings), None)
            event = ScheduleEvent(
                surface_id=surface_id,
                start_time=start,
                end_time=end,
                title=str(record.get("title") or "Untitled event"),
                description=record.get("description"),
                event_type=record.get("event_type"),
                raw_data={k: v for k, v in record.items() if k not in {"password", "token", "pin"}},
                event_id=event_id,
                team=record.get("team"),
                opponent=record.get("opponent"),
                venue=record.get("venue"),
                surface_name=record.get("surface"),
                feed_mode=record.get("feed_mode"),
                pre_roll_minutes=int(record.get("pre_roll_minutes", 0)),
                post_roll_minutes=int(record.get("post_roll_minutes", 0)),
            )
            output.append(event)
            if surface_id is None:
                self.unmapped_events.append(event)
        output.sort(key=lambda event: (event.start_time, event.event_id or ""))
        return output
