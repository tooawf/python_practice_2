"""Приложение FastAPI с отдельной папкой и настоящим API-клиентом."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from png_gif.application import create_app
from png_gif.client import ApiClient
from png_gif.config import load_config


FIXED_NOW = 2_000_000_000


class RunningApi:
    """Читать авторизацию из INI и выполнять HTTP-запросы через ASGI."""

    def __init__(self, test_mode=True):
        self.folder = TemporaryDirectory()
        self.root = Path(self.folder.name)
        backend = os.environ.get("TEST_BACKEND", "file")
        config = self.root / "config.ini"
        config.write_text(
            "[auth]\nusername = test-user\npassword = test:password\n"
            f"[server]\nbackend = {backend}\ntest_mode = {test_mode}\n",
            encoding="utf-8",
        )
        self.settings = load_config(config)
        self.app = create_app(self.settings)
        self.transport = TestClient(self.app)
        self.transport.__enter__()
        self.client = ApiClient("http://testserver", "test-user",
                                "test:password", self.transport)
        self.model = self.app.state.model
        self.model.clock = lambda: FIXED_NOW
        self.jobs = self.app.state.jobs

    def settle(self):
        """Дождаться фоновой очереди перед сравнением состояния."""
        self.jobs.queue.join()
        if self.jobs.errors:
            raise RuntimeError("Worker failed") from self.jobs.errors[0]

    def close(self):
        """Закончить lifespan приложения, затем удалить временные данные."""
        try:
            self.transport.__exit__(None, None, None)
        finally:
            self.folder.cleanup()
