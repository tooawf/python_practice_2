"""Чтение PNG из stdin и сохранение однокадрового GIF на диск."""

import argparse
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image


ALPHA_THRESHOLD = 128
TRANSPARENT_INDEX = 255
PALETTE_COLORS = 255


def convert(data, destination):
    """Проверить PNG и сохранить GIF с однобитной прозрачностью."""
    with Image.open(BytesIO(data)) as source:
        if source.format != "PNG":
            raise ValueError("Expected PNG data on standard input")
        image = source.convert("RGBA")
        alpha = image.getchannel("A")
        result = image.convert("RGB").quantize(colors=PALETTE_COLORS)
        mask = alpha.point(lambda value: 255 if value < ALPHA_THRESHOLD else 0)
        options = {}
        if mask.getbbox():
            result.paste(TRANSPARENT_INDEX, mask=mask)
            options["transparency"] = TRANSPARENT_INDEX
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result.save(destination, "GIF", **options)
        return image.size


def main():
    """Принять бинарный PNG из stdin, а путь результата из аргумента CLI."""
    parser = argparse.ArgumentParser(
        description="Read PNG from stdin, save GIF")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        convert(sys.stdin.buffer.read(), args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Conversion failed: {error}\n")


if __name__ == "__main__":
    main()
