"""Safe event-to-acquisition planning; planning never starts a subprocess."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Optional

from schedule_providers import ScheduleEvent


def safe_slug(value: str, fallback: str = "event") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    value = re.sub(r"-+", "-", value)
    return value[:96] or fallback


@dataclass(frozen=True)
class AcquisitionPlan:
    event_id: str
    surface_id: Optional[int]
    start_time: datetime
    end_time: datetime
    feed_mode: Optional[str]
    status: str
    source: str
    destination_name: str
    reason: Optional[str] = None


def plan_event(event: ScheduleEvent, pre_roll_minutes: int = 0, post_roll_minutes: int = 0) -> AcquisitionPlan:
    if event.start_time.tzinfo is None or event.end_time.tzinfo is None:
        raise ValueError("event times must be timezone-aware")
    start = event.start_time - timedelta(minutes=pre_roll_minutes + event.pre_roll_minutes)
    end = event.end_time + timedelta(minutes=post_roll_minutes + event.post_roll_minutes)
    event_id = event.event_id or f"{event.start_time.isoformat()}-{event.title}"
    title = event.team and event.opponent and f"{event.team}-vs-{event.opponent}" or event.title
    suffix = event.feed_mode or "default"
    destination = f"{start.astimezone().strftime('%Y-%m-%d_%H-%M')}-{safe_slug(title)}-{safe_slug(suffix)}.ts"
    if event.surface_id is None:
        return AcquisitionPlan(str(event_id), None, start, end, event.feed_mode, "unmapped-surface", "none", destination, "no explicit or configured surface mapping")
    return AcquisitionPlan(str(event_id), event.surface_id, start, end, event.feed_mode, "vod-unconfirmed", "official-vod-or-live-proxy", destination, "VOD transport requires approved authenticated contract")
