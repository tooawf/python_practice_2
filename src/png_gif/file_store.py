"""Файловая реализация слоя данных второго этапа."""

import json
from pathlib import Path
from threading import RLock
import time

from png_gif.schema import FIELDS


REPLACE_ATTEMPTS = 10
REPLACE_PAUSE = 0.05


class FileStore:
    """Хранить таблицы в JSON с блокировкой и атомарной заменой файла."""

    def __init__(self, filename):
        self.path = Path(filename)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.tables = {name: [] for name in FIELDS}
        if self.path.exists():
            self.tables = json.loads(self.path.read_text("utf-8"))

    def rows(self, table):
        """Вернуть независимые словари в порядке первичных ключей."""
        with self.lock:
            return sorted([dict(row) for row in self.tables[table]],
                          key=lambda row: row["key"])

    def put(self, table, row):
        """Вставить запись или заменить запись с тем же ключом."""
        with self.lock:
            self.tables[table] = [item for item in self.tables[table]
                                  if item["key"] != row["key"]] + [dict(row)]
            self._save()

    def delete(self, table, key):
        """Удалить запись по первичному ключу."""
        with self.lock:
            self.tables[table] = [row for row in self.tables[table]
                                  if row["key"] != key]
            self._save()

    def _save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.tables), "utf-8")
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                temporary.replace(self.path)
                return
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_PAUSE)

    def close(self):
        """У файлового слоя нет постоянно открытого дескриптора."""
