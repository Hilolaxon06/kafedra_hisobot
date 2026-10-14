from django.contrib import admin

from apps.core.access import DepartmentScopedAdminMixin

from .models import Student, Graduate


@admin.register(Student)
class StudentAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "department"
    list_display = ("full_name", "department", "degree_level", "citizenship_country")
    list_filter = (("department", admin.RelatedOnlyFieldListFilter), "degree_level", "citizenship_country__category")
    search_fields = ("full_name",)
    autocomplete_fields = ("department", "citizenship_country")


@admin.register(Graduate)
class GraduateAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "department"
    list_display = ("full_name", "department", "graduation_year", "student")
    list_filter = (("department", admin.RelatedOnlyFieldListFilter), "graduation_year")
    search_fields = ("full_name",)
    autocomplete_fields = ("department", "student")
