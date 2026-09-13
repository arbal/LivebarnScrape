"""Generate credential-free go2rtc stream configuration fragments."""

from __future__ import annotations

import json
import re
from typing import Iterable, Mapping


def safe_stream_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return name[:80] or "livebarn_surface"


def build_streams(
    surfaces: Iterable[Mapping[str, object]],
    base_url: str = "http://livebarn-manager:5000/proxy",
) -> dict:
    streams = {}
    for surface in surfaces:
        surface_id = int(surface["surface_id"])
        label = str(surface.get("name") or f"surface_{surface_id}")
        modes = surface.get("feed_modes") or ["auto"]
        for mode in modes:
            normalized = str(mode).casefold()
            if normalized not in {"auto", "pano"}:
                raise ValueError(f"unsupported feed mode: {mode}")
            key = safe_stream_name(f"{label}_{normalized}_{surface_id}")
            streams[key] = [f"{base_url.rstrip('/')}/{surface_id}?mode={normalized}"]
    return {"streams": streams}


def build_test_config(surfaces, api_listen="127.0.0.1:1984", rtsp_listen="127.0.0.1:8554"):
    """Build a loopback-only validation config; production callers own binding policy."""
    config = build_streams(surfaces)
    config["api"] = {"listen": api_listen}
    config["rtsp"] = {"listen": rtsp_listen}
    return config


def render_json(surfaces: Iterable[Mapping[str, object]], base_url: str = "http://livebarn-manager:5000/proxy") -> str:
    return json.dumps(build_streams(surfaces, base_url), indent=2, sort_keys=True) + "\n"
