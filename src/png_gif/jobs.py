"""Фоновая очередь преобразований: Base64 из content → stdin CLI → GIF."""

import base64
import binascii
from pathlib import Path
from queue import Queue
import subprocess
import sys
from threading import Thread

from png_gif.schema import ModelError


CONVERTER_TIMEOUT = 60


def png_bytes(content):
    """Проверить Base64; сам формат PNG проверяет дочерний процесс."""
    try:
        data = base64.b64decode(content, validate=True)
        if not data:
            raise ValueError("Empty input")
        return data
    except (ValueError, binascii.Error) as error:
        raise ModelError(
            "Content must be nonempty PNG encoded as Base64") from error


class Jobs:
    """Один рабочий поток выполняет принятые инструкции последовательно."""

    def __init__(self, model, folder, test_mode=False):
        self.model = model
        self.folder = Path(folder) / "results"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.test_mode = test_mode
        self.errors = []
        self.queue = Queue()
        self.thread = Thread(target=self._loop, daemon=True)
        self.thread.start()
        for row in self.model.store.rows("instruction"):
            if row["status"] in {"queued", "running"}:
                self.queue.put(row["key"])

    def register_instruction(self, key, values):
        """Проверить content, сохранить инструкцию и немедленно вернуть её."""
        png_bytes(values.get("content", ""))
        row = self.model.register_instruction(key, values)
        self.queue.put(row["key"])
        return row

    def modify_instruction(self, key, values):
        """Повторно поставить готовое задание при изменении content."""
        if "content" in values:
            png_bytes(values["content"])
        row = self.model.modify_instruction(key, values)
        if row["status"] == "queued":
            self.queue.put(row["key"])
        return row

    def _loop(self):
        while True:
            key = self.queue.get()
            try:
                if key is None:
                    return
                self._execute(key)
            except Exception as error:
                self.errors.append(error)
            finally:
                self.queue.task_done()

    def _execute(self, key):
        row = self.model.start(key)
        if row is None:
            return
        if self.test_mode:
            self.model.finish(key, "skipped")
            return
        try:
            output = self._convert(row)
            self.model.finish(key, "done", output=output)
        except (OSError, subprocess.SubprocessError, ModelError) as error:
            self.model.finish(key, "failed", failure=str(error))

    def _convert(self, row):
        target = self.folder / f"{row['key']}.gif"
        subprocess.run(
            [sys.executable, "-m", "png_gif.convert", str(target)],
            input=png_bytes(row["content"]), capture_output=True,
            check=True, timeout=CONVERTER_TIMEOUT,
        )
        return base64.b64encode(target.read_bytes()).decode("ascii")

    def close(self):
        """Закончить очередь и сообщить о непредвиденной ошибке работника."""
        self.queue.put(None)
        self.queue.join()
        self.thread.join()
        if self.errors:
            raise RuntimeError("Background worker failed") from self.errors[0]
