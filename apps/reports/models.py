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

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.staff.models import Teacher
from apps.students.models import Student, Graduate
from apps.workflow.models import ReportingPeriod


class TeacherPeriodFactMixin:
    """Запись преподавателя должна относиться к отчётному периоду его же
    кафедры — иначе показатель уходит в статистику и отчёт чужой кафедры.
    Проверяется при создании записи и при смене преподавателя/периода (старые
    записи после перевода преподавателя на другую кафедру не блокируются)."""

    teacher_field = "teacher"

    def clean(self):
        super().clean()
        teacher_id = getattr(self, f"{self.teacher_field}_id")
        if not teacher_id or not self.reporting_period_id:
            return
        if not self._state.adding:
            old = type(self).objects.filter(pk=self.pk).values(f"{self.teacher_field}_id", "reporting_period_id").first()
            if old == {f"{self.teacher_field}_id": teacher_id, "reporting_period_id": self.reporting_period_id}:
                return
        teacher = getattr(self, self.teacher_field)
        if self.reporting_period.department_id != teacher.department_id:
            raise ValidationError({"reporting_period": _(
                "Этот отчётный период относится к другой кафедре — выберите период кафедры преподавателя.")})


class Publication(TeacherPeriodFactMixin, models.Model):
    class Indexing(models.TextChoices):
        SCOPUS = "scopus", "Scopus"
        WOS = "wos", "Web of Science"
        OAK = "oak", _("Журнал из перечня ОАК (OAK ro'yxati)")
        FOREIGN = "foreign", _("Другой зарубежный журнал")
        LOCAL = "local", _("Республиканский журнал")
        CONFERENCE = "conference", _("Сборник конференции (тезисы)")
        OTHER = "other", _("Другое (монография, учебник, статья)")

    # квартиль и топ по цитируемости имеют смысл только для этих баз
    RANKED_INDEXINGS = (Indexing.SCOPUS, Indexing.WOS)

    class Quartile(models.TextChoices):
        Q1 = "Q1", "Q1"
        Q2 = "Q2", "Q2"
        Q3 = "Q3", "Q3"
        Q4 = "Q4", "Q4"

    class CitationTier(models.TextChoices):
        TOP1 = "top1", _("Top 1% most cited")
        TOP10 = "top10", _("Top 10% most cited")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="publications", verbose_name=_("Автор"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="publications", verbose_name=_("Отчётный период"))
    indexing = models.CharField(
        _("Где опубликовано (база / тип издания)"), max_length=20,
        choices=Indexing.choices, default=Indexing.SCOPUS,
        help_text=_("В свод по квартилям (листы 2,1 и 2,2) попадают только статьи Scopus; "
                    "остальные статьи хранятся в кабинете и попадают в ZIP-архив кафедры."),
    )
    journal_name = models.CharField(_("Название журнала / сборника"), max_length=255, blank=True)
    publish_year = models.PositiveSmallIntegerField(_("Год публикации"), null=True, blank=True)
    publish_month = models.PositiveSmallIntegerField(_("Месяц публикации"), null=True, blank=True)
    article_title = models.CharField(_("Название статьи"), max_length=500, blank=True)
    language = models.CharField(_("Язык публикации"), max_length=30, blank=True)
    scopus_url = models.URLField(
        _("Ссылка на статью"), max_length=500, blank=True,
        help_text=_("Scopus, DOI или страница статьи на сайте журнала."),
    )
    quartile = models.CharField(
        _("Квартиль"), max_length=2, choices=Quartile.choices, null=True, blank=True,
        help_text=_("Только для Scopus / Web of Science."),
    )
    citation_tier = models.CharField(
        _("Топ по цитируемости"), max_length=10, choices=CitationTier.choices, null=True, blank=True,
        help_text=_("Только для Scopus / Web of Science."),
    )
    citations_count = models.PositiveIntegerField(_("Число цитирований"), default=0)
    article_file = models.FileField(_("Электронный PDF статьи"), upload_to="publications/", null=True, blank=True)
    department_co_authors_count = models.PositiveSmallIntegerField(
        _("Число соавторов-сотрудников этой кафедры"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text=_("Сколько сотрудников этой кафедры (включая вас) — авторы статьи. В рейтинге "
                    "и своде по квартилям (лист 2,1) каждому засчитывается доля 1/N "
                    "(0.5, 0.33 и т.п.). Завкафедрой проверяет это число и при ошибке исправляет."),
    )
    co_authors_checked = models.BooleanField(
        _("Число соавторов проверено завкафедрой"), default=False,
        help_text=_("Снимается автоматически, если преподаватель меняет число соавторов."),
    )

    class Meta:
        verbose_name = _("Публикация")
        verbose_name_plural = _("Публикации (Scopus и другие)")
        ordering = ["-publish_year", "-publish_month"]

    def __str__(self):
        return f"{self.teacher} — {self.article_title[:40]}"

    @property
    def share(self):
        """Доля автора в статье: 1/N, N — соавторы-сотрудники кафедры."""
        return Decimal(1) / Decimal(self.department_co_authors_count or 1)
    share.fget.short_description = _("Доля (1/N)")

    def save(self, *args, **kwargs):
        # у не-Scopus/WoS статей квартиля нет — не даём ему попасть в свод 2,1
        if self.indexing not in self.RANKED_INDEXINGS:
            self.quartile = None
            self.citation_tier = None
        super().save(*args, **kwargs)


class TeacherHIndex(TeacherPeriodFactMixin, models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="hindex_records", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="hindex_records", verbose_name=_("Отчётный период"))
    h_index = models.PositiveIntegerField(_("Индекс Хирша (Scopus)"))

    class Meta:
        verbose_name = _("H-индекс")
        verbose_name_plural = _("H-индексы")
        unique_together = [("teacher", "reporting_period")]

    def __str__(self):
        return f"{self.teacher}: h={self.h_index}"


class Patent(models.Model):
    class PatentType(models.TextChoices):
        INVENTION = "invention", _("Изобретение")
        UTILITY_MODEL = "utility_model", _("Полезная модель")
        INDUSTRIAL_DESIGN = "industrial_design", _("Промышленный образец")
        SELECTION = "selection_achievement", _("Селекционное достижение")
        SOFTWARE_CERTIFICATE = "software_certificate", _("Свидетельство на программу для ЭВМ")
        DATABASE_CERTIFICATE = "database_certificate", _("Свидетельство на базу данных")

    # в колонку C листа 2,4 попадают только патенты; свидетельства на
    # программы/базы данных учитываются лишь с лицензионным договором (колонка D)
    CLASSIC_TYPES = (
        PatentType.INVENTION, PatentType.UTILITY_MODEL,
        PatentType.INDUSTRIAL_DESIGN, PatentType.SELECTION,
    )

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="patents", verbose_name=_("Отчётный период"))
    title = models.CharField(_("Название"), max_length=500, blank=True)
    patent_type = models.CharField(_("Тип"), max_length=30, choices=PatentType.choices)
    registered_in_scopus = models.BooleanField(_("Учтён в Scopus"), default=False)
    has_license_agreement = models.BooleanField(_("Есть лицензионный договор"), default=False)
    document_file = models.FileField(
        _("Документ, подтверждающий патент (PDF)"), upload_to="patents/", null=True, blank=True,
    )
    authors = models.ManyToManyField(Teacher, through="PatentAuthor", related_name="patents", verbose_name=_("Авторы"))

    class Meta:
        verbose_name = _("Патент / объект интеллектуальной собственности")
        verbose_name_plural = _("Патенты / объекты интеллектуальной собственности")

    def __str__(self):
        return self.title or f"Патент #{self.pk}"


class PatentAuthor(models.Model):
    patent = models.ForeignKey(Patent, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Автор патента")
        verbose_name_plural = _("Авторы патентов")
        unique_together = [("patent", "teacher")]


class Funding(TeacherPeriodFactMixin, models.Model):
    class SourceType(models.TextChoices):
        FOREIGN = "foreign_international", _("Зарубежные / международные организации")
        STATE_PROGRAM = "state_program", _("Государственные научные программы")
        BUSINESS_CONTRACT = "business_contract", _("Хоздоговорные заказы")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="fundings", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="fundings", verbose_name=_("Отчётный период"))
    source_type = models.CharField(_("Источник средств"), max_length=30, choices=SourceType.choices)
    amount = models.DecimalField(_("Сумма"), max_digits=15, decimal_places=2)
    document_file = models.FileField(
        _("Договор / квитанция (PDF)"), upload_to="fundings/", null=True, blank=True,
    )

    class Meta:
        verbose_name = _("Привлечённые средства")
        verbose_name_plural = _("Привлечённые средства")

    def __str__(self):
        return f"{self.teacher} — {self.amount}"


class PostgradDefense(TeacherPeriodFactMixin, models.Model):
    teacher_field = "advisor_teacher"

    class DegreeType(models.TextChoices):
        PHD = "PhD", _("PhD (фалсафа доктори)")
        DSC = "DSc", _("DSc (фан доктори)")

    advisor_teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name=_("Научный руководитель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="postgrad_defenses", verbose_name=_("Отчётный период"))
    degree_type = models.CharField(_("Степень"), max_length=5, choices=DegreeType.choices)
    defended_full_name = models.CharField(_("Ф.И.Ш. соискателя"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Защита диссертации (под руководством)")
        verbose_name_plural = _("Защиты диссертаций (под руководством)")

    def __str__(self):
        return f"{self.advisor_teacher} — {self.degree_type}"


class ReputationVote(models.Model):
    class Source(models.TextChoices):
        RATING_ORG = "rating_org_expert", _("Эксперт THE / QS / ARWU")
        NATIONAL_QA = "national_qa_agency_expert", _("Эксперт нац. агентства по качеству образования")
        FOREIGN_PARTNER = "foreign_partner_staff", _("Сотрудник зарубежного вуза-партнёра")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="reputation_votes", verbose_name=_("Отчётный период"))
    source = models.CharField(_("Источник голосов"), max_length=30, choices=Source.choices)
    votes_count = models.PositiveIntegerField(_("Число голосов"))

    class Meta:
        verbose_name = _("Голос за международную репутацию")
        verbose_name_plural = _("Голоса за международную репутацию")

    def __str__(self):
        return f"{self.teacher} — {self.source}: {self.votes_count}"


class TeacherMobility(TeacherPeriodFactMixin, models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", _("Outbound")
        INBOUND = "inbound", _("Inbound")

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="mobility_records", verbose_name=_("Преподаватель"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="teacher_mobility", verbose_name=_("Отчётный период"))
    direction = models.CharField(_("Направление"), max_length=10, choices=Direction.choices)
    partner_institution_name = models.CharField(_("Партнёрский вуз"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Международная мобильность ППС")
        verbose_name_plural = _("Международная мобильность ППС")

    def __str__(self):
        return f"{self.teacher} — {self.direction}"


class StudentMobility(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "outbound", _("Outbound")
        INBOUND = "inbound", _("Inbound")

    class ProgramType(models.TextChoices):
        EXCHANGE = "exchange", _("Программа обмена")
        JOINT_PROGRAM = "joint_program", _("Совместная образовательная программа")

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="mobility_records", verbose_name=_("Студент"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="student_mobility", verbose_name=_("Отчётный период"))
    direction = models.CharField(_("Направление"), max_length=10, choices=Direction.choices, blank=True)
    program_type = models.CharField(_("Тип программы"), max_length=20, choices=ProgramType.choices)
    partner_rank = models.CharField(
        _("Рейтинг партнёрского вуза"), max_length=10,
        choices=[("TOP100", "TOP-100"), ("TOP300", "TOP-300"), ("TOP500", "TOP-500"),
                 ("TOP1000", "TOP-1000"), ("other", _("Вне рейтинга"))],
    )

    class Meta:
        verbose_name = _("Академическая мобильность студента")
        verbose_name_plural = _("Академическая мобильность студентов")

    def __str__(self):
        return f"{self.student} — {self.partner_rank}"


class GraduateEmployment(models.Model):
    class Status(models.TextChoices):
        ENTREPRENEUR = "entrepreneur_or_founder", _("ИП / учредитель")
        EMPLOYED = "employed_state_or_business", _("Трудоустроен (гос. орган / хоз. субъект)")
        EXEMPT = "further_education_or_exempt", _("Продолжает учёбу / декрет / инвалидность / самозанят")

    graduate = models.OneToOneField(Graduate, on_delete=models.CASCADE, related_name="employment", verbose_name=_("Выпускник"))
    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="graduate_employment", verbose_name=_("Отчётный период"))
    status = models.CharField(_("Статус занятости"), max_length=30, choices=Status.choices)
    months_to_employment = models.PositiveSmallIntegerField(
        _("Через сколько месяцев трудоустроен"), null=True, blank=True,
        choices=[(3, "3"), (6, "6"), (12, "12")],
    )
    monthly_income = models.DecimalField(_("Средний месячный доход"), max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = _("Трудоустройство выпускника")
        verbose_name_plural = _("Трудоустройство выпускников")

    def __str__(self):
        return f"{self.graduate} — {self.status}"


class NationalAvgSalary(models.Model):
    """Справочная величина Госкомстата — не факт о выпускнике, а точка
    сравнения для листа «Bitiruvchilarning o'rtacha daromadi»."""

    year = models.PositiveSmallIntegerField(_("Год"))
    month = models.PositiveSmallIntegerField(_("Месяц"))
    amount = models.DecimalField(_("Средняя номинальная зарплата по РУз"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = _("Средняя зарплата по стране (Госкомстат)")
        verbose_name_plural = _("Средняя зарплата по стране (Госкомстат)")
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
        TEACHER = "teacher", _("Преподаватель")
        STUDENT = "student", _("Студент")
        GRADUATE = "graduate", _("Выпускник")
        DEPARTMENT = "department", _("Кафедра")

    reporting_period = models.ForeignKey(ReportingPeriod, on_delete=models.CASCADE, related_name="indicator_values", verbose_name=_("Отчётный период"))
    subject_type = models.CharField(_("Тип субъекта"), max_length=20, choices=SubjectType.choices)
    subject_id = models.PositiveIntegerField(_("ID субъекта"))
    indicator_code = models.CharField(_("Код показателя"), max_length=100, help_text=_("Например: sheet_1_3_top100_degree_count"))
    value_numeric = models.DecimalField(_("Числовое значение"), max_digits=15, decimal_places=2, null=True, blank=True)
    value_text = models.CharField(_("Текстовое значение"), max_length=500, blank=True)
    document_path = models.CharField(_("Путь к подтверждающему документу"), max_length=500, blank=True)

    class Meta:
        verbose_name = _("Показатель (гибкий, вне основной схемы)")
        verbose_name_plural = _("Показатели (гибкие, вне основной схемы)")
        unique_together = [("reporting_period", "subject_type", "subject_id", "indicator_code")]

    def __str__(self):
        return f"{self.indicator_code} [{self.subject_type}#{self.subject_id}]"
