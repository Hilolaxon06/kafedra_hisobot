from django.db import models


class University(models.Model):
    name = models.CharField("Название (полное)", max_length=255)
    short_name = models.CharField("Короткое название", max_length=50, blank=True)

    class Meta:
        verbose_name = "Университет"
        verbose_name_plural = "Университеты"
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name


class Faculty(models.Model):
    university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="faculties",
        verbose_name="Университет",
    )
    name = models.CharField("Название факультета", max_length=255)
    short_name = models.CharField("Короткое название", max_length=50, blank=True)

    class Meta:
        verbose_name = "Факультет"
        verbose_name_plural = "Факультеты"
        ordering = ["name"]
        unique_together = [("university", "name")]

    def __str__(self):
        return self.short_name or self.name


class Department(models.Model):
    """
    Единая сущность «кафедра». Намеренно только одна таблица — в исходной
    ERD-схеме вуза кафедра была продублирована как departments и kafedralar
    с неочевидной связью между ними; здесь эта путаница устранена.
    """

    faculty = models.ForeignKey(
        Faculty, on_delete=models.PROTECT, related_name="departments",
        verbose_name="Факультет",
    )
    name = models.CharField("Название кафедры", max_length=255)
    short_name = models.CharField("Короткое название", max_length=50, blank=True)

    class Meta:
        verbose_name = "Кафедра"
        verbose_name_plural = "Кафедры"
        ordering = ["name"]
        unique_together = [("faculty", "name")]

    def __str__(self):
        return self.short_name or self.name
