import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from acquisition import AcquisitionPlan
from acquisition_ledger import DryRunLedger


class AcquisitionLedgerTest(unittest.TestCase):
    def test_restart_is_idempotent_and_preserves_terminal_state(self):
        now = datetime(2026, 1, 1, 20, tzinfo=timezone.utc)
        plan = AcquisitionPlan("game-1", 123, now - timedelta(hours=2), now - timedelta(hours=1), "auto", "vod-unconfirmed", "none", "game.ts")
        with tempfile.TemporaryDirectory() as directory:
            first = DryRunLedger(f"{directory}/state.db").reconcile([plan], now)
            second = DryRunLedger(f"{directory}/state.db").reconcile([plan], now + timedelta(minutes=1))
            self.assertEqual(first[0].state, "completed-dry-run")
            self.assertEqual(second[0].state, "completed-dry-run")
            self.assertEqual(len(DryRunLedger(f"{directory}/state.db").rows()), 1)

    def test_auto_and_pano_are_distinct_identities(self):
        now = datetime(2026, 1, 1, 18, tzinfo=timezone.utc)
        plans = [AcquisitionPlan("game-1", 123, now, now + timedelta(hours=1), mode, "vod-unconfirmed", "none", f"{mode}.ts") for mode in ("auto", "pano")]
        with tempfile.TemporaryDirectory() as directory:
            rows = DryRunLedger(f"{directory}/state.db").reconcile(plans, now)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len({row.identity for row in rows}), 2)


if __name__ == "__main__":
    unittest.main()
