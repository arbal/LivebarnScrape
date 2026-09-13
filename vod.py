"""Evidence-bounded VOD domain objects and transport boundary.

LiveBarn's current authenticated VOD transport is intentionally not guessed
here.  The normalized model can be tested and populated by a future approved
client implementation without coupling schedule or planning code to JSON.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Sequence


class VodAvailability(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PRIVATE = "private"
    OUTSIDE_RETENTION = "outside-retention"
    AUTH_REQUIRED = "auth-required"


@dataclass(frozen=True)
class VodQuery:
    surface_id: int
    start_time: datetime
    end_time: datetime
    feed_mode: Optional[str] = None

    def __post_init__(self) -> None:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("VOD query times must be timezone-aware")
        if self.end_time <= self.start_time:
            raise ValueError("VOD query end must be after start")


@dataclass(frozen=True)
class VodRecording:
    surface_id: int
    start_time: datetime
    end_time: datetime
    availability: VodAvailability = VodAvailability.UNKNOWN
    feed_mode: Optional[str] = None
    recording_id: Optional[str] = None
    private: bool = False
    duration_seconds: Optional[int] = None


class VodTransportUnavailable(RuntimeError):
    """Raised when the current authenticated VOD contract is unconfirmed."""


class VodClient:
    def query(self, query: VodQuery) -> Sequence[VodRecording]:
        raise VodTransportUnavailable(
            "authenticated LiveBarn VOD transport is not confirmed by current public evidence"
        )
