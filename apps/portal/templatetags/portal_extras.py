from django import template
from django.core.exceptions import FieldDoesNotExist
from django.db.models.fields.files import FieldFile
from django.utils.html import format_html

register = template.Library()


@register.filter(name="getattr")
def getattr_filter(obj, attr_name):
    """Позволяет выводить в шаблоне {{ obj|getattr:col }}, когда имя поля
    приходит динамически (из cfg.list_columns), а не как литерал."""
    return getattr(obj, attr_name, "")


@register.filter
def field_label(model, field_name):
    """Человеческое название колонки (verbose_name поля) вместо имени в коде."""
    try:
        return model._meta.get_field(field_name).verbose_name
    except FieldDoesNotExist:
        return field_name


@register.filter
def display(obj, field_name):
    """Значение для таблицы: подпись из choices, ссылка на файл, «—» для пустого."""
    getter = getattr(obj, f"get_{field_name}_display", None)
    value = getter() if callable(getter) else getattr(obj, field_name, "")
    if isinstance(value, FieldFile):
        if not value:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', value.url)
    if value in (None, ""):
        return "—"
    return value
