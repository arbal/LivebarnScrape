import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from acquisition import plan_event, safe_slug
from go2rtc_config import build_streams, render_json
from schedule_providers.generic_json_provider import GenericJsonScheduleProvider
from schedule_providers.base_provider import ScheduleEvent
from vod import VodClient, VodQuery, VodTransportUnavailable


class FeatureBatchTest(unittest.TestCase):
    def test_generic_schedule_maps_and_preserves_unmapped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.json"
            path.write_text(json.dumps({"events": [
                {"id": "g1", "title": "Fictional A vs Fictional B", "team": "A", "opponent": "B",
                 "venue": "North Rink", "surface": "Main", "start": "2026-01-01T18:00:00-05:00",
                 "end": "2026-01-01T19:00:00-05:00", "event_type": "game"},
                {"id": "u1", "title": "Unmapped", "venue": "Unknown", "start": "2026-01-01T20:00:00Z",
                 "end": "2026-01-01T21:00:00Z"},
            ]}))
            provider = GenericJsonScheduleProvider(path, {"north rink main": 123})
            events = provider.fetch_schedule(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
            self.assertEqual({e.event_id: e.surface_id for e in events}, {"g1": 123, "u1": None})
            self.assertEqual(provider.unmapped_events[0].event_id, "u1")
            self.assertEqual(next(e for e in events if e.event_id == "g1").team, "A")

    def test_generic_schedule_rejects_naive_time(self):
        with self.assertRaises(ValueError):
            from schedule_providers.generic_json_provider import parse_schedule_datetime
            parse_schedule_datetime("2026-01-01T18:00:00")

    def test_planner_has_explicit_window_and_safe_name(self):
        event = ScheduleEvent(123, datetime(2026, 1, 1, 18, tzinfo=timezone.utc), datetime(2026, 1, 1, 19, tzinfo=timezone.utc), "A / B", event_id="g/1", team="A", opponent="B", feed_mode="auto")
        plan = plan_event(event, pre_roll_minutes=10, post_roll_minutes=5)
        self.assertEqual((plan.start_time.hour, plan.end_time.hour), (17, 19))
        self.assertEqual(plan.status, "vod-unconfirmed")
        self.assertNotIn("/", plan.destination_name)
        self.assertEqual(safe_slug("../../A:B"), "A-B")

    def test_vod_transport_fails_explicitly_without_contract(self):
        query = VodQuery(123, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
        with self.assertRaises(VodTransportUnavailable):
            VodClient().query(query)

    def test_go2rtc_config_is_stable_and_credential_free(self):
        output = render_json([{"surface_id": 123, "name": "Rink / One", "feed_modes": ["auto", "pano"]}])
        self.assertIn("proxy/123?mode=auto", output)
        self.assertIn("proxy/123?mode=pano", output)
        self.assertNotIn("password", output.casefold())
        self.assertEqual(len(build_streams([{"surface_id": 123, "name": "Rink / One", "feed_modes": ["auto"]}])["streams"]), 1)


if __name__ == "__main__":
    unittest.main()
