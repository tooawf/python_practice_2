# Асинхронное преобразование PNG в GIF

Практическая работа № 2, вариант 1, ИКБО-71-24.
Тема курсовой: веб-приложение с HTTP API для асинхронного
преобразования файлов из формата PNG в формат GIF.

## Этап 1. Конвертер со стандартным вводом

Нужен Python 3.10 или новее. Установка из корня проекта:

```console
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[test]"
```

CLI принимает бинарное содержимое PNG через stdin и сохраняет GIF
по пути, переданному аргументом. В cmd.exe или bash:

```console
python -m png_gif.convert result.gif < input.png
```

В PowerShell используйте команду через cmd.exe, чтобы сохранить
бинарные данные без преобразования кодировки:

```powershell
cmd /c "python -m png_gif.convert result.gif < input.png"
```

Альтернатива: установленная команда `png-to-gif result.gif` с тем же stdin.
`convert(data, destination)` проверяет формат и сохраняет результат,
возвращая размер изображения. `main()` разбирает аргументы и читает stdin.
Ошибка формата или чтения даёт ненулевой код завершения.

RGB, RGBA, L, LA и палитровые PNG приводятся к RGBA. Палитра GIF
содержит до 255 цветов и отдельный прозрачный индекс. Alpha меньше
128 становится прозрачной, остальные пиксели непрозрачны.
Для много кадрового PNG обрабатывается первый кадр.

```console
run.bat demo
run.bat test
python -m pip wheel . --no-deps -w dist
```

`examples/demo.py` создаёт пять входов: цветной, серый, прозрачный,
палитровый и однопиксельный PNG. `run_case` передаёт каждый в stdin
отдельного процесса и проверяет формат GIF и размеры, `main`
сохраняет протокол `examples/results.json`.
Бинарные примеры создаются в `examples/generated` и исключены из git.
Модульные проверки находятся в `tests/test_convert.py`.

## Этап 2. FastAPI, XML и файловый слой

Скопируйте пример конфигурации и запустите сервер:

```powershell
Copy-Item config.example.ini config.ini
run.bat --config config.ini
```

Альтернатива: `python -m png_gif.server --config config.ini`.
Сервер доступен по адресу `http://127.0.0.1:8001`.
Для первоначальной версии укажите `backend = file`.
Имена пользователя и пароль берутся из секции `[auth]` файла INI.
Демонстрационные значения: `student` и `png-gif-local`.
Локальный `config.ini` исключён из git.

| Настройка | Назначение | Значение в примере |
|---|---|---|
| auth.username | Имя HTTP-пользователя, без двоеточия | student |
| auth.password | Пароль HTTP-пользователя | png-gif-local |
| server.host | Интерфейс сервера | 127.0.0.1 |
| server.port | Порт Uvicorn | 8001 |
| server.data_dir | Папка данных относительно INI | data |
| server.backend | Реализация хранилища | file |
| server.test_mode | Не запускать настоящий конвертер | false |

Секция auth обязательна. Неверный слой хранения, пустое имя или пароль
не позволяют запустить приложение. Аргумент `--config` по умолчанию
равен `config.ini`. `Ctrl+C` останавливает HTTP-сервер и дожидается
принятых фоновых заданий перед закрытием данных.

### Маршруты таблицы 1

| Метод | Маршрут | Передача параметров | Метод модели и клиента |
|---|---|---|---|
| PUT | `/api/register-actor/:key` | ключ в пути, поля в query | `register_actor` |
| GET | `/api/discard-actor` | key в query | `discard_actor` |
| POST | `/api/all-actor` | фильтры в XML | `all_actor` |
| PUT | `/api/modify-actor/:key` | ключ в пути, поля в query | `modify_actor` |
| PUT | `/api/register-instruction/:key` | ключ в пути, поля в query | `register_instruction` |
| GET | `/api/discard-instruction` | key в query | `discard_instruction` |
| POST | `/api/all-instruction/:actor` | родитель в пути, фильтры в XML | `all_instruction` |
| PUT | `/api/modify-instruction/:key` | ключ в пути, поля в query | `modify_instruction` |
| POST | `/api/all-response/:instruction` | родитель в пути, фильтры в XML | `all_response` |
| POST | `/api/all-report` | нет | `all_report` |

Все операции проверяют HTTP Basic по RFC 7617. Отсутствующий,
повреждённый или неверный Authorization даёт `401` с заголовком
`WWW-Authenticate: Basic realm="png-gif", charset="UTF-8"`.
Проверка выполняется до маршрутизации и разбора параметров.
Имя и пароль поддерживают UTF-8, пароль может содержать двоеточие.
Клиент формирует `Authorization: Basic base64(username:password)`.
При работе через внешнюю сеть Basic-авторизация должна передаваться
через HTTPS; сам пример запускается локально по HTTP.

Успешные операции возвращают `200` и XML. Ошибки приложения тоже
возвращают XML: `400` для неверных полей, XML или ключа; `404` для
отсутствующей записи или маршрута; `409` для существующего ключа
или изменения ещё выполняющейся инструкции.

### Схема записей и правила изменения

| Таблица | Поля рисунка 1 |
|---|---|
| Actor | key:int, time:int, ip:str, user_agent:str |
| Instruction | key:int, time:int, content:str, actor:int, status:str |
| Response | key:int, time:int, output:str, status:str, failure:str, instruction:int |

Ключи Actor и Instruction задаёт клиент в пути: положительные целые,
уникальные внутри таблицы. Ключ Response назначается сервером.
`time` измеряется в целых секундах Unix UTC. При создании оно ставится
сервером, если клиент не задал его явно. Пропущенные строковые поля
равны пустой строке. Instruction требует существующего Actor.

`content` содержит Base64 бинарного PNG; `output` — Base64 готового GIF.
При создании Instruction сервер проверяет Base64 и ставит `queued`.
HTTP-запрос возвращается без ожидания преобразования. Рабочий поток
меняет статус на `running`, передаёт декодированный PNG в stdin
дочернего `python -m png_gif.convert` через `subprocess.run`, сохраняет
`data/results/<key>.gif` и Response со статусом `done`.
Ошибка формата, сбой чтения или тайм-аут 60 секунд дают `failed` и
непустое поле `failure`. В тестовом режиме subprocess не вызывается,
статус становится `skipped`, `output` и `failure` остаются пустыми.
После перезапуска очередь восстанавливается из `queued` и `running`.

Ключ и status нельзя менять запросом modify. Изменение content готовой
Instruction повторно ставит её в очередь; предыдущие ответы сохраняются.
Изменение времени или Actor не требует повторного преобразования.
Удаление Instruction удаляет её Response, удаление Actor каскадно
удаляет его Instruction и Response. Завершение уже удалённой инструкции
не создаёт её заново.

Фильтры используют точное равенство полей и их логическое И.
`<filters/>` означает отсутствие фильтров. Неизвестные поля, вложенные
элементы, дубликаты параметров и повторения XML-полей отклоняются.
Пустой результат поиска — список, а не ошибка.

Пример тела поиска:

```xml
<filters><user_agent>desktop-client</user_agent></filters>
```

XML-ответ использует корень `result`. Атрибут `type` различает
`object`, `list`, `int`, `str`, `null`; элементы списка называются `item`.
Пустая строка записывается как элемент с `type="str"` без текста.
XML разбирается через defusedxml с запретом опасных DTD и сущностей.

```xml
<?xml version="1.0" encoding="utf-8"?>
<result type="list">
  <item type="object">
    <key type="int">1</key>
    <time type="int">2000000000</time>
    <ip type="str">127.0.0.1</ip>
    <user_agent type="str">desktop-client</user_agent>
  </item>
</result>
```

Отчёт выполняет формулу (1): правое внешнее соединение Actor и
Instruction по `Actor.key = Instruction.actor`, отбор
`Instruction.time >= now - 5*60`, проекция `user_agent`, `content`.
Дубликаты проекции устраняются. Отчёт зависит от времени инструкции,
а не ответа, поэтому включает незавершённые инструкции.
Если связанный Actor отсутствует, `user_agent` имеет тип null.
Публичные операции модели обычно исключают такую ситуацию.

### Пример API-клиента

```python
import base64
from pathlib import Path
import time

from png_gif.client import ApiClient

api = ApiClient("http://127.0.0.1:8001", "student", "png-gif-local")
try:
    api.register_actor(1, {"user_agent": "desktop-client"})
    encoded = base64.b64encode(Path("input.png").read_bytes()).decode("ascii")
    api.register_instruction(1, {"actor": 1, "content": encoded})
    deadline = time.monotonic() + 70
    while not (answers := api.all_response(1)):
        if time.monotonic() >= deadline:
            raise TimeoutError("Conversion did not finish")
        time.sleep(0.1)
    answer = answers[-1]
    if answer["status"] != "done":
        raise RuntimeError(answer["failure"] or answer["status"])
    Path("downloaded.gif").write_bytes(base64.b64decode(answer["output"]))
    print(api.all_report())
finally:
    api.close()
```

Указанные ключи рассчитаны на пустую базу; при повторном запуске
используйте новые ключи либо удалите ранее созданного Actor через API.
Так как таблица 1 требует content в строке запроса, входные изображения
должны помещаться в допустимый размер URL используемого HTTP-сервера
и промежуточного прокси. Для демонстрации используются небольшие PNG.

### Проверки второго этапа

```console
python -m coverage run --data-file=.coverage.file -m pytest tests/test_mbt.py tests/test_workflow.py
python -m coverage report --data-file=.coverage.file
python -m coverage html --data-file=.coverage.file
```

`ApiMachine` наследует `RuleBasedStateMachine`. Hypothesis генерирует
строки, индексы родителей и последовательности операций, сравнивая
результат API с независимыми словарями Actor, Instruction и Response.
У каждого сценария своя папка и FastAPI-приложение. Запросы выполняются
через `ApiClient` и ASGI-транспорт TestClient; обхода маршрутов нет.
Все десять обработчиков обязательно вызываются внутри генерируемых
сценариев, включая авторизованные и неавторизованные запросы.
Обычные тесты CLI не участвуют в отчётах покрытия HTTP.

`test_workflow.py` использует `@given` для проверки реального subprocess,
асинхронности, прозрачности GIF, неверного формата входа, границы
пятиминутного окна, дубликатов проекции, внешнего соединения,
удаления выполняющейся инструкции и восстановления очереди.

### Состав программы

- `schema`: `integer`, `key_value`, `clean`, `record` проверяют типы,
  ключи, имена полей и формируют ER-записи; `ModelError` хранит HTTP-код.
- `file_store.FileStore`: `rows`, `put`, `delete`, `close` управляют
  таблицами; `_save` записывает JSON с атомарной заменой файла и
  повтором при краткой блокировке Windows.
- `model.Model`: десять публичных методов совпадают с таблицей маршрутов;
  `_find`, `_register`, `_all`, `_changes` реализуют общие проверки,
  `start` и `finish` управляют состоянием фоновой инструкции.
- `jobs`: `png_bytes` декодирует Base64; `Jobs.register_instruction`
  и `modify_instruction` сохраняют задания и ставят их в очередь;
  `_loop`, `_execute`, `_convert` выполняют работу; `close` завершает
  очередь и сообщает о непредвиденных ошибках фонового потока.
- `xml_codec`: `fill`, `encode`, `read`, `decode` переводят данные в XML
  и обратно; `filters_from_xml` проверяет XML-фильтры запроса.
- `config`: `Settings` содержит настройки, `load_config` читает INI.
- `routes`: `query` и `delete_key` проверяют query-параметры;
  `actor_router`, `instruction_router`, `report_router` создают
  обработчики из таблицы 1 с соответствующими именами.
- `application`: `XmlResponse.render` создаёт XML; `authorized` проверяет
  Basic; `create_store` выбирает хранилище; `lifespan_for` управляет
  ресурсами; `add_error_handlers` задаёт XML-ошибки; `create_app`
  собирает FastAPI и middleware `authenticate`.
- `client`: десять методов модели отправляют соответствующие запросы;
  `request` возвращает полный HTTP-ответ, `_call` разбирает XML и
  вызывает `ApiError` при ошибке; `close` закрывает HTTP-соединения.
- `server.main`: принимает путь к конфигурации и запускает Uvicorn.
- `tools/check_quality.py`: `inspect_function`, `inspect_ast`,
  `inspect_complexity`, `inspect_file` проверяют ограничения,
  `main` выводит результат проверки исходников, примеров и тестов.
