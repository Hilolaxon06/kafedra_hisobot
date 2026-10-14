"""
Админ-панель в упрощённом виде для завкафедрой (is_staff, но не суперпользователь):
понятные узбекские названия разделов, описания, иконки и счётчики записей
(уже ограниченные своей кафедрой — через get_queryset() соответствующей ModelAdmin).
Суперпользователь видит стандартную админку Django.
"""

from django import template
from django.contrib import admin
from django.utils.safestring import mark_safe

from apps.core.access import managed_departments
from apps.core.labels import APP_NAMES, MODELS, SECTIONS

register = template.Library()

ICONS = {
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 3-5.5 6.5-5.5s6.5 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.8c2.2.6 3.5 2.4 3.5 5.2"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16"/>',
    "doc": '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h7"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "award": '<circle cx="12" cy="9" r="6"/><path d="m8.5 14-1.5 7 5-3 5 3-1.5-7"/>',
    "money": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
    "cap": '<path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5"/>',
    "star": '<path d="m12 3 2.8 5.8 6.2.9-4.5 4.4 1 6.2L12 17.4 6.5 20.3l1-6.2L3 9.7l6.2-.9z"/>',
    "plane": '<path d="M2 16l20-8-6 13-3-6z"/><path d="m13 15-4 4"/>',
    "brief": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M17 6l3 3M15 8l2 2"/>',
}


def _label(model_dict):
    model = model_dict.get("model")
    return model._meta.label_lower if model is not None else ""


@register.filter
def is_mudiri(user):
    """Завкафедрой: зашёл в админку, но не суперпользователь."""
    return bool(getattr(user, "is_staff", False) and not getattr(user, "is_superuser", False))


@register.simple_tag
def kh_model_name(model_dict):
    info = MODELS.get(_label(model_dict))
    return info[1] if info else model_dict.get("name", "")


@register.simple_tag
def kh_app_name(app_dict):
    return APP_NAMES.get(app_dict.get("app_label"), app_dict.get("name", ""))


@register.simple_tag
def kh_icon(name):
    return mark_safe(f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICONS.get(name, ICONS["list"])}</svg>')


@register.simple_tag(takes_context=True)
def kh_dashboard(context, app_list):
    """Разделы с карточками для главной страницы админки завкафедрой."""
    request = context["request"]
    order = {label: i for i, label in enumerate(MODELS)}
    buckets = {key: [] for key, _t, _d in SECTIONS}
    for app in app_list:
        for m in app["models"]:
            label = _label(m)
            section, name, desc, icon = MODELS.get(label, ("other", m["name"], "", "list"))
            count = None
            model_admin = admin.site._registry.get(m.get("model"))
            if model_admin is not None and m.get("admin_url"):
                try:
                    count = model_admin.get_queryset(request).count()
                except Exception:  # счётчик — не критично для страницы
                    count = None
            buckets[section].append({
                "name": name, "desc": desc, "icon": icon, "count": count,
                "admin_url": m.get("admin_url"), "add_url": m.get("add_url"),
                "view_only": m.get("view_only"), "order": order.get(label, len(order)),
            })
    sections = []
    for key, title, desc in SECTIONS:
        cards = sorted(buckets[key], key=lambda c: c["order"])
        if cards:
            sections.append({"key": key, "title": title, "desc": desc, "cards": cards})
    return sections


@register.simple_tag(takes_context=True)
def kh_departments(context):
    return managed_departments(context["request"].user)
