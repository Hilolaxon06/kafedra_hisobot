from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin, UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, Permission

from .access import DepartmentScopedAdminMixin, managed_departments
from .models import University, Faculty, Department
from .permissions import PermissionMatrixWidget, relevant_permissions

admin.site.site_header = "Kafedra hisoboti — boshqaruv paneli"
admin.site.site_title = "Kafedra hisoboti"
admin.site.index_title = "Bosh sahifa"


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("short_name", "name")
    search_fields = ("name", "short_name")


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "university")
    list_filter = ("university",)
    search_fields = ("name", "short_name")
    autocomplete_fields = ("university",)


@admin.register(Department)
class DepartmentAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = ""
    list_display = ("name", "short_name", "faculty")
    list_filter = ("faculty__university", "faculty")
    search_fields = ("name", "short_name")
    autocomplete_fields = ("faculty",)


# ---------------------------------------------------------------------------
# Группы и пользователи: вместо двух длинных списков со всеми правами системы
# показываем таблицу только тех прав, что нужны кафедре (см. permissions.py).
#
# Завкафедрой (не суперпользователь) видит только своё:
# - пользователей — только логины преподавателей своей кафедры;
# - группы — только те, в которых состоят преподаватели его кафедры;
# - выдать может лишь те права, что есть у него самого, а сделать кого-то
#   суперпользователем, создать/удалить логин или группу — не может
#   (логины преподавателям создаются действием «Создать логин» в списке
#   преподавателей).
# ---------------------------------------------------------------------------
def _department_users(request):
    return User.objects.filter(teacher_profile__department__in=managed_departments(request.user))


def _department_groups(request):
    return Group.objects.filter(user__in=_department_users(request)).distinct()


class DepartmentAuthMixin:
    permission_fields = ("permissions", "user_permissions")

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in self.permission_fields:
            perms = relevant_permissions()
            if not request.user.is_superuser:
                # нельзя выдать права, которых нет у самого завкафедрой
                perms = perms.filter(pk__in=request.user.user_permissions.all()) | perms.filter(
                    pk__in=Permission.objects.filter(group__user=request.user))
                perms = perms.distinct()
            kwargs["queryset"] = perms
            kwargs["widget"] = PermissionMatrixWidget()
        elif db_field.name == "groups" and not request.user.is_superuser:
            kwargs["queryset"] = _department_groups(request)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)


User = get_user_model()
admin.site.unregister(Group)
admin.site.unregister(User)


@admin.register(Group)
class GroupAdmin(DepartmentAuthMixin, BaseGroupAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(pk__in=_department_groups(request))


@admin.register(User)
class UserAdmin(DepartmentAuthMixin, BaseUserAdmin):
    list_display = ("username", "teacher_name", "teacher_department", "is_staff", "is_active", "last_login")

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("teacher_profile__department")
        if request.user.is_superuser:
            return qs
        return qs.filter(pk__in=_department_users(request))

    def get_list_filter(self, request):
        if request.user.is_superuser:
            return super().get_list_filter(request)
        return ("is_staff", "is_active")

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            readonly = (*readonly, "is_superuser", "last_login", "date_joined")
        return readonly

    @admin.display(description="O‘qituvchi", ordering="teacher_profile__full_name")
    def teacher_name(self, obj):
        teacher = getattr(obj, "teacher_profile", None)
        return teacher.full_name if teacher else "—"

    @admin.display(description="Kafedra", ordering="teacher_profile__department__name")
    def teacher_department(self, obj):
        teacher = getattr(obj, "teacher_profile", None)
        return teacher.department if teacher else "—"
