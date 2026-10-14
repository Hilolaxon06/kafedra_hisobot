from django.conf import settings
from django.db import models

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
        verbose_name="Кафедра",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teacher_profile",
        verbose_name="Логин в системе",
        help_text="Заводится кафедрой через действие «Создать логин» в списке преподавателей — "
                   "даёт доступ в личный кабинет, где преподаватель сам вносит свои показатели.",
    )
    full_name = models.CharField("Ф.И.Ш. (полностью)", max_length=255)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)

    specialty_name = models.CharField(
        "Специальность по диплому об учёной степени", max_length=255, blank=True,
    )
    diploma_series = models.CharField("Серия диплома", max_length=10, blank=True)
    diploma_number = models.CharField("Номер диплома", max_length=20, blank=True)
    diploma_file = models.FileField(
        "Скан диплома об учёной степени (PDF)", upload_to="teachers/diplomas/",
        null=True, blank=True,
    )
    foreign_university_name = models.CharField(
        "Зарубежный ОТМ, присвоивший степень", max_length=255, blank=True,
    )

    hire_order_number = models.CharField("№ приказа о приёме", max_length=50, blank=True)
    hire_order_date = models.DateField("Дата приказа о приёме", null=True, blank=True)

    is_active = models.BooleanField("Работает сейчас", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
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
        verbose_name="Преподаватель",
    )
    reporting_period = models.ForeignKey(
        ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_snapshots",
        verbose_name="Отчётный период",
    )
    employment_type = models.ForeignKey(
        EmploymentType, on_delete=models.PROTECT, verbose_name="Тип занятости",
    )
    position = models.ForeignKey(
        Position, on_delete=models.PROTECT, null=True, blank=True, verbose_name="Должность",
    )
    stavka = models.DecimalField("Ставка", max_digits=4, decimal_places=2, default=1)
    academic_degree = models.ForeignKey(
        AcademicDegree, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Учёная степень на момент отчёта",
    )
    academic_title = models.ForeignKey(
        AcademicTitle, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Учёное звание на момент отчёта",
    )

    class Meta:
        verbose_name = "Снимок статуса ППС за период"
        verbose_name_plural = "Снимки статуса ППС за период"
        unique_together = [("teacher", "reporting_period")]
        ordering = ["reporting_period", "employment_type__sort_order", "teacher__full_name"]

    def __str__(self):
        return f"{self.teacher} — {self.reporting_period}"
