"""Ровно десять обработчиков из таблицы 1 задания."""

from fastapi import APIRouter, Request

from png_gif.schema import ModelError
from png_gif.xml_codec import filters_from_xml


def query(request):
    """Не принимать повторяющиеся параметры строки запроса."""
    pairs = request.query_params.multi_items()
    if len(pairs) != len(dict(pairs)):
        raise ModelError("Repeated query parameter")
    return dict(pairs)


def delete_key(request):
    """Удаление требует ровно один параметр key."""
    values = query(request)
    if set(values) != {"key"}:
        raise ModelError("Exactly one key parameter is required")
    return values["key"]


def actor_router():
    """Создание, удаление, поиск и изменение Actor."""
    router = APIRouter()

    @router.put("/api/register-actor/{key}")
    async def register_actor(key: int, request: Request):
        return request.app.state.model.register_actor(key, query(request))

    @router.get("/api/discard-actor")
    async def discard_actor(request: Request):
        return request.app.state.model.discard_actor(delete_key(request))

    @router.post("/api/all-actor")
    async def all_actor(request: Request):
        values = filters_from_xml(await request.body())
        return request.app.state.model.all_actor(values)

    @router.put("/api/modify-actor/{key}")
    async def modify_actor(key: int, request: Request):
        return request.app.state.model.modify_actor(key, query(request))

    return router


def instruction_router():
    """Создание, удаление, поиск и изменение Instruction."""
    router = APIRouter()

    @router.put("/api/register-instruction/{key}")
    async def register_instruction(key: int, request: Request):
        return request.app.state.jobs.register_instruction(key, query(request))

    @router.get("/api/discard-instruction")
    async def discard_instruction(request: Request):
        return request.app.state.model.discard_instruction(delete_key(request))

    @router.post("/api/all-instruction/{actor}")
    async def all_instruction(actor: int, request: Request):
        values = filters_from_xml(await request.body())
        return request.app.state.model.all_instruction(actor, values)

    @router.put("/api/modify-instruction/{key}")
    async def modify_instruction(key: int, request: Request):
        return request.app.state.jobs.modify_instruction(key, query(request))

    return router


def report_router():
    """Поиск Response и отчёт по формуле (1)."""
    router = APIRouter()

    @router.post("/api/all-response/{instruction}")
    async def all_response(instruction: int, request: Request):
        values = filters_from_xml(await request.body())
        return request.app.state.model.all_response(instruction, values)

    @router.post("/api/all-report")
    async def all_report(request: Request):
        return request.app.state.model.all_report()

    return router
