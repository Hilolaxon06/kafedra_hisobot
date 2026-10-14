"""
Какие права вообще имеет смысл выдавать завкафедрой (группам кафедр).

Стандартный виджет Django показывает ~100 прав, включая технические
(журнал admin, сессии, типы контента, пользователи и группы) — завкафедрой
они не нужны и только путают. Здесь — белый список: модели, которые кафедра
ведёт сама (полные права), и справочники, которые ей нужно только видеть
(для выпадающих списков и автодополнения в формах).

Используется в GroupAdmin / UserAdmin (apps/core/admin.py) — и для
фильтрации списка, и для кнопки «Отметить рекомендуемые».
"""

from django import forms
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils.text import capfirst

from .labels import MODELS, SECTIONS

ACTIONS = [
    ("view", "Ko‘rish"),
    ("add", "Qo‘shish"),
    ("change", "O‘zgartirish"),
    ("delete", "O‘chirish"),
]

# app_label -> модели (model_name), которые кафедра ведёт сама
FULL_ACCESS = {
    "staff": ["teacher", "teacherperiodsnapshot"],
    "students": ["student", "graduate"],
    "workflow": ["reportingperiod"],
    "reports": [
        "publication", "teacherhindex", "patent", "patentauthor", "funding",
        "postgraddefense", "reputationvote", "teachermobility", "studentmobility",
        "graduateemployment",
    ],
}

# справочники: завкафедрой их только просматривает
VIEW_ONLY = {
    "core": ["department"],
    "dictionaries": ["employmenttype", "position", "academicdegree", "academictitle", "country"],
    "reports": ["nationalavgsalary"],
}

def _models_q(mapping, actions=None):
    q = Q(pk__in=[])
    for app_label, models in mapping.items():
        cond = Q(content_type__app_label=app_label, content_type__model__in=models)
        if actions:
            cond &= Q(codename__regex=r"^(%s)_" % "|".join(actions))
        q |= cond
    return q


def relevant_permissions():
    """Права, которые показываются при настройке группы/пользователя."""
    return (Permission.objects
            .filter(_models_q(FULL_ACCESS) | _models_q(VIEW_ONLY))
            .select_related("content_type"))


def recommended_permission_ids():
    """Набор «завкафедрой по умолчанию»: всё по своим моделям + просмотр справочников."""
    return set(Permission.objects
               .filter(_models_q(FULL_ACCESS) | _models_q(VIEW_ONLY, actions=["view"]))
               .values_list("pk", flat=True))


class PermissionMatrixWidget(forms.CheckboxSelectMultiple):
    """Права в виде таблицы: строка — раздел данных, колонки —
    Ko‘rish / Qo‘shish / O‘zgartirish / O‘chirish. Отправляет то же, что и
    обычный CheckboxSelectMultiple (список id), поэтому форма не меняется."""

    template_name = "core/widgets/permission_matrix.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        selected = set(context["widget"]["value"])
        recommended = recommended_permission_ids()
        model_order = {label: i for i, label in enumerate(MODELS)}

        rows = {}
        for perm in self.choices.queryset.select_related("content_type"):
            ct = perm.content_type
            action = perm.codename.split("_", 1)[0]
            if action not in dict(ACTIONS):
                continue
            label = f"{ct.app_label}.{ct.model}"
            row = rows.get(label)
            if row is None:
                model = ct.model_class()
                info = MODELS.get(label)
                row = rows[label] = {
                    "section": info[0] if info else "other",
                    "label": info[1] if info else capfirst(model._meta.verbose_name_plural if model else ct.model),
                    "order": model_order.get(label, len(model_order)),
                    "cells": {},
                }
            row["cells"][action] = {
                "id": perm.pk, "checked": str(perm.pk) in selected,
                "recommended": perm.pk in recommended, "title": perm.name,
            }

        by_section = {}
        for row in sorted(rows.values(), key=lambda r: r["order"]):
            row["cells"] = [row["cells"].get(code) for code, _label in ACTIONS]
            by_section.setdefault(row["section"], []).append(row)
        sections = [{"title": title, "rows": by_section[key]}
                    for key, title, _desc in SECTIONS if key in by_section]

        context["widget"]["sections"] = sections
        context["widget"]["actions"] = ACTIONS
        return context
