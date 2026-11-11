"""Настройки приложения и учётные данные HTTP Basic в INI-файле."""

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    """Адрес, хранение, HTTP-пользователь и тестовый режим."""

    username: str
    password: str
    data_dir: Path
    backend: str = "tinydb"
    host: str = "127.0.0.1"
    port: int = 8001
    test_mode: bool = False


def load_config(filename):
    """Прочитать обязательную секцию auth и настройки server."""
    path = Path(filename).resolve()
    parser = ConfigParser(interpolation=None)
    if not parser.read(path, encoding="utf-8"):
        raise ValueError("Configuration file not found")
    username = parser.get("auth", "username")
    password = parser.get("auth", "password")
    backend = parser.get("server", "backend", fallback="tinydb")
    if not username or ":" in username or not password:
        raise ValueError("Username and password must be nonempty")
    if backend not in {"file", "tinydb"}:
        raise ValueError("Backend must be file or tinydb")
    folder = parser.get("server", "data_dir", fallback="data")
    return Settings(
        username, password, (path.parent / folder).resolve(), backend,
        parser.get("server", "host", fallback="127.0.0.1"),
        parser.getint("server", "port", fallback=8001),
        parser.getboolean("server", "test_mode", fallback=False),
    )
