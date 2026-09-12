import unittest
from unittest.mock import patch

import livebarn_manager


class RuntimeTests(unittest.TestCase):
    def tearDown(self):
        livebarn_manager._runtime_started = False
        livebarn_manager.scheduler = None

    def test_runtime_starts_scheduler_once(self):
        fake_scheduler = type(
            "Scheduler",
            (),
            {"add_job": lambda *a, **k: None, "start": lambda self: None},
        )()
        with patch.object(livebarn_manager, "init_db_if_needed"), patch.object(
            livebarn_manager, "BackgroundScheduler", return_value=fake_scheduler
        ) as scheduler_factory, patch.object(livebarn_manager, "refresh_schedule") as refresh:
            livebarn_manager.start_runtime(run_initial_refresh=False)
            livebarn_manager.start_runtime(run_initial_refresh=True)
        scheduler_factory.assert_called_once_with()
        refresh.assert_not_called()

    def test_production_config_uses_one_threaded_worker(self):
        namespace = {}
        with open("gunicorn.conf.py", encoding="utf-8") as source:
            exec(compile(source.read(), "gunicorn.conf.py", "exec"), namespace)
        self.assertEqual(namespace["workers"], 1)
        self.assertEqual(namespace["worker_class"], "gthread")
        self.assertGreaterEqual(namespace["threads"], 2)
