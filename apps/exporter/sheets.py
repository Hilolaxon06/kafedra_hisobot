"""
Конкретные функции заполнения листов. Каждая функция получает лист openpyxl
(уже открытый из шаблона) и ReportingPeriod, и пишет значения в те же ячейки,
которые в оригинальном файле министерства заполнены вручную.

Ряды/колонки ниже — не догадка, а результат разбора реального файла
(kafedra_hisobot_template.xlsx), см. комментарии у каждой функции.

Шаблон — чистый бланк: строки с данными пустые, в заголовке A1 стоит
подстановка {kafedra} (её заменяет engine.export_report). Оригинал с
данными прежней кафедры сохранён рядом как kafedra_hisobot_template.original.xlsx.

Номера строк ниже — как в шаблоне. Если людей/записей больше, чем
строк-заготовок в секции, секция расширяется (layout.SectionRows): строки
вставляются с тем же оформлением, а следующие секции, примечания, подпись
«Rektor» и формулы «Jami» сдвигаются вниз. Ничего не обрезается.
"""

from collections import defaultdict
from decimal import Decimal

from apps.dictionaries.models import EmploymentType
from apps.staff.models import Teacher, TeacherPeriodSnapshot
from apps.reports.models import (
    TeacherHIndex, Publication, Patent, PatentAuthor, Funding,
    PostgradDefense, TeacherMobility,
)
from apps.reports.coauthors import department_year_publications, effective_shares
from .layout import SectionRows


_SECTION_CODES = [
    EmploymentType.ASOSIY, EmploymentType.ICHKI, EmploymentType.TASHQI, EmploymentType.SOATBAY,
]


def _staff(period, code):
    """[(teacher, snapshot | None), ...] по алфавиту для секции штатной
    ведомости. Преподаватели кафедры, которым завкафедрой ещё не завёл
    снимок за этот период (или завёл с нестандартным типом занятости),
    попадают в основной штат («asosiy») — чтобы только что добавленный
    человек сразу появлялся в отчёте, а не терялся молча."""
    snaps = (
        TeacherPeriodSnapshot.objects.filter(reporting_period=period)
        .select_related("teacher", "position", "academic_degree", "academic_title")
    )
    if code == EmploymentType.ASOSIY:
        snaps = snaps.exclude(employment_type__code__in=_SECTION_CODES[1:])
    else:
        snaps = snaps.filter(employment_type__code=code)
    rows = [(snap.teacher, snap) for snap in snaps]
    if code == EmploymentType.ASOSIY:
        with_snapshot = TeacherPeriodSnapshot.objects.filter(
            reporting_period=period).values("teacher_id")
        extra = Teacher.objects.filter(
            department=period.department, is_active=True,
        ).exclude(pk__in=with_snapshot)
        rows += [(teacher, None) for teacher in extra]
    rows.sort(key=lambda row: row[0].full_name)
    return rows


def _clear_rows(ws, rows, last_col):
    for row in rows:
        for col in range(1, last_col + 1):
            ws.cell(row=row, column=col).value = None


# ---------------------------------------------------------------------------
# Лист "5" — штатная ведомость (5-jadval)
# Колонки: A=T/r, B=Ф.И.Ш., C=год рождения, D=должность, E=ставка,
#          F=учёная степень, G=учёное звание
# Секции (по employment_type) и строки-заготовки в шаблоне (расширяются,
# если людей больше):
#   asosiy_shtat      -> строки 7..20  (14 строк)
#   ichki_orindosh    -> строка  22    (1 строка)
#   tashqi_orindosh   -> строки 24..26 (3 строки)
#   soatbay           -> строки 28..30 (3 строки)
# ---------------------------------------------------------------------------
_STAFFING_SECTIONS = [
    ("asosiy", 7, 20),
    ("ichki_orindosh", 22, 22),
    ("tashqi_orindosh", 24, 26),
    ("soatbay", 28, 30),
]


def fill_staffing_sheet(ws, period):
    rows = SectionRows(ws)
    for code, start_row, end_row in _STAFFING_SECTIONS:
        staff = _staff(period, code)
        start_row, end_row = rows.section(start_row, end_row, len(staff))
        _clear_rows(ws, range(start_row, end_row + 1), 7)

        for i, (teacher, snap) in enumerate(staff, start=1):
            row = start_row + i - 1
            ws.cell(row=row, column=1).value = i
            ws.cell(row=row, column=2).value = teacher.full_name
            ws.cell(row=row, column=3).value = teacher.birth_date.year if teacher.birth_date else None
            if snap is None:
                continue
            ws.cell(row=row, column=4).value = snap.position.name if snap.position else None
            ws.cell(row=row, column=5).value = float(snap.stavka)
            ws.cell(row=row, column=6).value = snap.academic_degree.name if snap.academic_degree else None
            ws.cell(row=row, column=7).value = snap.academic_title.name if snap.academic_title else None


# ---------------------------------------------------------------------------
# Лист "1,1" — доля ППС с учёной степенью/званием, полученной за рубежом
# Колонки: A=T/r, B=Ф.И.Ш., C=назв. зарубежного ОТМ,
#          D,E = серия/номер (Академик), F,G = серия/номер (DSc/профессор),
#          H,I = серия/номер (PhD/доцент), J=специальность, K=приказ о приёме
# Секции: строки 4..17 — основной штат (14 строк),
#         строка 18 — маркер "Ichki o'rindosh", строка 19 — 1 строка.
# ---------------------------------------------------------------------------
_DEGREE_COLUMN_BY_CODE = {
    "akademik": (4, 5),
    "dsc": (6, 7),
    "fan_doktori": (6, 7),
    "phd": (8, 9),
    "fan_nomzodi": (8, 9),
}


def _write_degree_share_row(ws, row, teacher, snap):
    ws.cell(row=row, column=2).value = teacher.full_name
    ws.cell(row=row, column=3).value = teacher.foreign_university_name or None

    degree = snap.academic_degree if snap else None
    cols = _DEGREE_COLUMN_BY_CODE.get(degree.code if degree else None)
    if cols and teacher.diploma_series:
        ws.cell(row=row, column=cols[0]).value = teacher.diploma_series
        ws.cell(row=row, column=cols[1]).value = teacher.diploma_number

    ws.cell(row=row, column=10).value = teacher.specialty_name or None
    if teacher.hire_order_number:
        order = teacher.hire_order_number
        if teacher.hire_order_date:
            order = f"{order}, {teacher.hire_order_date:%d.%m.%Y}"
        ws.cell(row=row, column=11).value = order


def fill_academic_degree_share_sheet(ws, period):
    rows = SectionRows(ws)
    for code, start, end in [("asosiy", 4, 17), ("ichki_orindosh", 19, 19)]:
        staff = _staff(period, code)
        start, end = rows.section(start, end, len(staff))
        _clear_rows(ws, range(start, end + 1), 11)
        for i, (teacher, snap) in enumerate(staff, start=1):
            row = start + i - 1
            ws.cell(row=row, column=1).value = i
            _write_degree_share_row(ws, row, teacher, snap)


# ---------------------------------------------------------------------------
# Лист "1,2" — средний возраст ППС с учёной степенью.
# Колонки: A=T/r, B=Ф.И.Ш., C=дата рождения, D=полных лет. Строки 3..11.
# ---------------------------------------------------------------------------
def fill_degree_age_sheet(ws, period):
    staff = _staff(period, "asosiy") + _staff(period, "ichki_orindosh")
    with_degree = sorted(
        (teacher for teacher, snap in staff if snap and snap.academic_degree_id),
        key=lambda teacher: teacher.full_name,
    )
    start, end = SectionRows(ws).section(3, 11, len(with_degree))
    _clear_rows(ws, range(start, end + 1), 4)
    for i, teacher in enumerate(with_degree, start=1):
        row = 2 + i
        ws.cell(row=row, column=1).value = i
        ws.cell(row=row, column=2).value = teacher.full_name
        if teacher.birth_date:
            ws.cell(row=row, column=3).value = teacher.birth_date
            ws.cell(row=row, column=3).number_format = "DD.MM.YYYY"
            ws.cell(row=row, column=4).value = teacher.age


# ---------------------------------------------------------------------------
# Лист "2,3" — суммарный h-индекс ППС.
# Колонки: A=T/r, B=Ф.И.Ш., C=h-индекс. Секции: асосий 3..16, маркер 17, ички 18.
# Значение h-индекса преподаватель вносит сам в /kabinet/hindex/.
# ---------------------------------------------------------------------------
def fill_hindex_sheet(ws, period):
    hindex_by_teacher = {
        rec.teacher_id: rec.h_index
        for rec in TeacherHIndex.objects.filter(reporting_period=period)
    }
    rows = SectionRows(ws)
    for code, start, end in [("asosiy", 3, 16), ("ichki_orindosh", 18, 18)]:
        staff = _staff(period, code)
        start, end = rows.section(start, end, len(staff))
        _clear_rows(ws, range(start, end + 1), 3)
        for i, (teacher, _snap) in enumerate(staff, start=1):
            row = start + i - 1
            ws.cell(row=row, column=1).value = i
            ws.cell(row=row, column=2).value = teacher.full_name
            ws.cell(row=row, column=3).value = hindex_by_teacher.get(teacher.pk)


def _share(pubs_qs, shares):
    """Сумма 1/N-долей публикаций (N — соавторы-сотрудники кафедры; если
    статью внесло больше сотрудников, чем N, — по числу внесших, см.
    apps/reports/coauthors.py). Так в исходной методике получаются дробные
    значения вроде 0.33/0.5/0.66 в своде по квартилям."""
    total = Decimal("0")
    for pub in pubs_qs:
        total += shares[pub.pk]
    if not total:
        return None
    return float(round(total, 2))


def _write_sparse_rows(rows, start_row, end_row, entries, value_columns):
    """Общий помощник для «разреженных» листов (2,4 / 2,6 / 3,4 и т.п.),
    где в шаблоне не 14 строк на весь штат, а несколько строк под тех, у
    кого вообще есть что показать. entries — [(имя, (знач1, знач2, ...)), ...].
    rows — SectionRows листа: если записей больше, чем строк, секция растёт.
    """
    ws = rows.ws
    start_row, end_row = rows.section(start_row, end_row, len(entries))
    row = start_row
    for i, (name, values) in enumerate(entries, start=1):
        ws.cell(row=row, column=1).value = i
        ws.cell(row=row, column=2).value = name
        for col, value in zip(value_columns, values):
            ws.cell(row=row, column=col).value = value
        row += 1
    for empty_row in range(row, end_row + 1):
        for col in [1, 2] + list(value_columns):
            ws.cell(row=empty_row, column=col).value = None


# ---------------------------------------------------------------------------
# Лист "2,1" — свод публикаций по квартилям/топам цитируемости.
# Колонки: A=T/r,B=Ф.И.Ш.,C=Top1%,D=Top10%,E=Q1,F=Q2,G=Q3,H=Q4 (дробные доли).
# Секции: асосий 3..16 (14), маркер "Ichki oʻrindoshlar" в строке 17 (не
# трогаем), ички 18 (1). Итоговая строка 19 — формула Excel (=SUM(...)) —
# её не трогаем, пересчитается сама при открытии файла.
# ---------------------------------------------------------------------------
def fill_publications_quartile_sheet(ws, period):
    shares = effective_shares(department_year_publications(period.department_id, period.period_date.year))
    rows = SectionRows(ws)
    for code, start, end in [("asosiy", 3, 16), ("ichki_orindosh", 18, 18)]:
        entries = []
        for teacher, _snap in _staff(period, code):
            pubs = Publication.objects.filter(teacher=teacher, reporting_period=period,
                                              indexing=Publication.Indexing.SCOPUS)
            entries.append((teacher.full_name, (
                _share(pubs.filter(citation_tier="top1"), shares),
                _share(pubs.filter(citation_tier="top10"), shares),
                _share(pubs.filter(quartile="Q1"), shares),
                _share(pubs.filter(quartile="Q2"), shares),
                _share(pubs.filter(quartile="Q3"), shares),
                _share(pubs.filter(quartile="Q4"), shares),
            )))
        _write_sparse_rows(rows, start, end, entries, value_columns=[3, 4, 5, 6, 7, 8])


# ---------------------------------------------------------------------------
# Лист "2,2" — публикации и их цитирования.
# Колонки: A=T/r, B=Ф.И.Ш., C=журнал, D=год.месяц, E=название, F=язык,
#          G=ссылка Scopus, H=число цитирований. Одна строка на преподавателя,
#          несколько статей — через перенос строки внутри ячейки.
# Секции: асосий 3..16, маркер 17, ички 18.
# ---------------------------------------------------------------------------
def fill_publications_list_sheet(ws, period):
    pubs_by_teacher = defaultdict(list)
    for pub in Publication.objects.filter(reporting_period=period, indexing=Publication.Indexing.SCOPUS).order_by("publish_year", "publish_month", "id"):
        pubs_by_teacher[pub.teacher_id].append(pub)

    def joined(pubs, func):
        return "\n".join(func(p) for p in pubs) or None

    rows = SectionRows(ws)
    for code, start, end in [("asosiy", 3, 16), ("ichki_orindosh", 18, 18)]:
        staff = _staff(period, code)
        start, end = rows.section(start, end, len(staff))
        _clear_rows(ws, range(start, end + 1), 8)
        for i, (teacher, _snap) in enumerate(staff, start=1):
            row = start + i - 1
            ws.cell(row=row, column=1).value = i
            ws.cell(row=row, column=2).value = teacher.full_name
            pubs = pubs_by_teacher.get(teacher.pk)
            if not pubs:
                continue
            ws.cell(row=row, column=3).value = joined(pubs, lambda p: p.journal_name)
            ws.cell(row=row, column=4).value = joined(pubs, lambda p: ".".join(
                str(v) for v in (p.publish_year, p.publish_month) if v))
            ws.cell(row=row, column=5).value = joined(pubs, lambda p: p.article_title)
            ws.cell(row=row, column=6).value = joined(pubs, lambda p: p.language)
            ws.cell(row=row, column=7).value = joined(pubs, lambda p: p.scopus_url)
            ws.cell(row=row, column=8).value = sum(p.citations_count for p in pubs)


# ---------------------------------------------------------------------------
# Лист "2,4" — патенты/объекты интеллектуальной собственности.
# Колонки: A=T/r, B=Ф.И.Ш.,
#   C = патенты на изобретение, полезную модель, промышленный образец,
#       селекционное достижение (Patent.CLASSIC_TYPES); свидетельства на
#       программы для ЭВМ / базы данных сюда НЕ входят;
#   D = объекты интеллектуальной собственности с лицензионным договором —
#       любого типа, в т.ч. свидетельства. Свидетельство без договора не
#       учитывается нигде (так по тексту формы; уточнить у отдела рейтинга).
# Разреженный список (не весь штат) — только те, у кого есть что показать.
# Строки 3..5.
# ---------------------------------------------------------------------------
def fill_patents_share_sheet(ws, period):
    stats = defaultdict(lambda: [0, 0])
    for pa in PatentAuthor.objects.filter(patent__reporting_period=period).select_related("patent", "teacher"):
        if pa.patent.patent_type in Patent.CLASSIC_TYPES:
            stats[pa.teacher][0] += 1
        if pa.patent.has_license_agreement:
            stats[pa.teacher][1] += 1
    entries = sorted(
        ((t.full_name, tuple(v)) for t, v in stats.items() if any(v)),
        key=lambda x: x[0],
    )
    _write_sparse_rows(SectionRows(ws), 3, 5, entries, value_columns=[3, 4])


# ---------------------------------------------------------------------------
# Лист "2,6" — привлечённые средства.
# Колонки: A=T/r,B=Ф.И.Ш.,C=зарубежные/международные,D=госпрограммы,E=хоздоговоры.
# Разреженный список. Строки 3..6.
# ---------------------------------------------------------------------------
def fill_funding_sheet(ws, period):
    stats = defaultdict(lambda: [Decimal("0"), Decimal("0"), Decimal("0")])
    idx = {"foreign_international": 0, "state_program": 1, "business_contract": 2}
    for f in Funding.objects.filter(reporting_period=period).select_related("teacher"):
        stats[f.teacher][idx[f.source_type]] += f.amount
    entries = sorted(
        ((t.full_name, tuple(float(v) if v else None for v in vals)) for t, vals in stats.items()),
        key=lambda x: x[0],
    )
    _write_sparse_rows(SectionRows(ws), 3, 6, entries, value_columns=[3, 4, 5])


# ---------------------------------------------------------------------------
# Лист "2,7" — эффективность подготовки кадров высшей квалификации.
# Колонки: A=T/r,B=Ф.И.Ш.,C=число защит под руководством,D=флаг "нет степени".
# Строка попадает в отчёт, если хотя бы одно из двух условий верно.
# Секции: асосий 3..7 (5), маркер строка 8 (не трогаем), ички 9 (1).
# ---------------------------------------------------------------------------
def fill_postgrad_efficiency_sheet(ws, period):
    defense_counts = defaultdict(int)
    for d in PostgradDefense.objects.filter(reporting_period=period):
        defense_counts[d.advisor_teacher_id] += 1

    rows = SectionRows(ws)
    for code, start, end in [("asosiy", 3, 7), ("ichki_orindosh", 9, 9)]:
        entries = []
        for teacher, snap in _staff(period, code):
            defenses = defense_counts.get(teacher.pk, 0)
            no_degree = snap is None or snap.academic_degree_id is None
            if defenses or no_degree:
                entries.append((teacher.full_name, (
                    defenses or None,
                    1 if no_degree else None,
                )))
        _write_sparse_rows(rows, start, end, entries, value_columns=[3, 4])


# ---------------------------------------------------------------------------
# Лист "3,4" — международная мобильность ППС.
# Колонки: A=T/r,B=Ф.И.Ш.,C=outbound,D=inbound. Разреженный список. Строки 3..5.
# ---------------------------------------------------------------------------
def fill_teacher_mobility_sheet(ws, period):
    stats = defaultdict(lambda: [0, 0])
    for m in TeacherMobility.objects.filter(reporting_period=period).select_related("teacher"):
        stats[m.teacher][0 if m.direction == "outbound" else 1] += 1
    entries = sorted(
        ((t.full_name, tuple(v or None for v in vals)) for t, vals in stats.items()),
        key=lambda x: x[0],
    )
    _write_sparse_rows(SectionRows(ws), 3, 5, entries, value_columns=[3, 4])


SHEET_FILLERS = {
    "5": fill_staffing_sheet,
    "1,1": fill_academic_degree_share_sheet,
    "1,2": fill_degree_age_sheet,
    "2,1": fill_publications_quartile_sheet,
    "2,2": fill_publications_list_sheet,
    "2,3": fill_hindex_sheet,
    "2,4": fill_patents_share_sheet,
    "2,6": fill_funding_sheet,
    "2,7": fill_postgrad_efficiency_sheet,
    "3,4": fill_teacher_mobility_sheet,
}
