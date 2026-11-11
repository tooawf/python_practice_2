"""Предметная модель Actor, Instruction, Response и отчёта (1)."""

from threading import RLock
import time

from png_gif.schema import ModelError, REPORT_SECONDS, clean, key_value, record


class Model:
    """Одинаковые операции для файлового хранилища и TinyDB."""

    def __init__(self, store, clock=time.time):
        self.store = store
        self.clock = clock
        self.lock = RLock()

    def _find(self, table, key):
        key = key_value(key)
        for row in self.store.rows(table):
            if row["key"] == key:
                return row
        raise ModelError("Record not found", 404)

    def _register(self, table, key, values):
        row = record(table, key, values)
        if any(item["key"] == row["key"] for item in self.store.rows(table)):
            raise ModelError("Key already exists", 409)
        self.store.put(table, row)
        return row

    def _all(self, table, values):
        values = clean(table, values)
        return [row for row in self.store.rows(table)
                if all(row[name] == value for name, value in values.items())]

    def register_actor(self, key, values):
        """Создать Actor с ключом из пути запроса."""
        with self.lock:
            return self._register("actor", key, values)

    def discard_actor(self, key):
        """Удалить Actor вместе с его инструкциями и ответами."""
        with self.lock:
            actor = self._find("actor", key)
            for row in self.all_instruction(actor["key"], {}):
                self.discard_instruction(row["key"])
            self.store.delete("actor", actor["key"])
            return actor

    def all_actor(self, values):
        """Найти Actor по точному совпадению переданных полей."""
        with self.lock:
            return self._all("actor", values)

    def modify_actor(self, key, values):
        """Изменить поля Actor, сохранив первичный ключ."""
        with self.lock:
            row = self._find("actor", key)
            changes = self._changes("actor", values)
            row.update(changes)
            self.store.put("actor", row)
            return row

    def register_instruction(self, key, values):
        """Создать Instruction с существующим Actor и статусом queued."""
        with self.lock:
            data = clean("instruction", values)
            self._find("actor", data.get("actor", 0))
            data["status"] = "queued"
            return self._register("instruction", key, data)

    def discard_instruction(self, key):
        """Удалить Instruction и все её Response."""
        with self.lock:
            row = self._find("instruction", key)
            for answer in self.all_response(row["key"], {}):
                self.store.delete("response", answer["key"])
            self.store.delete("instruction", row["key"])
            return row

    def all_instruction(self, actor, values):
        """Найти инструкции конкретного Actor с дополнительными фильтрами."""
        with self.lock:
            criteria = dict(values, actor=key_value(actor))
            return self._all("instruction", criteria)

    def modify_instruction(self, key, values):
        """Изменить готовую инструкцию; новый content требует перерасчёта."""
        with self.lock:
            row = self._find("instruction", key)
            if row["status"] in {"queued", "running"}:
                raise ModelError("Instruction is still processing", 409)
            changes = self._changes("instruction", values)
            self._find("actor", changes.get("actor", row["actor"]))
            if "content" in changes:
                changes["status"] = "queued"
            row.update(changes)
            self.store.put("instruction", row)
            return row

    def _changes(self, table, values):
        changes = clean(table, values)
        if {"key", "status"} & changes.keys():
            raise ModelError("Key and processing status cannot be modified")
        return changes

    def all_response(self, instruction, values):
        """Найти ответы для одной Instruction, включая предыдущие запуски."""
        with self.lock:
            return self._all("response", dict(values, instruction=instruction))

    def start(self, key):
        """Получить актуальную инструкцию или пропустить уже удалённую."""
        with self.lock:
            rows = self._all("instruction", {"key": key})
            if not rows:
                return None
            row = rows[0]
            row["status"] = "running"
            self.store.put("instruction", row)
            return row

    def finish(self, key, status, output="", failure=""):
        """Сохранить ответ, если инструкция ещё существует."""
        with self.lock:
            rows = self._all("instruction", {"key": key})
            if not rows:
                return
            row = rows[0]
            answers = self.store.rows("response")
            answer_key = max((item["key"] for item in answers), default=0) + 1
            answer = record("response", answer_key, {
                "instruction": key, "status": status,
                "output": output, "failure": failure,
            })
            self.store.put("response", answer)
            self.store.put("instruction", dict(row, status=status))

    def all_report(self):
        """Правое соединение Actor с инструкциями за последние пять минут."""
        with self.lock:
            agents = {row["key"]: row["user_agent"]
                      for row in self.store.rows("actor")}
            threshold = int(self.clock()) - REPORT_SECONDS
            pairs = [(agents.get(row["actor"]), row["content"])
                     for row in self.store.rows("instruction")
                     if row["time"] >= threshold]
            return [{"user_agent": agent, "content": content}
                    for agent, content in dict.fromkeys(pairs)]
