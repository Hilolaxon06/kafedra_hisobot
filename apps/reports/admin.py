from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.core.access import DepartmentScopedAdminMixin

from .coauthors import department_year_publications, entries_per_article, mismatched
from .models import (
    Publication, TeacherHIndex, Patent, PatentAuthor, Funding,
    PostgradDefense, ReputationVote, TeacherMobility, StudentMobility,
    GraduateEmployment, NationalAvgSalary, IndicatorValue,
)


class CoAuthorsMismatchFilter(admin.SimpleListFilter):
    """Статьи, которые внесло больше сотрудников кафедры, чем указанное N."""

    title = _("Число соавторов")
    parameter_name = "coauthors"

    def lookups(self, request, model_admin):
        return [("mismatch", _("N меньше числа внесших статью"))]

    def queryset(self, request, queryset):
        if self.value() != "mismatch":
            return queryset
        scope = (Publication.objects
                 .filter(reporting_period__department__in=queryset.values("reporting_period__department"))
                 .select_related("reporting_period"))
        return queryset.filter(pk__in=[pub.pk for pub in mismatched(scope)])


@admin.register(Publication)
class PublicationAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    """Завкафедрой проверяет число соавторов-сотрудников (от него зависит доля
    1/N в рейтинге и листе 2,1) и исправляет прямо в списке."""

    department_path = "teacher__department"
    list_display = ("teacher", "article_title", "reporting_period", "indexing", "quartile",
                    "department_co_authors_count", "entries_display", "share_display", "co_authors_checked")
    list_editable = ("department_co_authors_count", "co_authors_checked")
    list_filter = (("reporting_period", admin.RelatedOnlyFieldListFilter), CoAuthorsMismatchFilter, "co_authors_checked",
                   "indexing", "quartile", "citation_tier")
    search_fields = ("teacher__full_name", "article_title", "journal_name")
    autocomplete_fields = ("teacher", "reporting_period")
    actions = ["mark_co_authors_checked"]

    @admin.display(description=_("Внесли статью на кафедре"))
    def entries_display(self, obj):
        period = obj.reporting_period
        entries = entries_per_article(
            department_year_publications(period.department_id, period.period_date.year))[obj.pk]
        if entries > (obj.department_co_authors_count or 1):
            return format_html('<b style="color:var(--error-fg, #ba2121)">{} ⚠</b>', entries)
        return entries

    @admin.display(description=_("Доля (1/N)"))
    def share_display(self, obj):
        return f"{obj.share:.2f}"

    @admin.action(description=_("Отметить: число соавторов проверено"))
    def mark_co_authors_checked(self, request, queryset):
        updated = queryset.update(co_authors_checked=True)
        self.message_user(request, _("Tasdiqlandi: %(n)s ta maqola.") % {"n": updated})

    def save_model(self, request, obj, form, change):
        # исправленное завкафедрой число считается проверенным
        if "department_co_authors_count" in form.changed_data:
            obj.co_authors_checked = True
        super().save_model(request, obj, form, change)


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
