import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from acquisition import plan_event
from acquisition_scheduler import evaluate_plan, evaluate_plans
from go2rtc_config import build_streams
from schedule_runtime import AtomicScheduleSnapshot, GenericScheduleConfig, acquisition_settings, load_generic_snapshot
from schedule_providers.generic_json_provider import GenericJsonScheduleProvider
from schedule_utils import display_event_title, group_events_by_surface


class ScheduleRuntimeTest(unittest.TestCase):
    def event_file(self, records):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "events.json"
        path.write_text(json.dumps({"events": records}), encoding="utf-8")
        self.addCleanup(directory.cleanup)
        return path

    def test_configured_manager_candidate_and_last_good_reload(self):
        path = self.event_file([{"id": "e1", "title": "Home vs Away", "venue": "Rink", "surface": "1",
            "start": "2026-01-01T18:00:00Z", "end": "2026-01-01T19:00:00Z"}])
        config = GenericScheduleConfig(str(path), "UTC", {"rink 1": 99})
        snapshot = AtomicScheduleSnapshot()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertTrue(snapshot.reload(lambda: load_generic_snapshot(config, now), now))
        self.assertEqual(snapshot.events[0].surface_id, 99)
        path.write_text("{bad", encoding="utf-8")
        self.assertFalse(snapshot.reload(lambda: load_generic_snapshot(config, now), now))
        self.assertEqual(snapshot.events[0].event_id, "e1")
        self.assertIsNotNone(snapshot.last_error)

    def test_end_to_end_schedule_epg_proxy_plan_dry_run(self):
        path = self.event_file([{"id": "game-1", "title": "Game", "team": "Foxes", "opponent": "Owls",
            "event_type": "game", "venue": "Rink", "surface": "1", "feed_mode": "auto",
            "start": "2026-01-01T18:00:00-05:00", "end": "2026-01-01T19:00:00-05:00"}])
        config = GenericScheduleConfig(str(path), "America/New_York", {"rink 1": 123}, pre_roll_minutes=10, post_roll_minutes=5)
        events = load_generic_snapshot(config, datetime(2026, 1, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(display_event_title(events[0]), "Foxes vs Owls")
        self.assertIn(123, group_events_by_surface(events))
        streams = build_streams([{"surface_id": 123, "name": "Rink 1", "feed_modes": ["auto"]}])
        self.assertIn("proxy/123?mode=auto", streams["streams"]["Rink_1_auto_123"][0])
        plan = plan_event(events[0], pre_roll_minutes=10, post_roll_minutes=5)
        evaluation = evaluate_plan(plan, datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc))
        self.assertEqual(evaluation.state, "active-dry-run")
        self.assertFalse(evaluation.operation["execute"])
        self.assertEqual(len(evaluate_plans([plan, plan], datetime(2026, 1, 1, 23, 30, tzinfo=timezone.utc))), 1)

    def test_invalid_source_and_duplicates_fail_without_partial_state(self):
        path = self.event_file([{"id": "same", "start": "2026-01-01T18:00:00Z", "end": "2026-01-01T19:00:00Z"},
                                {"id": "same", "start": "2026-01-01T20:00:00Z", "end": "2026-01-01T21:00:00Z"}])
        provider = GenericJsonScheduleProvider(path)
        with self.assertRaisesRegex(ValueError, "duplicate event id"):
            provider.fetch_schedule(datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 2, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            GenericScheduleConfig("ftp://example.invalid/events.json")

    def test_real_acquisition_configuration_is_rejected(self):
        self.assertEqual(acquisition_settings({})["execution"], "dry-run-only")
        with self.assertRaisesRegex(ValueError, "real acquisition"):
            acquisition_settings({"ACQUISITION_ENABLED": "true", "ACQUISITION_DRY_RUN": "false"})


if __name__ == "__main__":
    unittest.main()
