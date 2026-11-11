"""Проверки файлового конвертера отдельно от покрытия HTTP API."""

from io import BytesIO

from PIL import Image
import pytest

from png_gif.convert import convert


OPAQUE_ALPHA = 255


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "LA", "P"])
def test_modes(tmp_path, mode):
    """PNG разных цветовых режимов сохраняют размер после конвертации."""
    stream = BytesIO()
    Image.new(mode, (13, 27)).save(stream, "PNG")
    output = tmp_path / "nested" / "result.gif"
    assert convert(stream.getvalue(), output) == (13, 27)
    with Image.open(output) as image:
        assert image.format == "GIF"
        assert image.size == (13, 27)


def test_transparency(tmp_path):
    """Порог alpha сохраняет прозрачный и непрозрачный пиксели."""
    source = Image.new("RGBA", (2, 1), (50, 100, 150, 0))
    source.putpixel((1, 0), (255, 0, 0, 255))
    stream = BytesIO()
    source.save(stream, "PNG")
    output = tmp_path / "result.gif"
    convert(stream.getvalue(), output)
    with Image.open(output) as image:
        rgba = image.convert("RGBA")
        assert rgba.getpixel((0, 0))[3] == 0
        assert rgba.getpixel((1, 0))[3] == OPAQUE_ALPHA


def test_non_png(tmp_path):
    """JPEG не должен приниматься вместо PNG."""
    stream = BytesIO()
    Image.new("RGB", (2, 2)).save(stream, "JPEG")
    with pytest.raises(ValueError, match="PNG"):
        convert(stream.getvalue(), tmp_path / "result.gif")
