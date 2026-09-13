import unittest
from datetime import datetime, timezone

from schedule_providers.base_provider import ScheduleEvent
from schedule_utils import display_event_title, group_events_by_surface


class ScheduleUtilsTest(unittest.TestCase):
    def test_team_aware_title_is_generic(self):
        event = ScheduleEvent(1, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc), "ignored", team="A", opponent="B")
        self.assertEqual(display_event_title(event), "A vs B")
        self.assertEqual(group_events_by_surface([event])[1][0]["text"], "A vs B")

    def test_unmapped_events_are_not_emitted_as_surface_data(self):
        event = ScheduleEvent(None, datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, 1, tzinfo=timezone.utc), "unmapped")
        self.assertEqual(group_events_by_surface([event]), {})


if __name__ == "__main__":
    unittest.main()
