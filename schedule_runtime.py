"""Configuration and atomic reload helpers for the optional generic schedule."""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from schedule_providers.generic_json_provider import GenericJsonScheduleProvider


@dataclass(frozen=True)
class GenericScheduleConfig:
    source: str
    timezone_name: str = "UTC"
    mappings: Dict[str, int] = None
    timeout: float = 15.0
    max_bytes: int = 2_000_000
    pre_roll_minutes: int = 0
    post_roll_minutes: int = 0

    def __post_init__(self):
        if not self.source.strip():
            raise ValueError("generic schedule source is required")
        scheme = urlparse(self.source).scheme
        if scheme not in {"", "http", "https"}:
            raise ValueError("generic schedule source must be a local path or HTTP(S) URL")
        try:
            ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown schedule timezone: {self.timezone_name}") from exc
        if self.timeout <= 0 or self.max_bytes <= 0:
            raise ValueError("schedule timeout and max_bytes must be positive")
        if self.pre_roll_minutes < 0 or self.post_roll_minutes < 0:
            raise ValueError("pre/post-roll must not be negative")

    @classmethod
    def from_environment(cls, environ: Optional[dict] = None) -> Optional["GenericScheduleConfig"]:
        env = os.environ if environ is None else environ
        source = env.get("GENERIC_SCHEDULE_SOURCE", "").strip()
        if not source:
            return None
        mapping_text = env.get("GENERIC_SCHEDULE_MAPPINGS", "{}")
        try:
            mappings = json.loads(mapping_text)
        except json.JSONDecodeError as exc:
            raise ValueError("GENERIC_SCHEDULE_MAPPINGS must be valid JSON") from exc
        if not isinstance(mappings, dict):
            raise ValueError("GENERIC_SCHEDULE_MAPPINGS must be an object")
        return cls(source, env.get("GENERIC_SCHEDULE_TIMEZONE", "UTC"),
                   {str(k): int(v) for k, v in mappings.items()},
                   float(env.get("GENERIC_SCHEDULE_TIMEOUT", "15")),
                   int(env.get("GENERIC_SCHEDULE_MAX_BYTES", "2000000")),
                   int(env.get("GENERIC_SCHEDULE_PRE_ROLL_MINUTES", "0")),
                   int(env.get("GENERIC_SCHEDULE_POST_ROLL_MINUTES", "0")))

    def provider(self) -> GenericJsonScheduleProvider:
        return GenericJsonScheduleProvider(self.source, self.mappings or {}, self.timeout, max_bytes=self.max_bytes)


def load_generic_snapshot(config: GenericScheduleConfig, now: Optional[datetime] = None):
    """Load one fully validated candidate; exceptions leave the caller's snapshot untouched."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    end = now + timedelta(days=8)
    return config.provider().fetch_schedule(start, end)


class AtomicScheduleSnapshot:
    """Last-known-good schedule holder with explicit attempt/error metadata."""

    def __init__(self):
        self.events = []
        self.last_success: Optional[datetime] = None
        self.last_attempt: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def reload(self, loader: Callable[[], list], now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        self.last_attempt = now
        try:
            candidate = loader()
            if not isinstance(candidate, list):
                raise ValueError("schedule loader did not return a list")
        except Exception as exc:
            self.last_error = str(exc)
            return False
        self.events = list(candidate)
        self.last_success = now
        self.last_error = None
        return True
