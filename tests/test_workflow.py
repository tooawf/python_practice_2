"""Генерируемые проверки настоящего CLI, асинхронности и отчёта."""

import base64
from io import BytesIO
from http import HTTPStatus
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch

from hypothesis import given, settings, strategies as st
from PIL import Image

from png_gif.application import create_store
from png_gif.config import Settings
from png_gif.jobs import Jobs
from png_gif.model import Model
from support import FIXED_NOW, RunningApi


WAIT_SECONDS = 10
REPORT_SECONDS = 5 * 60
ALPHA_THRESHOLD = 128


def png_content(width=5, height=7, color=(70, 140, 210, 255)):
    """Получить Base64 настоящего PNG для сетевого запроса."""
    stream = BytesIO()
    Image.new("RGBA", (width, height), color).save(stream, "PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def add_instruction(api, key, data):
    """Создать запись Instruction с известным родителем через API."""
    return api.client.register_instruction(key, {
        "actor": 1, "time": FIXED_NOW, "content": data,
    })


def gated_converter(entered, release):
    """Дать тесту проверить состояние до завершения настоящего CLI."""
    original = Jobs._convert

    def convert(job, row):
        entered.set()
        if not release.wait(WAIT_SECONDS):
            raise OSError("Test did not release conversion")
        return original(job, row)

    return convert


@settings(max_examples=5, deadline=None, derandomize=True)
@given(width=st.integers(1, 40), height=st.integers(1, 40),
       alpha=st.sampled_from([0, 127, 128, 255]))
def test_real_conversion(width, height, alpha):
    """API возвращает queued до CLI, затем отдаёт GIF через XML-ответ."""
    api = RunningApi(test_mode=False)
    entered, release = Event(), Event()
    api.client.register_actor(1, {"user_agent": "integration"})
    try:
        gated = gated_converter(entered, release)
        with patch.object(Jobs, "_convert", gated):
            data = png_content(width, height, (30, 90, 150, alpha))
            row = add_instruction(api, 1, data)
            assert row["status"] == "queued"
            assert entered.wait(WAIT_SECONDS)
            assert api.client.all_response(1) == []
            release.set()
            api.settle()
        answer = api.client.all_response(1)[0]
        assert answer["status"] == "done"
        gif = base64.b64decode(answer["output"], validate=True)
        assert gif == (api.settings.data_dir / "results/1.gif").read_bytes()
        with Image.open(BytesIO(gif)) as image:
            assert image.format == "GIF"
            assert image.size == (width, height)
            expected_alpha = 0 if alpha < ALPHA_THRESHOLD else 255
            assert image.convert("RGBA").getpixel((0, 0))[3] == expected_alpha
    finally:
        release.set()
        api.close()


@settings(max_examples=3, deadline=None, derandomize=True)
@given(kind=st.sampled_from(["jpeg", "broken", "gif"]))
def test_failed_conversion(kind):
    """Ошибочный PNG сохраняет failure и состояние failed."""
    api = RunningApi(test_mode=False)
    try:
        stream = BytesIO()
        if kind == "broken":
            data = b"broken image"
        else:
            Image.new("RGB", (2, 2)).save(stream, kind.upper())
            data = stream.getvalue()
        api.client.register_actor(1, {})
        add_instruction(api, 1, base64.b64encode(data).decode("ascii"))
        api.settle()
        answer = api.client.all_response(1)[0]
        assert answer["status"] == "failed"
        assert answer["failure"] and answer["output"] == ""
        assert api.client.all_instruction(1)[0]["status"] == "failed"
    finally:
        api.close()


def populate_report(api, ages):
    """Сформировать независимый эталон проекции из входных параметров."""
    expected = []
    for index, age in enumerate(ages, start=1):
        value = base64.b64encode(f"input-{index}".encode()).decode()
        api.client.register_instruction(index, {
            "actor": 1, "content": value, "time": FIXED_NOW - age,
        })
        if age <= REPORT_SECONDS:
            expected.append({"user_agent": "agent", "content": value})
    api.settle()
    return expected


@settings(max_examples=5, deadline=None, derandomize=True)
@given(extra_age=st.integers(min_value=-10, max_value=600))
def test_report_boundary(extra_age):
    """Граница пяти минут включается; проекция не зависит от Response."""
    api = RunningApi()
    try:
        api.client.register_actor(1, {"user_agent": "agent"})
        expected = populate_report(api, [0, 299, 300, 301, extra_age])
        assert api.client.all_report() == expected
        duplicate = dict(api.model.store.rows("instruction")[0], key=99)
        api.model.store.put("instruction", duplicate)
        assert api.client.all_report() == expected
        orphan = dict(duplicate, key=100, actor=999, content="orphan")
        api.model.store.put("instruction", orphan)
        assert api.client.all_report() == expected + [
            {"user_agent": None, "content": "orphan"}]
    finally:
        api.close()


@settings(max_examples=3, deadline=None, derandomize=True)
@given(tag=st.text(alphabet="abc", min_size=1, max_size=5))
def test_delete_during_conversion(tag):
    """Удаление работающей и ожидающей инструкции не восстанавливает записи."""
    api = RunningApi(test_mode=False)
    entered, release = Event(), Event()
    try:
        api.client.register_actor(1, {"user_agent": tag})
        with patch.object(Jobs, "_convert", gated_converter(entered, release)):
            add_instruction(api, 1, png_content())
            assert entered.wait(WAIT_SECONDS)
            add_instruction(api, 2, png_content())
            reply = api.client.request("PUT", "/api/modify-instruction/1")
            assert reply.status_code == HTTPStatus.CONFLICT
            api.client.discard_instruction(2)
            api.client.discard_instruction(1)
            release.set()
            api.settle()
        assert api.client.all_instruction(1) == []
        assert api.client.all_response(1) == api.client.all_response(2) == []
    finally:
        release.set()
        api.close()


@settings(max_examples=2, deadline=None, derandomize=True)
@given(status=st.sampled_from(["queued", "running"]))
def test_restart(status):
    """Очередь восстанавливается из сохранённых незавершённых Instruction."""
    with TemporaryDirectory() as folder:
        config = Settings("test", "test", Path(folder),
                          os.environ.get("TEST_BACKEND", "file"))
        store = create_store(config)
        model = Model(store)
        model.register_actor(1, {})
        row = model.register_instruction(1, {"actor": 1,
                                             "content": png_content()})
        store.put("instruction", dict(row, status=status))
        store.close()
        restored = create_store(config)
        jobs = Jobs(Model(restored), folder, test_mode=True)
        try:
            jobs.queue.join()
            assert restored.rows("instruction")[0]["status"] == "skipped"
            assert len(restored.rows("response")) == 1
        finally:
            jobs.close()
            restored.close()
