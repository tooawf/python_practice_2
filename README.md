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
