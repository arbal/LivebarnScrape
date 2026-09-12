import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from credential_store import (
    clear_saved_credentials,
    get_credential_status,
    resolve_credentials,
    save_credentials,
)


class CredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "livebarn.db"
        self.environment = {
            "LIVEBARN_EMAIL": "env@example.com",
            "LIVEBARN_PASSWORD": "environment-secret",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_environment_credentials_are_used_without_override(self):
        credentials = resolve_credentials(self.db_path, self.environment)

        self.assertEqual(credentials["source"], "environment")
        self.assertEqual(credentials["email"], "env@example.com")

    def test_saved_credentials_override_environment(self):
        save_credentials(self.db_path, "admin@example.com", "admin-secret")

        credentials = resolve_credentials(self.db_path, self.environment)

        self.assertEqual(credentials["source"], "admin")
        self.assertEqual(credentials["password"], "admin-secret")

    def test_clearing_override_restores_environment(self):
        save_credentials(self.db_path, "admin@example.com", "admin-secret")
        clear_saved_credentials(self.db_path)

        credentials = resolve_credentials(self.db_path, self.environment)

        self.assertEqual(credentials["source"], "environment")

    def test_status_never_contains_password(self):
        save_credentials(self.db_path, "admin@example.com", "admin-secret")

        status = get_credential_status(self.db_path, self.environment)
        serialized = json.dumps(status)

        self.assertEqual(status["email_hint"], "a***@example.com")
        self.assertNotIn("admin-secret", serialized)
        self.assertNotIn("environment-secret", serialized)

    def test_partial_environment_credentials_are_rejected(self):
        with self.assertRaises(ValueError):
            resolve_credentials(
                self.db_path,
                {"LIVEBARN_EMAIL": "env@example.com", "LIVEBARN_PASSWORD": ""},
            )

    def test_saving_new_credentials_clears_cached_oauth_session(self):
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "CREATE TABLE livebarn_oauth_session (id INTEGER PRIMARY KEY)"
            )
            connection.execute("INSERT INTO livebarn_oauth_session VALUES (1)")
        save_credentials(self.db_path, "new@example.com", "new-fake-secret")
        with sqlite3.connect(self.db_path) as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM livebarn_oauth_session"
            ).fetchone())


if __name__ == "__main__":
    unittest.main()
