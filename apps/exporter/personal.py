"""
Shaxsiy hisobot o'qituvchining o'zi uchun: u kabinetga kiritgan maqolalar va
ilmiy ishlar bitta ZIP arxivda (kabinetdagi «Mening hisobotim» sahifasi):

    Hisobot_<F.I.Sh.>_<davr | barcha davrlar>/
        Hisobot_<F.I.Sh.>.xlsx               — «Umumiy» varag'i va har bir ko'rsatkich uchun alohida varaq
        Diplomlar/                    diplom.pdf
        Maqolalar/                    maqola1.pdf, ...
        Patentlar va guvohnomalar/    ...
        Mablag'lar/                   shartnoma.pdf

Papka nomlari kafedra arxividagi bilan bir xil (documents.DOCUMENTS) va faqat
haqiqatan yuklangan fayllar uchun yaratiladi. Fayllar ZIP'ga
archive.build_package'dagi yordamchi funksiyalar orqali qo'shiladi.
"""

import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import openpyxl
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.reports.models import (
    Funding, Patent, PostgradDefense, Publication, TeacherHIndex, TeacherMobility,
)
from apps.workflow.models import ReportingPeriod
from .archive import MISSING_ON_DISK, NO_FILE, _bold_header, _source_path, _unique, safe_name
from .documents import DOCUMENTS

_FOLDERS = {kind.sheet: kind.folder for kind in DOCUMENTS}
FILE_COLUMN = ("Fayl (arxivdagi yo‘li)", 60)


@dataclass(frozen=True)
class Section:
    key: str
    title: str             # sahifadagi va «Umumiy» varag'idagi nomi
    sheet_title: str       # xlsx varag'ining nomi (31 belgigacha)
    records: Callable      # records(teacher) -> queryset (barcha davrlar)
    columns: list          # [(sarlavha, kenglik), ...]
    values: Callable       # values(obj) -> ustunlar qiymatlari
    folder_sheet: str = None   # fayl bo'lsa — documents.DOCUMENTS dagi varaq (papka nomi undan)
    file_attr: str = None


def _label(period):
    return period.period_label if period else ""


SECTIONS = [
    Section(
        "publications", _("Maqolalar"), "Maqolalar",
        lambda t: Publication.objects.filter(teacher=t),
        [("Davr", 12), ("Maqola nomi", 50), ("Qayerda chop etilgan", 26), ("Jurnal", 30), ("Yili", 7),
         ("Kvartil", 8), ("Iqtiboslar", 10), ("Hammualliflar (N)", 12), ("Ulush (1/N)", 10), ("Havola", 40)],
        lambda p: [_label(p.reporting_period), p.article_title, str(p.get_indexing_display()), p.journal_name,
                   p.publish_year, p.quartile, p.citations_count, p.department_co_authors_count,
                   round(float(p.share), 2), p.scopus_url],
        "2,1", "article_file",
    ),
    Section(
        "patents", _("Patentlar va guvohnomalar"), "Patentlar",
        lambda t: Patent.objects.filter(patentauthor__teacher=t).distinct(),
        [("Davr", 12), ("Nomi", 50), ("Turi", 32), ("Scopus'da", 10), ("Litsenziya shartnomasi", 14)],
        lambda p: [_label(p.reporting_period), p.title, str(p.get_patent_type_display()),
                   "ha" if p.registered_in_scopus else "yo‘q", "ha" if p.has_license_agreement else "yo‘q"],
        "2,4-2,5", "document_file",
    ),
    Section(
        "fundings", _("Jalb qilingan mablag‘lar"), "Mablag'lar",
        lambda t: Funding.objects.filter(teacher=t),
        [("Davr", 12), ("Manba", 40), ("Summa", 16)],
        lambda f: [_label(f.reporting_period), str(f.get_source_type_display()), float(f.amount)],
        "2,6", "document_file",
    ),
    Section(
        "defenses", _("Mening rahbarligimdagi himoyalar"), "Himoyalar",
        lambda t: PostgradDefense.objects.filter(advisor_teacher=t),
        [("Davr", 12), ("Daraja", 24), ("Izlanuvchi F.I.Sh.", 40)],
        lambda d: [_label(d.reporting_period), str(d.get_degree_type_display()), d.defended_full_name],
    ),
    Section(
        "mobility", _("Xalqaro mobillik"), "Mobillik",
        lambda t: TeacherMobility.objects.filter(teacher=t),
        [("Davr", 12), ("Yo‘nalish", 14), ("Hamkor OTM", 50)],
        lambda m: [_label(m.reporting_period), str(m.get_direction_display()), m.partner_institution_name],
    ),
    Section(
        "hindex", _("H-indeks (Scopus)"), "H-indeks",
        lambda t: TeacherHIndex.objects.filter(teacher=t),
        [("Davr", 12), ("h-indeks", 10)],
        lambda h: [_label(h.reporting_period), h.h_index],
    ),
]


def teacher_periods(teacher):
    """Davrlar ro'yxati (filtr uchun): o'qituvchi kafedrasining davrlari va
    u yozuv kiritgan boshqa davrlar (boshqa kafedradan o'tgan bo'lsa)."""
    ids = set()
    for section in SECTIONS:
        ids.update(section.records(teacher).values_list("reporting_period_id", flat=True))
    return (ReportingPeriod.objects.filter(department=teacher.department) | ReportingPeriod.objects.filter(pk__in=ids)
            ).distinct().order_by("-period_date")


def _records(section, teacher, period):
    qs = section.records(teacher)
    if period is not None:
        qs = qs.filter(reporting_period=period)
    return list(qs.select_related("reporting_period").order_by("reporting_period__period_date", "id"))


def collect(teacher, period=None):
    """[(section, [yozuvlar])] — tanlangan davr bo'yicha (None — barcha davrlar)."""
    return [(section, _records(section, teacher, period)) for section in SECTIONS]


def summary(teacher, period=None):
    """Sahifa va «Umumiy» varag'i uchun: har bir ko'rsatkich bo'yicha yozuvlar
    soni, fayl biriktirilganlari (fayl nazarda tutilmagan bo'lsa — None)."""
    rows = []
    for section, records in collect(teacher, period):
        with_file = None
        if section.file_attr:
            with_file = sum(1 for obj in records if getattr(obj, section.file_attr))
        rows.append({"key": section.key, "title": section.title, "count": len(records), "with_file": with_file})
    return rows


def build_teacher_package(teacher, period=None):
    """ZIP'ni vaqtinchalik faylga yig'adi va (ochiq fayl, arxiv nomi) qaytaradi.
    Vaqtinchalik fayl yopilganda o'zi o'chadi (FileResponse uni yopadi)."""
    name = safe_name(teacher.full_name)
    scope = period.period_label if period else "barcha davrlar"
    root = safe_name(f"Hisobot_{name}_{scope}")
    data = collect(teacher, period)

    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        statuses = {}
        used_by_folder = {}

        def add_file(field_file, folder_sheet, key):
            source = _source_path(field_file)
            if source is None:
                statuses[key] = MISSING_ON_DISK if field_file else NO_FILE
                return
            folder = safe_name(_FOLDERS[folder_sheet])
            used = used_by_folder.setdefault(folder, set())
            relative = f"{folder}/{_unique(safe_name(Path(field_file.name).name), used)}"
            zf.write(source, f"{root}/{relative}")
            statuses[key] = relative

        add_file(teacher.diploma_file, "1,1", "diploma")
        for section, records in data:
            if section.file_attr:
                for obj in records:
                    add_file(getattr(obj, section.file_attr), section.folder_sheet, (section.key, obj.pk))

        workbook = _workbook(teacher, period, data, statuses)
        with tempfile.TemporaryFile() as xlsx_tmp:
            workbook.save(xlsx_tmp)
            xlsx_tmp.seek(0)
            zf.writestr(f"{root}/Hisobot_{name}.xlsx", xlsx_tmp.read())

    tmp.seek(0)
    return tmp, f"{root}.zip"


def _workbook(teacher, period, data, statuses):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Umumiy"
    _bold_header(ws, ["Ko‘rsatkich", "Yozuvlar", "Fayl biriktirilgan", "Fayl yo‘q"], (40, 12, 18, 12))
    for section, records in data:
        if section.file_attr:
            attached = sum(1 for obj in records if getattr(obj, section.file_attr))
            ws.append([str(section.title), len(records), attached, len(records) - attached])
        else:
            ws.append([str(section.title), len(records)])
    ws.append([])
    ws.append(["O‘qituvchi", teacher.full_name])
    ws.append(["Kafedra", str(teacher.department)])
    ws.append(["Davr", period.period_label if period else "barcha davrlar"])
    ws.append(["Ilmiy daraja diplomi", statuses["diploma"]])
    ws.append(["Tuzilgan sana", timezone.localtime().strftime("%d.%m.%Y %H:%M")])

    for section, records in data:
        ws = wb.create_sheet(section.sheet_title)
        columns = [("T/r", 5)] + section.columns + ([FILE_COLUMN] if section.file_attr else [])
        _bold_header(ws, [title for title, _w in columns], [width for _t, width in columns])
        for n, obj in enumerate(records, start=1):
            row = [n] + section.values(obj)
            if section.file_attr:
                row.append(statuses[(section.key, obj.pk)])
            ws.append(row)
        if not records:
            ws.append(["", "— yozuvlar yo‘q —"])
    return wb
