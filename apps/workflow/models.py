from django.conf import settings
from django.db import models


class ReportingPeriod(models.Model):
    """
    Один отчётный период кафедры (напр. «2026-mart» или «31.12.2026 holatiga»).
    Это и есть та точка, к которой привязаны все факт-таблицы показателей —
    вместо того чтобы каждый раз пересоздавать 19 листов вручную, данные
    накапливаются по преподавателям/студентам и группируются запросом по
    reporting_period при формировании отчёта.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик (кафедра вводит данные)"
        SUBMITTED = "submitted", "Отправлено на согласование"
        APPROVED = "approved", "Утверждено"

    department = models.ForeignKey(
        "core.Department", on_delete=models.PROTECT, related_name="reporting_periods",
        verbose_name="Кафедра",
    )
    period_label = models.CharField(
        "Метка периода", max_length=50, help_text="Например: 2026-mart",
    )
    period_date = models.DateField("Дата, на которую формируется отчёт (holatiga)")
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.DRAFT,
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="submitted_periods", verbose_name="Отправил на согласование",
    )
    submitted_at = models.DateTimeField("Отправлено", null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_periods", verbose_name="Утвердил",
    )
    approved_at = models.DateTimeField("Утверждено", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Отчётный период"
        verbose_name_plural = "Отчётные периоды"
        unique_together = [("department", "period_label")]
        ordering = ["-period_date"]

    def __str__(self):
        return f"{self.department} — {self.period_label}"
