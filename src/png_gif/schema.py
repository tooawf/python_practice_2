"""Типы полей рисунка 1 и общие проверки предметной модели."""

import time


FIELDS = {
    "actor": {"key": int, "time": int, "ip": str, "user_agent": str},
    "instruction": {"key": int, "time": int, "content": str,
                    "actor": int, "status": str},
    "response": {"key": int, "time": int, "output": str,
                 "status": str, "failure": str, "instruction": int},
}
REPORT_SECONDS = 5 * 60


class ModelError(Exception):
    """Ошибка модели с HTTP-кодом для XML-ответа."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def integer(value):
    """Принять целое без округления и логических значений."""
    try:
        if isinstance(value, bool):
            raise ValueError("Boolean is not an integer")
        return int(str(value))
    except (ValueError, TypeError) as error:
        raise ModelError("Expected an integer") from error


def key_value(value):
    """Первичный ключ должен быть положительным целым."""
    value = integer(value)
    if value <= 0:
        raise ModelError("Key must be positive")
    return value


def clean(table, values):
    """Отклонить неизвестные поля и привести числовые значения."""
    if values.keys() - FIELDS[table].keys():
        raise ModelError("Unknown field")
    return {name: integer(value) if FIELDS[table][name] is int else str(value)
            for name, value in values.items()}


def record(table, key, values):
    """Заполнить поля ER-записи, сохранив явно заданное время."""
    values = clean(table, values)
    if "key" in values:
        raise ModelError("Key belongs in the path")
    row = {name: kind() for name, kind in FIELDS[table].items()}
    row.update(time=int(time.time()))
    row.update(values)
    row["key"] = key_value(key)
    return row
