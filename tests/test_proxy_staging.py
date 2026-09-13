import json
import threading
import unittest
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import livebarn_manager


class ProxyStagingTest(unittest.TestCase):
    def test_actual_proxy_route_relays_local_hls_and_instruments_requests(self):
        counters = {"playlist": 0, "segments": 0, "connections": 0}
        segment = b"\x47" + b"synthetic-ts" * 40

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                counters["connections"] += 1
                if self.path == "/live.m3u8":
                    counters["playlist"] += 1
                    body = b"#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\nseg.ts\n#EXT-X-ENDLIST\n"
                    self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                elif self.path == "/seg.ts":
                    counters["segments"] += 1
                    self.send_response(200); self.send_header("Content-Type", "video/mp2t"); self.end_headers(); self.wfile.write(segment)
                else:
                    self.send_response(404); self.end_headers()
            def log_message(self, *_args): pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        info = {"playlist_url": f"http://127.0.0.1:{server.server_port}/live.m3u8", "feed_mode": "auto"}
        try:
            with patch.object(livebarn_manager, "get_stream_info", return_value=info), \
                 patch.object(livebarn_manager, "stream_needs_refresh", return_value=False), \
                 patch.object(livebarn_manager, "get_preferred_feed_mode", return_value="auto"):
                response = livebarn_manager.app.test_client().get("/proxy/123?mode=auto")
                self.assertEqual(response.status_code, 200)
                self.assertGreater(len(response.data), 0)
                self.assertGreaterEqual(counters["playlist"], 1)
                self.assertEqual(counters["segments"], 1)
                self.assertIn(b"synthetic-ts", response.data)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
