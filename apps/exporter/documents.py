"""
Реестр подтверждающих документов: какой лист формы → какая модель → какое
файловое поле → в какую папку архива.

По этому одному списку собираются и папки в ZIP-архиве кафедры
(archive.build_package), и Hujjatlar_royxati.xlsx — что приложено, а чего
не хватает. Новый вид документа = одна запись в DOCUMENTS.
"""

from dataclasses import dataclass
from typing import Any, Callable

from apps.reports.models import Funding, PatentAuthor, Publication
from apps.staff.models import TeacherPeriodSnapshot


@dataclass(frozen=True)
class DocumentRow:
    teacher_id: int
    file: Any            # FieldFile (может быть пустым — тогда «fayl yuklanmagan»)
    description: str
    obj: Any             # исходная запись (публикация, патент, договор, преподаватель)


@dataclass(frozen=True)
class DocumentKind:
    sheet: str           # лист формы, для которого нужен документ
    folder: str          # папка внутри папки преподавателя
    title: str           # вид документа в реестре
    rows: Callable       # rows(period, department_teachers) -> [DocumentRow, ...]


def _diplomas(period, department_teachers):
    # диплом нужен тем, у кого в штатной ведомости периода есть степень,
    # плюс всем, кто его уже загрузил
    with_degree = set(
        TeacherPeriodSnapshot.objects.filter(reporting_period=period, academic_degree__isnull=False)
        .values_list("teacher_id", flat=True)
    )
    return [
        DocumentRow(t.pk, t.diploma_file,
                    " ".join(v for v in (t.diploma_series, t.diploma_number) if v) or "Diplom", t)
        for t in department_teachers
        if t.pk in with_degree or t.diploma_file
    ]


def _publications(period, _teachers):
    return [
        DocumentRow(p.teacher_id, p.article_file, p.article_title or p.journal_name or f"#{p.pk}", p)
        for p in Publication.objects.filter(reporting_period=period).order_by("id")
    ]


def _patents(period, _teachers):
    # один документ патента — в папку каждого соавтора с кафедры
    return [
        DocumentRow(pa.teacher_id, pa.patent.document_file,
                    f"{pa.patent.get_patent_type_display()}: {pa.patent.title or pa.patent.pk}", pa.patent)
        for pa in PatentAuthor.objects.filter(patent__reporting_period=period)
        .select_related("patent").order_by("patent_id")
    ]


def _fundings(period, _teachers):
    return [
        DocumentRow(f.teacher_id, f.document_file, f"{f.get_source_type_display()}: {f.amount:,.2f}", f)
        for f in Funding.objects.filter(reporting_period=period).order_by("id")
    ]


DOCUMENTS = [
    DocumentKind("1,1", "1,1 Diplomlar", "Ilmiy daraja diplomi", _diplomas),
    DocumentKind("2,1", "2,1 Maqolalar", "Maqola PDF", _publications),
    DocumentKind("2,4-2,5", "2,4-2,5 Patentlar va guvohnomalar", "Patent / guvohnoma", _patents),
    DocumentKind("2,6", "2,6 Mablag'lar", "Shartnoma / kvitansiya", _fundings),
]
