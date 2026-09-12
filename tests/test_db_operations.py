import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from db_backup import backup_database
from db_integrity import check_integrity


class DatabaseOperationTests(unittest.TestCase):
    def test_integrity_is_read_only_and_backup_includes_database_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "livebarn.db"
            backup = root / "backup" / "livebarn.db"
            with sqlite3.connect(source) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("CREATE TABLE venues (id INTEGER, name TEXT)")
                connection.execute("INSERT INTO venues VALUES (1, 'Synthetic Rink')")
            self.assertEqual(check_integrity(source), "ok")
            backup_database(source, backup)
            self.assertEqual(check_integrity(backup), "ok")
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(backup) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM venues").fetchone()[0], 1)

    def test_cli_reports_missing_database_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.db"
            result = subprocess.run(
                ["python", "db_integrity.py", str(missing)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "query-error")
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
