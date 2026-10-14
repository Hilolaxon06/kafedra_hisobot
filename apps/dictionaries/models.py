from django.db import models


class EmploymentType(models.Model):
    """asosiy shtat / ichki o'rindosh / tashqi o'rindosh / soatbay."""

    ASOSIY = "asosiy"
    ICHKI = "ichki_orindosh"
    TASHQI = "tashqi_orindosh"
    SOATBAY = "soatbay"

    code = models.CharField("Код", max_length=30, unique=True)
    name = models.CharField("Название", max_length=100)
    sort_order = models.PositiveSmallIntegerField("Порядок в отчёте", default=0)

    class Meta:
        verbose_name = "Тип занятости"
        verbose_name_plural = "Типы занятости"
        ordering = ["sort_order"]

    def __str__(self):
        return self.name


class Position(models.Model):
    name = models.CharField("Название должности", max_length=100, unique=True)

    class Meta:
        verbose_name = "Должность (лавозим)"
        verbose_name_plural = "Должности (лавозимлар)"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicDegree(models.Model):
    """Fan nomzodi / PhD / Fan doktori / DSc."""

    code = models.CharField("Код", max_length=20, unique=True)
    name = models.CharField("Название", max_length=100)

    class Meta:
        verbose_name = "Учёная степень"
        verbose_name_plural = "Учёные степени"
        ordering = ["name"]

    def __str__(self):
        return self.name


class AcademicTitle(models.Model):
    """Dotsent / Professor."""

    name = models.CharField("Название", max_length=100, unique=True)

    class Meta:
        verbose_name = "Учёное звание"
        verbose_name_plural = "Учёные звания"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Country(models.Model):
    class Category(models.TextChoices):
        HIGH_INCOME = "high_income_developed", "Юқори даромадли ривожланган мамлакат"
        CENTRAL_ASIA = "central_asia", "Марказий Осиё давлати"
        OTHER = "other", "Бошқа давлат"

    name = models.CharField("Название страны", max_length=100, unique=True)
    category = models.CharField(
        "Категория (для отчётов по мобильности)", max_length=30,
        choices=Category.choices, default=Category.OTHER,
    )

    class Meta:
        verbose_name = "Страна"
        verbose_name_plural = "Страны"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ForeignInstitutionRank(models.TextChoices):
    """TOP-100 / TOP-300 / TOP-500 / TOP-1000 / вне рейтинга — повторяется
    в нескольких листах (мобильность, совместные программы, зарубежные
    степени), поэтому вынесено в общий справочник-перечисление."""

    TOP100 = "TOP100", "TOP-100"
    TOP300 = "TOP300", "TOP-300"
    TOP500 = "TOP500", "TOP-500"
    TOP1000 = "TOP1000", "TOP-1000"
    OTHER = "other", "Вне рейтинга TOP-1000"
