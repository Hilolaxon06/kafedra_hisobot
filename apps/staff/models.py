from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import Department
from apps.dictionaries.models import EmploymentType, Position, AcademicDegree, AcademicTitle
from apps.workflow.models import ReportingPeriod


class Teacher(models.Model):
    """
    Мастер-запись преподавателя. Всё, что меняется от периода к периоду
    (должность, ставка, степень на момент отчёта — как в 5-jadval), хранится
    в TeacherPeriodSnapshot, а не здесь, чтобы не терять историю.
    """

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="teachers",
        verbose_name=_("Кафедра"),
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teacher_profile",
        verbose_name=_("Логин в системе"),
        help_text=_("Заводится кафедрой через действие «Создать логин» в списке преподавателей — "
                    "даёт доступ в личный кабинет, где преподаватель сам вносит свои показатели."),
    )
    full_name = models.CharField(_("Ф.И.Ш. (полностью)"), max_length=255)
    birth_date = models.DateField(_("Дата рождения"), null=True, blank=True)

    specialty_name = models.CharField(
        _("Специальность по диплому об учёной степени"), max_length=255, blank=True,
    )
    diploma_series = models.CharField(_("Серия диплома"), max_length=10, blank=True)
    diploma_number = models.CharField(_("Номер диплома"), max_length=20, blank=True)
    diploma_file = models.FileField(
        _("Скан диплома об учёной степени (PDF)"), upload_to="teachers/diplomas/",
        null=True, blank=True,
    )
    foreign_university_name = models.CharField(
        _("Зарубежный ОТМ, присвоивший степень"), max_length=255, blank=True,
    )

    hire_order_number = models.CharField(_("№ приказа о приёме"), max_length=50, blank=True)
    hire_order_date = models.DateField(_("Дата приказа о приёме"), null=True, blank=True)

    is_active = models.BooleanField(_("Работает сейчас"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Преподаватель")
        verbose_name_plural = _("Преподаватели")
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    @property
    def age(self):
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )


class TeacherPeriodSnapshot(models.Model):
    """
    Снимок статуса преподавателя на конкретный отчётный период — покрывает
    5-jadval (штатная ведомость): тип занятости, должность, ставка, степень
    и звание могут отличаться от периода к периоду.
    """

    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="period_snapshots",
        verbose_name=_("Преподаватель"),
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_snapshots",
        verbose_name=_("Отчётный период"),
    )
    employment_type = models.ForeignKey(
        EmploymentType, on_delete=models.PROTECT, verbose_name=_("Тип занятости"),
    )
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, null=True, blank=True, verbose_name=_("Должность"),
    )
    stavka = models.DecimalField(_("Ставка"), max_digits=4, decimal_places=2, default=1)
    academic_degree = models.ForeignKey(
        AcademicDegree, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Учёная степень на момент отчёта"),
    )
    academic_title = models.ForeignKey(
        AcademicTitle, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Учёное звание на момент отчёта"),
    )

    class Meta:
        verbose_name = _("Снимок статуса ППС за период")
        verbose_name_plural = _("Снимки статуса ППС за период")
        unique_together = [("teacher", "reporting_period")]
        ordering = ["reporting_period", "employment_type__sort_order", "teacher__full_name"]

    def __str__(self):
        return f"{self.teacher} — {self.reporting_period}"
