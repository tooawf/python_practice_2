"""API-клиент: имена методов совпадают с методами предметной модели."""

import base64
from http import HTTPStatus

import httpx

from png_gif.xml_codec import decode, encode


class ApiError(Exception):
    """HTTP-код и понятное сообщение из XML-ответа сервера."""

    def __init__(self, status, data):
        super().__init__(data["error"])
        self.status = status


class ApiClient:
    """Поддерживать обычный HTTP и внедрение транспорта для тестов."""

    def __init__(self, url, username, password, transport=None):
        self.transport = transport or httpx.Client(base_url=url, timeout=10)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8"))
        self.authorization = "Basic " + token.decode("ascii")

    def request(self, method, path, values=None, xml=False, headers=None):
        """Вернуть HTTP-ответ; headers={} отключает авторизацию клиента."""
        actual = {
            "Authorization": self.authorization,
            "Content-Type": "application/xml", "Accept": "application/xml",
        }
        if headers is not None:
            actual = headers
        options = {"headers": actual}
        if xml:
            options["content"] = encode(values or {}, root="filters")
        elif values:
            options["params"] = values
        return self.transport.request(method, path, **options)

    def _call(self, method, path, values=None, xml=False):
        reply = self.request(method, path, values, xml)
        data = decode(reply.content)
        if reply.status_code != HTTPStatus.OK:
            raise ApiError(reply.status_code, data)
        return data

    def register_actor(self, key, values):
        """PUT /api/register-actor/:key, остальные поля в query."""
        return self._call("PUT", f"/api/register-actor/{key}", values)

    def discard_actor(self, key):
        """GET /api/discard-actor?key=... с каскадным удалением."""
        return self._call("GET", "/api/discard-actor", {"key": key})

    def all_actor(self, values=None):
        """POST /api/all-actor, фильтры в XML."""
        return self._call("POST", "/api/all-actor", values, xml=True)

    def modify_actor(self, key, values):
        """PUT /api/modify-actor/:key, новые значения в query."""
        return self._call("PUT", f"/api/modify-actor/{key}", values)

    def register_instruction(self, key, values):
        """PUT /api/register-instruction/:key, данные в query."""
        return self._call("PUT", f"/api/register-instruction/{key}", values)

    def discard_instruction(self, key):
        """GET /api/discard-instruction?key=... с удалением ответов."""
        return self._call("GET", "/api/discard-instruction", {"key": key})

    def all_instruction(self, actor, values=None):
        """POST /api/all-instruction/:actor, фильтры в XML."""
        return self._call("POST", f"/api/all-instruction/{actor}",
                          values, xml=True)

    def modify_instruction(self, key, values):
        """PUT /api/modify-instruction/:key с повторным запуском content."""
        return self._call("PUT", f"/api/modify-instruction/{key}", values)

    def all_response(self, instruction, values=None):
        """POST /api/all-response/:instruction, фильтры в XML."""
        return self._call("POST", f"/api/all-response/{instruction}",
                          values, xml=True)

    def all_report(self):
        """POST /api/all-report без параметров."""
        return self._call("POST", "/api/all-report")

    def close(self):
        """Освободить соединения используемого HTTP-транспорта."""
        self.transport.close()
