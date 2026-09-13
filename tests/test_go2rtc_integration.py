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
from unittest.mock import patch
from werkzeug.serving import make_server

import livebarn_manager

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
                protocol_version = "HTTP/1.1"
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

    def test_actual_proxy_route_to_go2rtc(self):
        """Exercise synthetic HLS -> Flask /proxy -> go2rtc -> RTSP."""
        binary = shutil.which("go2rtc") or "/usr/local/bin/go2rtc"
        if not Path(binary).exists() or not shutil.which("ffmpeg"):
            self.skipTest("go2rtc and ffmpeg are required")
        with tempfile.TemporaryDirectory(prefix="proxy-go2rtc-") as directory:
            root = Path(directory)
            fixture = root / "fixture.ts"
            config = root / "go2rtc.json"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc=size=320x180:rate=10", "-t", "5", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", "-f", "mpegts", str(fixture)], check=True)
            payload = fixture.read_bytes(); counters = {"source_connections": set(), "playlists": 0, "segments": 0}

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    counters["source_connections"].add(self.client_address)
                    if self.path == "/live.m3u8":
                        counters["playlists"] += 1
                        body = b"#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nseg1.ts\n#EXTINF:1,\nseg2.ts\n#EXTINF:1,\nseg3.ts\n"
                        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                    elif self.path in {"/seg1.ts", "/seg2.ts", "/seg3.ts"}:
                        counters["segments"] += 1; self.send_response(200); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
                    else:
                        self.send_response(404); self.end_headers()
                def log_message(self, *_args): pass

            source = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            threading.Thread(target=source.serve_forever, daemon=True).start()
            staging_port, api_port, rtsp_port = _free_port(), _free_port(), _free_port()
            proxy_requests = []
            def staging_app(environ, start_response):
                if environ.get("PATH_INFO") == "/proxy/123":
                    proxy_requests.append(environ.get("QUERY_STRING", ""))
                return livebarn_manager.app(environ, start_response)
            staging = make_server("127.0.0.1", staging_port, staging_app, threaded=True)
            threading.Thread(target=staging.serve_forever, daemon=True).start()
            config.write_text(json.dumps({
                "api": {"listen": f"127.0.0.1:{api_port}"},
                "rtsp": {"listen": f"127.0.0.1:{rtsp_port}"},
                "streams": {"proxy": [f"http://127.0.0.1:{staging_port}/proxy/123?mode=auto"]},
            }), encoding="utf-8")
            process = subprocess.Popen([binary, "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clients = []
            info = {"playlist_url": f"http://127.0.0.1:{source.server_port}/live.m3u8", "feed_mode": "auto"}
            try:
                with patch.object(livebarn_manager, "get_stream_info", return_value=info), \
                     patch.object(livebarn_manager, "stream_needs_refresh", return_value=False), \
                     patch.object(livebarn_manager, "get_preferred_feed_mode", return_value="auto"):
                    for _ in range(100):
                        try:
                            with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/streams", timeout=1): break
                        except Exception: time.sleep(0.1)
                    clients = [subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp",
                        "-i", f"rtsp://127.0.0.1:{rtsp_port}/proxy", "-frames:v", "5", "-an", "-f", "null", "-"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(2)]
                    time.sleep(0.6)
                    with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/streams") as response:
                        streams = json.load(response)
                    for client in clients:
                        try:
                            self.assertEqual(client.wait(timeout=10), 0)
                        except subprocess.TimeoutExpired:
                            client.kill()
                            client.wait(timeout=5)
                            raise
                    self.assertEqual(len(proxy_requests), 1)
                    self.assertGreaterEqual(counters["playlists"], 1)
                    self.assertGreaterEqual(counters["segments"], 1)
                    self.assertEqual(len(streams["proxy"]["producers"]), 1)
            finally:
                for client in clients:
                    if client.poll() is None:
                        client.kill()
                        client.wait(timeout=5)
                process.terminate(); process.wait(timeout=5)
                staging.shutdown(); source.shutdown(); staging.server_close(); source.server_close()


if __name__ == "__main__":
    unittest.main()
