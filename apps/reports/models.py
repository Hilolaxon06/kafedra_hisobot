"""
Факт-таблицы показателей кафедры. Общий принцип для всех таблиц этого файла:

- они хранят АТОМАРНЫЕ факты (одна публикация, один патент, один голос
  эксперта), а не готовые суммы — итоговые "Jami" в отчёте считаются
  агрегирующим запросом (SUM/COUNT) в apps/exporter, а не хранятся полем;
- почти каждая факт-таблица ссылается на ReportingPeriod — это и есть та
  «шина», вокруг которой построена вся схема (см. ERD-диаграмму): один и
  тот же список показателей можно вести из периода в период, не переписывая
  историю;
- IndicatorValue — универсальный запасной вариант на случай, если
  министерство добавит новый показатель, под который ещё не заведена
  отдельная таблица: не требует миграции схемы.
"""

from django.db import models

from apps.staff.models import Teacher
from apps.students.models import Student, Graduate
from apps.workflow.models import ReportingPeriod


class Publication(models.Model):
    class Indexing(models.TextChoices):
        SCOPUS = "scopus", "Scopus"
        WOS = "wos", "Web of Science"
        OAK = "oak", "Журнал из перечня ОАК (OAK ro'yxati)"
        FOREIGN = "foreign", "Другой зарубежный журнал"
        LOCAL = "local", "Республиканский журнал"
        CONFERENCE = "conference", "Сборник конференции (тезисы)"
        OTHER = "other", "Другое (монография, учебник, статья)"

    # квартиль и топ по цитируемости имеют смысл только для этих баз
    RANKED_INDEXINGS = (Indexing.SCOPUS, Indexing.WOS)

    class Quartile(models.TextChoices):
        Q1 = "Q1", "Q1"
        Q2 = "Q2", "Q2"
        Q3 = "Q3", "Q3"
        Q4 = "Q4", "Q4"

    class CitationTier(models.TextChoices):
        TOP1 = "top1", "Top 1% most cited"
        TOP10 = "top10", "Top 10% most cited"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="publications", verbose_name="Автор")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="publications", verbose_name="Отчётный период")
    indexing = models.CharField(
        "Где опубликовано (база / тип издания)", max_length=20,
        choices=Indexing.choices, default=Indexing.SCOPUS,
        help_text="В свод по квартилям (листы 2,1 и 2,2) попадают только статьи Scopus; "
                  "остальные статьи хранятся в кабинете и попадают в ZIP-архив кафедры.",
    )
    journal_name = models.CharField("Название журнала / сборника", max_length=255, blank=True)
    publish_year = models.PositiveSmallIntegerField("Год публикации", null=True, blank=True)
    publish_month = models.PositiveSmallIntegerField("Месяц публикации", null=True, blank=True)
    article_title = models.CharField("Название статьи", max_length=500, blank=True)
    language = models.CharField("Язык публикации", max_length=30, blank=True)
    scopus_url = models.URLField(
        "Ссылка на статью", max_length=500, blank=True,
        help_text="Scopus, DOI или страница статьи на сайте журнала.",
    )
    quartile = models.CharField(
        "Квартиль", max_length=2, choices=Quartile.choices, null=True, blank=True,
        help_text="Только для Scopus / Web of Science.",
    )
    citation_tier = models.CharField(
        "Топ по цитируемости", max_length=10, choices=CitationTier.choices, null=True, blank=True,
        help_text="Только для Scopus / Web of Science.",
    )
    citations_count = models.PositiveIntegerField("Число цитирований", default=0)
    article_file = models.FileField("Электронный PDF статьи", upload_to="publications/", null=True, blank=True)
    department_co_authors_count = models.PositiveSmallIntegerField(
        "Число соавторов-сотрудников этой кафедры",
        default=1,
        help_text="Если статью написали несколько сотрудников кафедры вместе, в своде по "
                   "квартилям (лист 2,1) каждому засчитывается доля 1/N — как в исходной "
                   "методике министерства (там встречаются значения вида 0.33, 0.5, 0.66).",
    )

    class Meta:
        verbose_name = "Публикация"
        verbose_name_plural = "Публикации (Scopus и другие)"
        ordering = ["-publish_year", "-publish_month"]

    def __str__(self):
        return f"{self.teacher} — {self.article_title[:40]}"

    def save(self, *args, **kwargs):
        # у не-Scopus/WoS статей квартиля нет — не даём ему попасть в свод 2,1
        if self.indexing not in self.RANKED_INDEXINGS:
            self.quartile = None
            self.citation_tier = None
        super().save(*args, **kwargs)


class TeacherHIndex(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="hindex_records", verbose_name="Преподаватель")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="hindex_records", verbose_name="Отчётный период")
    h_index = models.PositiveIntegerField("Индекс Хирша (Scopus)")

    class Meta:
        verbose_name = "H-индекс"
        verbose_name_plural = "H-индексы"
        unique_together = [("teacher", "reporting_period")]

    def __str__(self):
        return f"{self.teacher}: h={self.h_index}"


class Patent(models.Model):
    class PatentType(models.TextChoices):
        INVENTION = "invention", "Изобретение"
        UTILITY_MODEL = "utility_model", "Полезная модель"
        INDUSTRIAL_DESIGN = "industrial_design", "Промышленный образец"
        SELECTION = "selection_achievement", "Селекционное достижение"

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="patents", verbose_name="Отчётный период")
    title = models.CharField("Название", max_length=500, blank=True)
    patent_type = models.CharField("Тип", max_length=30, choices=PatentType.choices)
    registered_in_scopus = models.BooleanField("Учтён в Scopus", default=False)
    has_license_agreement = models.BooleanField("Есть лицензионный договор", default=False)
    document_file = models.FileField(
        "Документ, подтверждающий патент (PDF)", upload_to="patents/", null=True, blank=True,
    )
    authors = models.ManyToManyField(Teacher, through="PatentAuthor", related_name="patents", verbose_name="Авторы")

    class Meta:
        verbose_name = "Патент / объект интеллектуальной собственности"
        verbose_name_plural = "Патенты / объекты интеллектуальной собственности"

    def __str__(self):
        return self.title or f"Патент #{self.pk}"


class PatentAuthor(models.Model):
    patent = models.ForeignKey(Patent, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Автор патента"
        verbose_name_plural = "Авторы патентов"
        unique_together = [("patent", "teacher")]


class Funding(models.Model):
    class SourceType(models.TextChoices):
        FOREIGN = "foreign_international", "Зарубежные / международные организации"
        STATE_PROGRAM = "state_program", "Государственные научные программы"
        BUSINESS_CONTRACT = "business_contract", "Хоздоговорные заказы"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="fundings", verbose_name="Преподаватель")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="fundings", verbose_name="Отчётный период")
    source_type = models.CharField("Источник средств", max_length=30, choices=SourceType.choices)
    amount = models.DecimalField("Сумма", max_digits=15, decimal_places=2)
    document_file = models.FileField(
        "Договор / квитанция (PDF)", upload_to="fundings/", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Привлечённые средства"
        verbose_name_plural = "Привлечённые средства"

    def __str__(self):
        return f"{self.teacher} — {self.amount}"


class PostgradDefense(models.Model):
    class DegreeType(models.TextChoices):
        PHD = "PhD", "PhD (фалсафа доктори)"
        DSC = "DSc", "DSc (фан доктори)"

    advisor_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name="Научный руководитель")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name="Отчётный период")
    degree_type = models.CharField("Степень", max_length=5, choices=DegreeType.choices)
    defended_full_name = models.CharField("Ф.И.Ш. соискателя", max_length=255, blank=True)

    class Meta:
        verbose_name = "Защита диссертации (под руководством)"
        verbose_name_plural = "Защиты диссертаций (под руководством)"

    def __str__(self):
        return f"{self.advisor_teacher} — {self.degree_type}"


class ReputationVote(models.Model):
    class Source(models.TextChoices):
        RATING_ORG = "rating_org_expert", "Эксперт THE / QS / ARWU"
        NATIONAL_QA = "national_qa_agency_expert", "Эксперт нац. агентства по качеству образования"
        FOREIGN_PARTNER = "foreign_partner_staff", "Сотрудник зарубежного вуза-партнёра"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name="Преподаватель")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name="Отчётный период")
    source = models.CharField("Источник голосов", max_length=30, choices=Source.choices)
    votes_count = models.PositiveIntegerField("Число голосов")

    class Meta:
        verbose_name = "Голос за международную репутацию"
        verbose_name_plural = "Голоса за международную репутацию"

    def __str__(self):
        return f"{self.teacher} — {self.source}: {self.votes_count}"


class TeacherMobility(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", "Outbound"
        INBOUND = "inbound", "Inbound"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="mobility_records", verbose_name="Преподаватель")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_mobility", verbose_name="Отчётный период")
    direction = models.CharField("Направление", max_length=10, choices=Direction.choices)
    partner_institution_name = models.CharField("Партнёрский вуз", max_length=255, blank=True)

    class Meta:
        verbose_name = "Международная мобильность ППС"
        verbose_name_plural = "Международная мобильность ППС"

    def __str__(self):
        return f"{self.teacher} — {self.direction}"


class StudentMobility(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", "Outbound"
        INBOUND = "inbound", "Inbound"

    class ProgramType(models.TextChoices):
        EXCHANGE = "exchange", "Программа обмена"
        JOINT_PROGRAM = "joint_program", "Совместная образовательная программа"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="mobility_records", verbose_name="Студент")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="student_mobility", verbose_name="Отчётный период")
    direction = models.CharField("Направление", max_length=10, choices=Direction.choices, blank=True)
    program_type = models.CharField("Тип программы", max_length=20, choices=ProgramType.choices)
    partner_rank = models.CharField(
        "Рейтинг партнёрского вуза", max_length=10,
        choices=[("TOP100", "TOP-100"), ("TOP300", "TOP-300"), ("TOP500", "TOP-500"),
                 ("TOP1000", "TOP-1000"), ("other", "Вне рейтинга")],
    )

    class Meta:
        verbose_name = "Академическая мобильность студента"
        verbose_name_plural = "Академическая мобильность студентов"

    def __str__(self):
        return f"{self.student} — {self.partner_rank}"


class GraduateEmployment(models.Model):
    class Status(models.TextChoices):
        ENTREPRENEUR = "entrepreneur_or_founder", "ИП / учредитель"
        EMPLOYED = "employed_state_or_business", "Трудоустроен (гос. орган / хоз. субъект)"
        EXEMPT = "further_education_or_exempt", "Продолжает учёбу / декрет / инвалидность / самозанят"

    graduate = models.OneToOneField(Graduate, on_delete=models.CASCADE, related_name="employment", verbose_name="Выпускник")
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="graduate_employment", verbose_name="Отчётный период")
    status = models.CharField("Статус занятости", max_length=30, choices=Status.choices)
    months_to_employment = models.PositiveSmallIntegerField(
        "Через сколько месяцев трудоустроен", null=True, blank=True,
        choices=[(3, "3"), (6, "6"), (12, "12")],
    )
    monthly_income = models.DecimalField("Средний месячный доход", max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Трудоустройство выпускника"
        verbose_name_plural = "Трудоустройство выпускников"

    def __str__(self):
        return f"{self.graduate} — {self.status}"


class NationalAvgSalary(models.Model):
    """Справочная величина Госкомстата — не факт о выпускнике, а точка
    сравнения для листа «Bitiruvchilarning o'rtacha daromadi»."""

    year = models.PositiveSmallIntegerField("Год")
    month = models.PositiveSmallIntegerField("Месяц")
    amount = models.DecimalField("Средняя номинальная зарплата по РУз", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Средняя зарплата по стране (Госкомстат)"
        verbose_name_plural = "Средняя зарплата по стране (Госкомстат)"
        unique_together = [("year", "month")]
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.year}-{self.month:02d}: {self.amount}"


class IndicatorValue(models.Model):
    """
    Универсальный запасной вариант для показателей, под которые ещё нет
    отдельной таблицы (методика рейтинга вузов Узбекистана пересматривается
    почти ежегодно). Не заменяет таблицы выше — используется только для
    новых/редких пунктов, чтобы не делать миграцию схемы под каждое
    изменение методики.
    """

    class SubjectType(models.TextChoices):
        TEACHER = "teacher", "Преподаватель"
        STUDENT = "student", "Студент"
        GRADUATE = "graduate", "Выпускник"
        DEPARTMENT = "department", "Кафедра"

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="indicator_values", verbose_name="Отчётный период")
    subject_type = models.CharField("Тип субъекта", max_length=20, choices=SubjectType.choices)
    subject_id = models.PositiveIntegerField("ID субъекта")
    indicator_code = models.CharField("Код показателя", max_length=100, help_text="Например: sheet_1_3_top100_degree_count")
    value_numeric = models.DecimalField("Числовое значение", max_digits=15, decimal_places=2, null=True, blank=True)
    value_text = models.CharField("Текстовое значение", max_length=500, blank=True)
    document_path = models.CharField("Путь к подтверждающему документу", max_length=500, blank=True)

    class Meta:
        verbose_name = "Показатель (гибкий, вне основной схемы)"
        verbose_name_plural = "Показатели (гибкие, вне основной схемы)"
        unique_together = [("reporting_period", "subject_type", "subject_id", "indicator_code")]

    def __str__(self):
        return f"{self.indicator_code} [{self.subject_type}#{self.subject_id}]"
