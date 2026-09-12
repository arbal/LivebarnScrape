import os
import signal
import socket
import subprocess
import time
import unittest
import urllib.request


class ServingHarnessTests(unittest.TestCase):
    def test_long_stream_does_not_block_health(self):
        environment = os.environ.copy()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = str(probe.getsockname()[1])
        process = subprocess.Popen(
                [
                "/tmp/livebarnscrape-pass-venv/bin/gunicorn",
                "--config", "/dev/null",
                "--workers", "1",
                "--worker-class", "gthread",
                "--threads", "4",
                "--timeout", "10",
                "--bind", f"127.0.0.1:{port}",
                "tests.stream_fixture_app:app",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    urllib.request.urlopen(base + "/health", timeout=1).read()
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                self.fail("fixture Gunicorn did not start")

            with urllib.request.urlopen(base + "/stream", timeout=3) as stream:
                first = stream.read(6)
                started = time.monotonic()
                with urllib.request.urlopen(base + "/health", timeout=3) as health:
                    self.assertEqual(health.status, 200)
                    self.assertLess(time.monotonic() - started, 1.0)
                self.assertEqual(first, b"chunk-")
        finally:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
