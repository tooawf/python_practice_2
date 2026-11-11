"""Пять воспроизводимых PNG: бинарный stdin → subprocess → GIF."""

from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image


CASES = (
    ("color", "RGB", (64, 48), "red"),
    ("grayscale", "L", (73, 51), 128),
    ("transparent", "RGBA", (90, 60), (0, 100, 200, 0)),
    ("palette", "P", (120, 40), 17),
    ("single_pixel", "RGB", (1, 1), "white"),
)


def run_case(case, folder):
    """Передать содержимое PNG в stdin CLI и проверить полученный GIF."""
    name, mode, size, color = case
    source = BytesIO()
    Image.new(mode, size, color).save(source, "PNG")
    data = source.getvalue()
    (folder / f"{name}.png").write_bytes(data)
    output = folder / f"{name}.gif"
    subprocess.run([sys.executable, "-m", "png_gif.convert", str(output)],
                   input=data, check=True)
    with Image.open(output) as image:
        assert image.format == "GIF"
        assert image.size == size
    return {"name": name, "mode": mode, "size": size, "ok": True}


def main():
    """Создать изображения локально, в git сохранить текстовый протокол."""
    folder = Path(__file__).parent / "generated"
    folder.mkdir(exist_ok=True)
    result = [run_case(case, folder) for case in CASES]
    text = json.dumps(result, indent=2)
    (folder.parent / "results.json").write_text(text + "\n", "utf-8")
    print(text)


if __name__ == "__main__":
    main()
