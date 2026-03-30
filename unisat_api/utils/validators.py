# utils/validators.py

from typing import Any


def is_bbox(value: Any) -> bool:
    """Проверяет, является ли значение корректным BBOX (minx, miny, maxx, maxy)"""
    if not isinstance(value, (list, tuple)):
        return False
    if len(value) != 4:
        return False
    return all(isinstance(x, (int, float)) for x in value)


def is_date_or_datetime(value: Any) -> bool:
    """Проверяет, является ли значение корректной датой/временем в строковом формате"""
    if not isinstance(value, str):
        return False
    # Простая проверка на наличие разделителей даты
    return 'T' in value or value.count('-') >= 2


def is_list_of_strings(value: Any) -> bool:
    """Проверяет, является ли значение списком строк"""
    if not isinstance(value, list):
        return False
    return all(isinstance(item, str) for item in value)


def is_number(value: Any) -> bool:
    """Проверяет, является ли значение числом"""
    return isinstance(value, (int, float))