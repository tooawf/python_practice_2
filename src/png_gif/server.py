"""Запуск Uvicorn с настройками и HTTP-учётными данными из INI."""

import argparse
from configparser import Error

import uvicorn

from png_gif.application import create_app
from png_gif.config import load_config


def main():
    """Прочитать конфигурацию, затем запустить FastAPI на заданном порту."""
    parser = argparse.ArgumentParser(description="Asynchronous PNG to GIF API")
    parser.add_argument("--config", default="config.ini")
    args = parser.parse_args()
    try:
        settings = load_config(args.config)
    except (ValueError, Error) as error:
        parser.error(str(error))
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
