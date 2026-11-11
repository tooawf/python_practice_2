"""Model-based testing всех десяти маршрутов только через API-клиент."""

import base64
from http import HTTPStatus

from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine, initialize, invariant, precondition, rule,
)

from png_gif.client import ApiError
from png_gif.xml_codec import decode
from support import FIXED_NOW, RunningApi


TEXT = st.text(alphabet="abc XYZабв012_&<>\"", max_size=12)
INDEX = st.integers(min_value=0, max_value=50)
ROUTES = (
    ("PUT", "/api/register-actor/1"),
    ("GET", "/api/discard-actor"),
    ("POST", "/api/all-actor"),
    ("PUT", "/api/modify-actor/1"),
    ("PUT", "/api/register-instruction/1"),
    ("GET", "/api/discard-instruction"),
    ("POST", "/api/all-instruction/1"),
    ("PUT", "/api/modify-instruction/1"),
    ("POST", "/api/all-response/1"),
    ("POST", "/api/all-report"),
)


def content(text):
    """В тестовом режиме достаточно Base64 без настоящего преобразования."""
    return base64.b64encode((text or "PNG").encode("utf-8")).decode("ascii")


class ApiMachine(RuleBasedStateMachine):
    """Сравнивать приложение с независимыми словарями эталонной модели."""

    def __init__(self):
        super().__init__()
        self.api = RunningApi()
        self.client = self.api.client
        self.actors, self.instructions, self.responses = {}, {}, {}
        self.actor_sequence = 0
        self.instruction_sequence = 0

    @initialize(text=TEXT)
    def seed(self, text):
        """Каждый сценарий обязательно проходит все десять маршрутов."""
        self.add_actor(text)
        self.add_actor("second")
        self.add_instruction(0, text)
        self.modify_actor(0, "changed")
        self.modify_instruction(0, "new content")
        self.check_state()
        self.remove_instruction(0)
        self.add_instruction(0, text)
        self.remove_actor(0)
        self.authentication()
        self.invalid_requests()

    @rule(text=TEXT)
    def add_actor(self, text):
        """Создать Actor с ожидаемыми полями и явно заданным временем."""
        self.actor_sequence += 1
        key = self.actor_sequence
        values = {"time": FIXED_NOW, "ip": "127.0.0.1", "user_agent": text}
        expected = dict(values, key=key)
        assert self.client.register_actor(key, values) == expected
        self.actors[key] = expected

    @precondition(lambda self: bool(self.actors))
    @rule(index=INDEX, text=TEXT)
    def add_instruction(self, index, text):
        """Поставить инструкцию и предсказать ответ тестового режима."""
        actor = sorted(self.actors)[index % len(self.actors)]
        self.instruction_sequence += 1
        key = self.instruction_sequence
        values = {"time": FIXED_NOW, "content": content(text), "actor": actor}
        expected = dict(values, key=key, status="queued")
        assert self.client.register_instruction(key, values) == expected
        expected["status"] = "skipped"
        self.instructions[key] = expected
        self.save_expected_response(key)

    def save_expected_response(self, instruction):
        """После завершения добавить самостоятельно вычисленные поля ответа."""
        self.api.settle()
        key = max(self.responses, default=0) + 1
        self.responses[key] = {"key": key, "instruction": instruction,
                               "status": "skipped", "output": "", "failure": ""}

    @precondition(lambda self: bool(self.actors))
    @rule(index=INDEX, text=TEXT)
    def modify_actor(self, index, text):
        """Изменение user_agent должно отражаться в поиске и отчёте."""
        key = sorted(self.actors)[index % len(self.actors)]
        self.actors[key]["user_agent"] = text
        assert self.client.modify_actor(key, {"user_agent": text}) == (
            self.actors[key])

    @precondition(lambda self: bool(self.instructions))
    @rule(index=INDEX, text=TEXT)
    def modify_instruction(self, index, text):
        """Новый content готовой инструкции создаёт ещё один ответ."""
        key = sorted(self.instructions)[index % len(self.instructions)]
        expected = dict(self.instructions[key], content=content(text),
                        status="queued")
        assert self.client.modify_instruction(
            key, {"content": content(text)}) == expected
        self.instructions[key] = dict(expected, status="skipped")
        self.save_expected_response(key)

    @precondition(lambda self: bool(self.instructions))
    @rule(index=INDEX)
    def remove_instruction(self, index):
        """Каскадное удаление не оставляет ответов на отсутствующее задание."""
        key = sorted(self.instructions)[index % len(self.instructions)]
        assert self.client.discard_instruction(key) == self.instructions[key]
        self.instructions.pop(key)
        self.responses = {item: row for item, row in self.responses.items()
                          if row["instruction"] != key}

    @precondition(lambda self: bool(self.actors))
    @rule(index=INDEX)
    def remove_actor(self, index):
        """Удаление Actor удаляет связанные Instruction и Response."""
        key = sorted(self.actors)[index % len(self.actors)]
        assert self.client.discard_actor(key) == self.actors.pop(key)
        removed = {item for item, row in self.instructions.items()
                   if row["actor"] == key}
        self.instructions = {
            item: row for item, row in self.instructions.items()
            if item not in removed
        }
        self.responses = {item: row for item, row in self.responses.items()
                          if row["instruction"] not in removed}

    @rule(text=TEXT)
    def search(self, text):
        """XML-фильтры должны сохранять пробелы и специальные символы."""
        expected = [row for row in self.actors.values()
                    if row["user_agent"] == text]
        assert self.client.all_actor({"user_agent": text}) == expected

    @precondition(lambda self: bool(self.instructions))
    @rule(index=INDEX, age=st.integers(min_value=0, max_value=600))
    def change_instruction_time(self, index, age):
        """Изменение только времени не должно запускать новый конвертер."""
        key = sorted(self.instructions)[index % len(self.instructions)]
        value = FIXED_NOW - age
        self.instructions[key]["time"] = value
        assert self.client.modify_instruction(key, {"time": value}) == (
            self.instructions[key])

    @rule()
    def authentication(self):
        """Любой маршрут отвергает отсутствующий или неверный Basic."""
        for method, path in ROUTES:
            for value in (None, "Bearer abc", "Basic ???", "Basic /w==",
                          "Basic bm9jb2xvbg==", "Basic YmFkOmJhZA=="):
                headers = {} if value is None else {"Authorization": value}
                reply = self.client.request(method, path, headers=headers)
                assert reply.status_code == HTTPStatus.UNAUTHORIZED
                assert reply.headers["WWW-Authenticate"].startswith("Basic ")
                assert "error" in decode(reply.content)

    @rule()
    def invalid_requests(self):
        """Ошибки XML, путей и параметров возвращают XML с нужным кодом."""
        for path in ("/api/discard-actor", "/api/discard-instruction"):
            reply = self.client.request("GET", path)
            assert reply.status_code == HTTPStatus.BAD_REQUEST
        for body in (b"broken", b"<wrong/>", b"<filters><x/><x/></filters>",
                     b"<filters><x><y/></x></filters>",
                     b'<!DOCTYPE a [<!ENTITY b "c">]><filters>&b;</filters>'):
            reply = self.api.transport.post(
                "/api/all-actor", content=body,
                headers={"Authorization": self.client.authorization},
            )
            assert reply.status_code == HTTPStatus.BAD_REQUEST
        self.bad_model_requests()

    def bad_model_requests(self):
        """Отсутствующие ключи и неверные поля не изменяют модель."""
        cases = (
            ("PUT", "/api/register-actor/no-int", {}, HTTPStatus.BAD_REQUEST),
            ("PUT", "/api/register-actor/0", {}, HTTPStatus.BAD_REQUEST),
            ("PUT", "/api/register-actor/99", {"wrong": "x"},
             HTTPStatus.BAD_REQUEST),
            ("PUT", "/api/modify-actor/9999", {}, HTTPStatus.NOT_FOUND),
            ("PUT", "/api/register-instruction/9999", {"content": "?"},
             HTTPStatus.BAD_REQUEST),
            ("GET", "/api/discard-actor?key=1&key=2", {},
             HTTPStatus.BAD_REQUEST),
            ("GET", "/not-found", {}, HTTPStatus.NOT_FOUND),
        )
        for method, path, values, status in cases:
            reply = self.client.request(method, path, values)
            assert reply.status_code == status
            assert "error" in decode(reply.content)
        try:
            self.client.discard_instruction(9999)
        except ApiError as error:
            assert error.status == HTTPStatus.NOT_FOUND
        else:
            raise AssertionError("ApiError expected")
        self.business_errors()

    def business_errors(self):
        """Дубликаты, изменение ключа и отсутствующий Actor отклоняются."""
        if self.actors:
            key = next(iter(self.actors))
            reply = self.client.request("PUT", f"/api/register-actor/{key}")
            assert reply.status_code == HTTPStatus.CONFLICT
            reply = self.client.request("PUT", f"/api/modify-actor/{key}",
                                        {"key": 99})
            assert reply.status_code == HTTPStatus.BAD_REQUEST
        reply = self.client.request("PUT", "/api/register-instruction/9999",
                                    {"actor": 9999, "content": content("x")})
        assert reply.status_code == HTTPStatus.NOT_FOUND
        reply = self.client.request("POST", "/api/all-actor", {"time": "bad"},
                                    xml=True)
        assert reply.status_code == HTTPStatus.BAD_REQUEST

    @invariant()
    def check_state(self):
        """Сверить таблицы и проекцию отчёта после каждого перехода."""
        assert self.client.all_actor() == list(self.actors.values())
        self.check_instructions()
        self.check_responses()
        pairs = {(self.actors[row["actor"]]["user_agent"], row["content"])
                 for row in self.instructions.values()
                 if row["time"] >= FIXED_NOW - 5 * 60}
        actual = self.client.all_report()
        assert {(row["user_agent"], row["content"]) for row in actual} == pairs

    def check_instructions(self):
        """Поиск инструкций должен ограничиваться родителем и фильтрами."""
        for key in self.actors:
            expected = [row for row in self.instructions.values()
                        if row["actor"] == key]
            assert self.client.all_instruction(key) == expected
            assert self.client.all_instruction(
                key, {"status": "skipped"}) == expected

    def check_responses(self):
        """Сравнить все поля ответов, кроме серверного времени завершения."""
        for key in self.instructions:
            expected = [row for row in self.responses.values()
                        if row["instruction"] == key]
            actual = self.client.all_response(key)
            normalized = [{name: value for name, value in row.items()
                           if name != "time"} for row in actual]
            assert normalized == expected

    def teardown(self):
        """Закрыть приложение даже при найденном контрпримере."""
        self.api.close()


TestApi = ApiMachine.TestCase
TestApi.settings = settings(max_examples=10, stateful_step_count=16,
                            deadline=None, derandomize=True)
