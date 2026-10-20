from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ReportingPeriod(models.Model):
    """
    Один отчётный период кафедры (напр. «2026-mart» или «31.12.2026 holatiga»).
    Это и есть та точка, к которой привязаны все факт-таблицы показателей —
    вместо того чтобы каждый раз пересоздавать 19 листов вручную, данные
    накапливаются по преподавателям/студентам и группируются запросом по
    reporting_period при формировании отчёта.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик (кафедра вводит данные)")
        SUBMITTED = "submitted", _("Отправлено на согласование")
        APPROVED = "approved", _("Утверждено")

    department = models.ForeignKey(
        "core.Department", on_delete=models.PROTECT, related_name="reporting_periods",
        verbose_name=_("Кафедра"),
    )
    period_label = models.CharField(
        _("Метка периода"), max_length=50, help_text=_("Например: 2026-mart"),
    )
    period_date = models.DateField(_("Дата, на которую формируется отчёт (holatiga)"))
    status = models.CharField(
        _("Статус"), max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="submitted_periods", verbose_name=_("Отправил на согласование"),
    )
    submitted_at = models.DateTimeField(_("Отправлено"), null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_periods", verbose_name=_("Утвердил"),
    )
    approved_at = models.DateTimeField(_("Утверждено"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Отчётный период")
        verbose_name_plural = _("Отчётные периоды")
        unique_together = [("department", "period_label")]
        ordering = ["-period_date"]

    def __str__(self):
        return f"{self.department} — {self.period_label}"
