"""
Кто какие кафедры видит.

- Суперпользователь — все кафедры.
- Сотрудник (is_staff), у которого есть карточка преподавателя, — только
  кафедру из этой карточки (завкафедрой — тоже преподаватель своей кафедры).
- Все остальные — ничего.

Используется и в /hisobot/, и в админ-панели (DepartmentScopedAdminMixin),
чтобы завкафедрой не видел и не мог выбрать чужие данные.
"""

from .models import Department


def managed_departments(user):
    if not user.is_authenticated:
        return Department.objects.none()
    if user.is_superuser:
        return Department.objects.all()
    teacher = getattr(user, "teacher_profile", None)
    if user.is_staff and teacher is not None:
        return Department.objects.filter(pk=teacher.department_id)
    return Department.objects.none()


# модель (app_label.ModelName) -> путь от неё к кафедре; "" — это сама кафедра
_DEPARTMENT_PATHS = {
    "core.Department": "",
    "staff.Teacher": "department",
    "workflow.ReportingPeriod": "department",
    "students.Student": "department",
    "students.Graduate": "department",
}


def _scope(queryset, path, user):
    lookup = f"{path}__in" if path else "pk__in"
    return queryset.filter(**{lookup: managed_departments(user)})


class DepartmentScopedAdminMixin:
    """Для ModelAdmin и инлайнов: список, карточки и выпадающие списки
    (кафедра, преподаватель, период, студент, выпускник) ограничены кафедрой
    пользователя. department_path — путь от модели админки к кафедре;
    None — саму модель не фильтровать (только выпадающие списки)."""

    department_path = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.department_path is None or request.user.is_superuser:
            return qs
        return _scope(qs, self.department_path, request.user).distinct()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        path = _DEPARTMENT_PATHS.get(db_field.related_model._meta.label)
        if path is not None and not request.user.is_superuser:
            kwargs["queryset"] = _scope(db_field.related_model._default_manager.all(), path, request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
