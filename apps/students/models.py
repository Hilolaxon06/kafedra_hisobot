from django.db import models

from apps.core.models import Department
from apps.dictionaries.models import Country


class Student(models.Model):
    class DegreeLevel(models.TextChoices):
        BACHELOR = "bakalavriat", "Бакалавриат"
        MASTER = "magistratura", "Магистратура"

    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="students",
        verbose_name="Кафедра",
    )
    full_name = models.CharField("Ф.И.Ш.", max_length=255)
    degree_level = models.CharField(
        "Уровень обучения", max_length=20, choices=DegreeLevel.choices,
        default=DegreeLevel.BACHELOR,
    )
    citizenship_country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="students",
        verbose_name="Гражданство",
    )

    class Meta:
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Graduate(models.Model):
    """
    Выпускник. Связан со Student, когда запись велась ещё во время учёбы;
    student может быть пустым, если выпускник заводится сразу постфактум
    (например, при первичном заполнении отчётности за прошлые годы).
    """

    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="graduate_record", verbose_name="Запись студента (если есть)",
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="graduates",
        verbose_name="Кафедра",
    )
    full_name = models.CharField("Ф.И.Ш.", max_length=255)
    graduation_year = models.PositiveSmallIntegerField("Год выпуска")

    class Meta:
        verbose_name = "Выпускник"
        verbose_name_plural = "Выпускники"
        ordering = ["-graduation_year", "full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.graduation_year})"
