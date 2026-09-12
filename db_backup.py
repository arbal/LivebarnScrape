#!/usr/bin/env python3
"""Create a transactionally consistent SQLite backup without copying WAL by hand."""

import argparse
import os
import sqlite3
from pathlib import Path


def backup_database(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as source_connection:
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
                destination_connection.execute("PRAGMA quick_check").fetchone()
        os.chmod(destination, 0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        backup_database(args.source, args.destination)
    except (OSError, sqlite3.Error):
        print("backup-error")
        return 2
    print("backup-created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
