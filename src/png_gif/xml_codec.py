"""Простой типизированный XML без потери пустых строк и числовых полей."""

from xml.etree.ElementTree import Element, SubElement, tostring

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

from png_gif.schema import ModelError


def fill(element, value):
    """Рекурсивно записать словарь, список или скаляр в XML-элемент."""
    if isinstance(value, dict):
        element.set("type", "object")
        for name, item in value.items():
            fill(SubElement(element, name), item)
    elif isinstance(value, list):
        element.set("type", "list")
        for item in value:
            fill(SubElement(element, "item"), item)
    elif value is None:
        element.set("type", "null")
    else:
        element.set("type", "int" if isinstance(value, int) else "str")
        element.text = str(value)


def encode(value, root="result"):
    """Сериализовать результат API или XML-фильтры в UTF-8."""
    element = Element(root)
    fill(element, value)
    return tostring(element, encoding="utf-8", xml_declaration=True)


def read(element):
    """Восстановить Python-значения из типизированного ответа API."""
    kind = element.get("type")
    if kind == "object":
        return {child.tag: read(child) for child in element}
    if kind == "list":
        return [read(child) for child in element]
    if kind == "null":
        return None
    if kind == "int":
        return int(element.text)
    return element.text or ""


def decode(data):
    """Прочитать типизированный XML-ответ на стороне API-клиента."""
    return read(fromstring(data))


def filters_from_xml(data):
    """Принять только плоский filters без DTD и повторяющихся полей."""
    try:
        root = fromstring(data)
    except (ValueError, DefusedXmlException) as error:
        raise ModelError("Invalid XML") from error
    except Exception as error:
        raise ModelError("Malformed XML") from error
    if root.tag != "filters":
        raise ModelError("Expected filters root")
    values = {}
    for child in root:
        if len(child) or child.tag in values:
            raise ModelError("Filters must have unique scalar fields")
        values[child.tag] = child.text or ""
    return values
