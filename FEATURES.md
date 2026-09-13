# Generic schedule, VOD planning, and go2rtc boundary

This document describes the implemented, evidence-bounded feature layer. It
does not claim that the current authenticated LiveBarn VOD transport is known.

## Generic schedule input

`GenericJsonScheduleProvider` accepts either a local JSON file or an HTTP JSON
endpoint. The payload is an array or an object with an `events` array:

```json
{
  "events": [
    {
      "id": "fictional-game-1",
      "title": "Fictional A vs Fictional B",
      "event_type": "game",
      "team": "Fictional A",
      "opponent": "Fictional B",
      "venue": "Example Arena",
      "surface": "Main",
      "start": "2026-01-01T18:00:00-05:00",
      "end": "2026-01-01T19:00:00-05:00",
      "feed_mode": "auto",
      "pre_roll_minutes": 10,
      "post_roll_minutes": 10
    }
  ]
}
```

Times must be timezone-aware ISO-8601 values. Mapping precedence is explicit
`surface_id`, configured `venue + surface`, configured surface, then configured
venue. Unmapped events are retained by the provider for diagnostics and never
silently assigned to a rink.

## VOD and acquisition planning

`vod.py` defines timezone-aware `VodQuery` and normalized `VodRecording`
objects. Its client deliberately raises `VodTransportUnavailable` until the
current authenticated LiveBarn VOD contract is established through an approved
test. Historical libraries are not treated as current API authority.

`acquisition.py` converts an event into a safe, explicit `AcquisitionPlan` with
pre/post-roll, feed mode, sanitized destination name, and states such as
`unmapped-surface` or `vod-unconfirmed`. Creating a plan never starts a
process, downloads media, or contacts LiveBarn.

Product-supported VOD/download, direct segment retrieval, and recording a live
proxy are intentionally separate concepts. Subscription/retention/private
session rules may affect availability and must not be bypassed.

## go2rtc boundary

`go2rtc_config.py` emits credential-free JSON stream fragments using stable
LiveBarnScrape proxy URLs:

```text
LiveBarnScrape /proxy/<surface_id>?mode=auto
    -> go2rtc HTTP MPEG-TS source
    -> go2rtc RTSP/WebRTC outputs
    -> Home Assistant or local consumers
```

The generated names are sanitized and stable per surface/feed. LiveBarn
credentials remain inside LiveBarnScrape. An ffmpeg-backed go2rtc source can
be evaluated separately if direct HTTP MPEG-TS ingest is insufficient. This
repository does not claim fan-out behavior without a go2rtc integration test.

Current official go2rtc documentation lists HTTP TS input, FFmpeg sources, and
RTSP/WebRTC/HLS/MSE outputs. Current Home Assistant documentation describes a
go2rtc integration that can connect to a self-hosted instance and provide a
WebRTC proxy. Those documents support this boundary design, but do not prove
that this repository's exact proxy stream or multi-consumer fan-out works;
`go2rtc` is not installed in the current test environment.

The feature layer is synthetic-testable and disabled from automatic acquisition
by default. It contains no private venue mappings, credentials, signed URLs, or
real schedule data.
