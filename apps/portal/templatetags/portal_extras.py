from decimal import Decimal

from django import template
from django.core.exceptions import FieldDoesNotExist
from django.db.models.fields.files import FieldFile
from django.utils.html import format_html
from django.utils.translation import gettext as _

register = template.Library()


@register.filter(name="getattr")
def getattr_filter(obj, attr_name):
    """Позволяет выводить в шаблоне {{ obj|getattr:col }}, когда имя поля
    приходит динамически (из cfg.list_columns), а не как литерал."""
    return getattr(obj, attr_name, "")


@register.filter
def field_label(model, field_name):
    """Человеческое название колонки (verbose_name поля или short_description
    свойства модели) вместо имени в коде."""
    try:
        return model._meta.get_field(field_name).verbose_name
    except FieldDoesNotExist:
        attr = getattr(model, field_name, None)
        return getattr(getattr(attr, "fget", attr), "short_description", field_name)


@register.filter
def display(obj, field_name):
    """Значение для таблицы: подпись из choices, ссылка на файл, «—» для пустого."""
    getter = getattr(obj, f"get_{field_name}_display", None)
    value = getter() if callable(getter) else getattr(obj, field_name, "")
    if isinstance(value, FieldFile):
        if not value:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">PDF</a>', value.url)
    if isinstance(value, bool):
        return format_html('<span class="badge {}">{}</span>',
                           "status-approved" if value else "neutral", _("ha") if value else _("yo‘q"))
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if value in (None, ""):
        return "—"
    return value
