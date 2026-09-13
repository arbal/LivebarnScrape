"""Small SQLite ledger for dry-run acquisition reconciliation only."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from acquisition import AcquisitionPlan


@dataclass(frozen=True)
class LedgerRow:
    identity: str
    event_id: str
    surface_id: Optional[int]
    feed_mode: Optional[str]
    state: str
    planned_start: str
    planned_end: str
    last_evaluated: str


class DryRunLedger:
    """Persist plan identity/state, never media URLs or execution credentials."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.execute("""CREATE TABLE IF NOT EXISTS acquisition_ledger (
            identity TEXT PRIMARY KEY, event_id TEXT NOT NULL, surface_id INTEGER,
            feed_mode TEXT, state TEXT NOT NULL, planned_start TEXT NOT NULL,
            planned_end TEXT NOT NULL, first_seen TEXT NOT NULL,
            last_evaluated TEXT NOT NULL
        )""")
        return connection

    def reconcile(self, plans: Iterable[AcquisitionPlan], now: datetime) -> list[LedgerRow]:
        if now.tzinfo is None:
            raise ValueError("ledger time must be timezone-aware")
        from acquisition_scheduler import evaluate_plan, plan_identity
        rows = []
        with self._connect() as connection:
            existing = {row[0]: row for row in connection.execute(
                "SELECT identity,event_id,surface_id,feed_mode,state,planned_start,planned_end,first_seen,last_evaluated FROM acquisition_ledger"
            )}
            for plan in plans:
                identity = plan_identity(plan)
                state = evaluate_plan(plan, now).state
                previous = existing.get(identity)
                first_seen = previous[7] if previous else now.isoformat()
                connection.execute("""INSERT INTO acquisition_ledger
                    (identity,event_id,surface_id,feed_mode,state,planned_start,planned_end,first_seen,last_evaluated)
                    VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET
                    state=excluded.state, planned_start=excluded.planned_start,
                    planned_end=excluded.planned_end, last_evaluated=excluded.last_evaluated""",
                    (identity, plan.event_id, plan.surface_id, plan.feed_mode, state,
                     plan.start_time.isoformat(), plan.end_time.isoformat(), first_seen, now.isoformat()))
                rows.append(LedgerRow(identity, plan.event_id, plan.surface_id, plan.feed_mode,
                                      state, plan.start_time.isoformat(), plan.end_time.isoformat(), now.isoformat()))
        return rows

    def rows(self) -> list[LedgerRow]:
        with self._connect() as connection:
            return [LedgerRow(*row) for row in connection.execute(
                "SELECT identity,event_id,surface_id,feed_mode,state,planned_start,planned_end,last_evaluated FROM acquisition_ledger ORDER BY identity"
            )]
