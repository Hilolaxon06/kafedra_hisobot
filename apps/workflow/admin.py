from django.contrib import admin
from django.utils import timezone

from apps.core.access import DepartmentScopedAdminMixin

from .models import ReportingPeriod


@admin.register(ReportingPeriod)
class ReportingPeriodAdmin(DepartmentScopedAdminMixin, admin.ModelAdmin):
    department_path = "department"
    list_display = ("department", "period_label", "period_date", "status", "approved_at")
    list_filter = ("status", ("department", admin.RelatedOnlyFieldListFilter))
    search_fields = ("period_label",)
    autocomplete_fields = ("department",)
    readonly_fields = ("submitted_by", "submitted_at", "approved_by", "approved_at")
    actions = ["mark_submitted", "mark_approved"]

    @admin.action(description="Отметить как «отправлено на согласование»")
    def mark_submitted(self, request, queryset):
        queryset.update(
            status=ReportingPeriod.Status.SUBMITTED,
            submitted_by=request.user,
            submitted_at=timezone.now(),
        )

    @admin.action(description="Утвердить период")
    def mark_approved(self, request, queryset):
        queryset.update(
            status=ReportingPeriod.Status.APPROVED,
            approved_by=request.user,
            approved_at=timezone.now(),
        )
