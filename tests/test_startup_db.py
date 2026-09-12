import sqlite3
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from startup_db import classify_database


class StartupDatabaseTests(unittest.TestCase):
    def test_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(classify_database(Path(directory) / "missing.db"), ("absent", None))

    def test_missing_table_and_empty_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "livebarn.db"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE other (id INTEGER)")
            self.assertEqual(classify_database(path), ("table-absent", None))
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE venues (id INTEGER)")
            self.assertEqual(classify_database(path), ("empty", 0))

    def test_populated_table(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "livebarn.db"
            with sqlite3.connect(path) as connection:
                connection.execute("CREATE TABLE venues (id INTEGER)")
                connection.executemany("INSERT INTO venues VALUES (?)", [(1,), (2,)])
            self.assertEqual(classify_database(path), ("populated", 2))

    def test_malformed_database_is_query_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "livebarn.db"
            path.write_text("not a sqlite database", encoding="utf-8")
            self.assertEqual(classify_database(path), ("query-error", None))

    def test_entrypoint_query_error_fails_without_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.db"
            path.write_text("not a sqlite database", encoding="utf-8")
            environment = os.environ.copy()
            environment["DB_PATH"] = str(path)
            result = subprocess.run(
                ["bash", "entrypoint.sh"],
                cwd=Path(__file__).parent.parent,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to rebuild", result.stdout)
            self.assertNotIn("Building venue catalog", result.stdout)
