"""Conservative production serving defaults for LiveBarn's long-lived streams."""

import os


bind = "0.0.0.0:" + os.getenv("SERVER_PORT", "5000")
workers = 1
worker_class = "gthread"
threads = 8
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = None
errorlog = "-"
capture_output = True


def post_worker_init(worker):
    from livebarn_manager import start_runtime

    start_runtime(os.getenv("SCHEDULE_REFRESH_ON_START", "1") != "0")
