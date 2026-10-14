from django.contrib import admin

from apps.core.access import DepartmentScopedAdminMixin

from .models import (
    Publication, TeacherHIndex, Patent, PatentAuthor, Funding,
    PostgradDefense, ReputationVote, TeacherMobility, StudentMobility,
    GraduateEmployment, NationalAvgSalary, IndicatorValue,
)


@admin.register(Publication)
class PublicationAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "teacher__department"
    list_display = ("teacher", "reporting_period", "indexing", "quartile", "citation_tier", "citations_count", "publish_year")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "indexing", "quartile", "citation_tier")
    search_fields = ("teacher__full_name", "article_title", "journal_name")
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(TeacherHIndex)
class TeacherHIndexAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "teacher__department"
    list_display = ("teacher", "reporting_period", "h_index")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period")


class PatentAuthorInline(DepartmentScopedAdminMixin, admin.TabularInline):
    model = PatentAuthor
    extra = 1
    autocomplete_fields = ("teacher",)


@admin.register(Patent)
class PatentAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "reporting_period__department"
    list_display = ("title", "reporting_period", "patent_type", "registered_in_scopus", "has_license_agreement")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "patent_type", "registered_in_scopus")
    search_fields = ("title",)
    autocomplete_fields = ("reporting_period",)
    inlines = [PatentAuthorInline]


@admin.register(Funding)
class FundingAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "teacher__department"
    list_display = ("teacher", "reporting_period", "source_type", "amount")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "source_type")
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(PostgradDefense)
class PostgradDefenseAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "advisor_teacher__department"
    list_display = ("advisor_teacher", "reporting_period", "degree_type", "defended_full_name")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "degree_type")
    search_fields = ("advisor_teacher__full_name", "defended_full_name")
    autocomplete_fields = ("advisor_teacher", "reporting_period")


@admin.register(ReputationVote)
class ReputationVoteAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "teacher__department"
    list_display = ("teacher", "reporting_period", "source", "votes_count")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "source")
    search_fields = ("teacher__full_name",)
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(TeacherMobility)
class TeacherMobilityAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "teacher__department"
    list_display = ("teacher", "reporting_period", "direction", "partner_institution_name")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "direction")
    search_fields = ("teacher__full_name", "partner_institution_name")
    autocomplete_fields = ("teacher", "reporting_period")


@admin.register(StudentMobility)
class StudentMobilityAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "student__department"
    list_display = ("student", "reporting_period", "direction", "program_type", "partner_rank")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "program_type", "partner_rank")
    search_fields = ("student__full_name",)
    autocomplete_fields = ("student", "reporting_period")


@admin.register(GraduateEmployment)
class GraduateEmploymentAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "graduate__department"
    list_display = ("graduate", "reporting_period", "status", "months_to_employment", "monthly_income")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "status")
    search_fields = ("graduate__full_name",)
    autocomplete_fields = ("graduate", "reporting_period")


@admin.register(NationalAvgSalary)
class NationalAvgSalaryAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "amount")
    ordering = ("-year", "-month")


@admin.register(IndicatorValue)
class IndicatorValueAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "reporting_period__department"
    list_display = ("indicator_code", "subject_type", "subject_id", "reporting_period", "value_numeric", "value_text")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), "subject_type")
    search_fields = ("indicator_code",)
    autocomplete_fields = ("reporting_period",)
