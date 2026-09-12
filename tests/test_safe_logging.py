import logging
import unittest

from safe_logging import redact_sensitive


class SafeLoggingTests(unittest.TestCase):
    def test_redacts_canary_fields_and_signed_query_values(self):
        canaries = (
            "password=FAKE-PASSWORD",
            "access_token=FAKE-TOKEN",
            "Authorization: Bearer FAKE-BEARER",
            "pin=1234",
            "https://cdn.example/live.m3u8?token=FAKE-STREAM-TOKEN&x=1",
        )
        result = redact_sensitive(" ".join(canaries))
        for canary in ("FAKE-PASSWORD", "FAKE-TOKEN", "FAKE-BEARER", "1234", "FAKE-STREAM-TOKEN"):
            self.assertNotIn(canary, result)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("[REDACTED]]", result)

    def test_debug_level_does_not_disable_redaction(self):
        logger = logging.getLogger("safe-logging-test")
        record = logger.makeRecord(
            logger.name, logging.DEBUG, __file__, 1,
            "DEBUG access_token=FAKE-DEBUG-TOKEN", (), None
        )
        self.assertNotIn("FAKE-DEBUG-TOKEN", redact_sensitive(record.getMessage()))


if __name__ == "__main__":
    unittest.main()
