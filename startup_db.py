#!/usr/bin/env python3
"""Classify the persisted catalog database without requiring sqlite3 CLI."""

import sqlite3
import sys
from pathlib import Path


def classify_database(path: Path) -> tuple[str, int | None]:
    """Return a safe startup state and optional venue count."""
    if not path.exists():
        return "absent", None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='venues'"
            ).fetchone()
            if table is None:
                return "table-absent", None
            count = connection.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
            return ("populated" if count else "empty"), count
    except (OSError, sqlite3.Error):
        return "query-error", None


def main() -> int:
    state, count = classify_database(Path(sys.argv[1] if len(sys.argv) > 1 else "/data/livebarn.db"))
    if state == "populated":
        print(state, count)
        return 0
    print(state)
    return 2 if state == "query-error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
