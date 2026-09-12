#!/usr/bin/env python3
"""Run a read-only SQLite integrity check for operational diagnostics."""

import argparse
import sqlite3
from pathlib import Path


def check_integrity(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        result = connection.execute("PRAGMA quick_check").fetchone()
    return str(result[0]) if result else "no-result"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        result = check_integrity(args.database)
    except (OSError, sqlite3.Error):
        print("query-error")
        return 2
    print(result)
    return 0 if result.lower() == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
