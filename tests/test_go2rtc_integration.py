"""Optional real go2rtc test; core CI remains independent of the binary."""

import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from go2rtc_config import build_test_config


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@unittest.skipUnless(os.getenv("RUN_GO2RTC_INTEGRATION") == "1", "set RUN_GO2RTC_INTEGRATION=1")
class Go2RTCIntegrationTest(unittest.TestCase):
    def test_http_mpegts_to_rtsp_fans_out(self):
        binary = shutil.which("go2rtc") or "/usr/local/bin/go2rtc"
        if not Path(binary).exists() or not shutil.which("ffmpeg"):
            self.skipTest("go2rtc and ffmpeg are required")
        with tempfile.TemporaryDirectory(prefix="go2rtc-test-") as directory:
            root = Path(directory)
            fixture = root / "fixture.ts"
            config = root / "go2rtc.json"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "testsrc=size=320x180:rate=10", "-t", "5", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-f", "mpegts", str(fixture),
            ], check=True)
            payload = fixture.read_bytes()
            connections = []

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    connections.append(self.client_address)
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp2t")
                    self.end_headers()
                    try:
                        while True:
                            self.wfile.write(payload)
                            self.wfile.flush()
                            time.sleep(0.02)
                    except OSError:
                        pass

                def log_message(self, *_args):
                    pass

            source = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            source_thread = threading.Thread(target=source.serve_forever, daemon=True)
            source_thread.start()
            api_port, rtsp_port = _free_port(), _free_port()
            config.write_text(json.dumps({
                **build_test_config([{"surface_id": 1, "name": "synthetic", "feed_modes": ["auto"]}],
                                    f"127.0.0.1:{api_port}", f"127.0.0.1:{rtsp_port}"),
                "streams": {"synthetic": [f"http://127.0.0.1:{source.server_port}/stream"]},
            }), encoding="utf-8")
            process = subprocess.Popen([binary, "-c", str(config)], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            clients = []
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/streams", timeout=1):
                            break
                    except Exception:
                        time.sleep(0.1)
                clients = [subprocess.Popen([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp",
                    "-i", f"rtsp://127.0.0.1:{rtsp_port}/synthetic", "-t", "1", "-an", "-f", "null", "-",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
                time.sleep(0.5)
                with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/streams") as response:
                    streams = json.load(response)
                for client in clients:
                    self.assertEqual(client.wait(timeout=10), 0)
                self.assertEqual(len(connections), 1)
                self.assertIn("synthetic", streams)
                self.assertEqual(len(streams["synthetic"]["producers"]), 1)
            finally:
                for client in clients:
                    if client.poll() is None:
                        client.terminate()
                        client.wait(timeout=5)
                process.terminate()
                process.wait(timeout=5)
                source.shutdown()
                source.server_close()


if __name__ == "__main__":
    unittest.main()
