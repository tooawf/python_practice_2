"""Документный слой данных третьего этапа на библиотеке TinyDB."""

from pathlib import Path
from threading import RLock

from tinydb import Query, TinyDB
from tinydb.storages import JSONStorage


class TinyStore:
    """Сохранить контракт rows/put/delete файлового слоя."""

    def __init__(self, filename):
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.database = TinyDB(path, storage=JSONStorage, encoding="utf-8")

    def rows(self, table):
        """Прочитать документы без выдачи изменяемых ссылок наружу."""
        with self.lock:
            rows = [dict(row) for row in self.database.table(table).all()]
            return sorted(rows, key=lambda row: row["key"])

    def put(self, table, row):
        """Обновить документ по ER-ключу или вставить новый."""
        with self.lock:
            self.database.table(table).upsert(
                dict(row), Query()["key"] == row["key"])

    def delete(self, table, key):
        """Удалить документы с переданным ER-ключом."""
        with self.lock:
            self.database.table(table).remove(Query()["key"] == key)

    def close(self):
        """Закрыть файловое соединение TinyDB после завершения очереди."""
        with self.lock:
            self.database.close()
