"""
Полный пакет кафедры за период одним ZIP-архивом — то, что завкафедрой
скачивает кнопкой «Скачать всё (ZIP)»:

    Arxiv_<Кафедра>_<период>/
        Reyting_<Кафедра>_<период>.xlsx      — рейтинговая таблица (все листы)
        Hujjatlar_royxati.xlsx               — какие документы приложены, каких не хватает
                                               (+ лист «Maqolalar»: статьи, h-индекс, квартиль)
        <Ф.И.Ш. преподавателя>/
            Diplomlar/                       diplom.pdf
            Maqolalar/                       maqola1.pdf, ...
            Patentlar va guvohnomalar/       ...
            Mablag'lar/                      shartnoma.pdf

Какие документы куда кладутся — documents.DOCUMENTS. Папки создаются
только под реально загруженные файлы: нет патента — нет папки «2,4-2,5».
"""

import re
import tempfile
import zipfile
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from apps.reports.models import TeacherHIndex
from apps.staff.models import Teacher
from .documents import DOCUMENTS
from .engine import export_report

_UNSAFE = re.compile(r'[\\/:*?"<>|\r\n\t]+')

NO_FILE = "fayl yuklanmagan"
MISSING_ON_DISK = "fayl serverda topilmadi"


def safe_name(text, limit=120):
    """Имя файла/папки, которое откроется и в Windows, и в Linux."""
    cleaned = _UNSAFE.sub(" ", str(text)).strip(" .")
    return cleaned[:limit].strip() or "nomsiz"


def _source_path(field_file):
    """Путь к файлу на диске или None (поле пустое / файла нет / не локальное хранилище)."""
    if not field_file:
        return None
    try:
        source = Path(field_file.path)
    except (NotImplementedError, ValueError):
        return None
    return source if source.exists() else None


def _unique(name, used):
    stem, suffix = Path(name).stem, Path(name).suffix
    k = 2
    while name.lower() in used:
        name = f"{stem}_{k}{suffix}"
        k += 1
    used.add(name.lower())
    return name


def _bold_header(ws, headers, widths):
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"


def _register(period, teachers, rows_by_kind, statuses):
    """Hujjatlar_royxati.xlsx: лист «Hujjatlar» — все документы по всем
    видам; лист «Maqolalar» — подробный реестр статей с h-индексом."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Hujjatlar"
    _bold_header(ws, ["T/r", "O‘qituvchi F.I.Sh.", "Varaq", "Hujjat turi", "Tavsif", "Fayl (arxivdagi yo‘li)"],
                 (5, 38, 9, 26, 60, 80))
    n = 0
    for teacher in teachers:
        for kind in DOCUMENTS:
            for row in rows_by_kind[kind.sheet].get(teacher.pk, []):
                n += 1
                ws.append([n, teacher.full_name, kind.sheet, kind.title, row.description, statuses[id(row)]])

    pubs_kind = next(k for k in DOCUMENTS if k.sheet == "2,1")
    ws = wb.create_sheet("Maqolalar")
    _bold_header(ws, [
        "T/r", "O‘qituvchi F.I.Sh.", "h-indeks", "Maqola nomi", "Qayerda chop etilgan", "Jurnal", "Yili",
        "Kvartil", "Iqtiboslar", "Havola", "Fayl (arxivdagi yo‘li)",
    ], (5, 38, 9, 50, 26, 30, 7, 8, 10, 40, 60))
    hindex = {
        rec.teacher_id: rec.h_index
        for rec in TeacherHIndex.objects.filter(reporting_period=period)
    }
    n = 0
    for teacher in teachers:
        rows = rows_by_kind[pubs_kind.sheet].get(teacher.pk) or [None]
        for row in rows:
            n += 1
            if row is None:
                ws.append([n, teacher.full_name, hindex.get(teacher.pk), "— maqola kiritilmagan —"])
                continue
            pub = row.obj
            ws.append([
                n, teacher.full_name, hindex.get(teacher.pk), pub.article_title, pub.get_indexing_display(),
                pub.journal_name, pub.publish_year, pub.quartile, pub.citations_count, pub.scopus_url,
                statuses[id(row)],
            ])
    return wb


def build_package(department, period):
    """Собирает ZIP во временный файл и возвращает (открытый файл, имя архива).
    Временный файл удаляется сам при закрытии (FileResponse его закроет)."""
    xlsx_path, _filled, _skipped = export_report(department, period)

    dept = department.short_name or department.name
    root = safe_name(f"Arxiv_{dept}_{period.period_label}")

    department_teachers = list(Teacher.objects.filter(department=department, is_active=True))
    rows_by_kind = {}
    author_ids = set()
    for kind in DOCUMENTS:
        by_teacher = {}
        for row in kind.rows(period, department_teachers):
            by_teacher.setdefault(row.teacher_id, []).append(row)
        rows_by_kind[kind.sheet] = by_teacher
        author_ids.update(by_teacher)

    # все преподаватели кафедры + авторы записей этого периода (на случай перевода с другой кафедры)
    known = {t.pk for t in department_teachers}
    teachers = sorted(
        department_teachers + list(Teacher.objects.filter(pk__in=author_ids - known)),
        key=lambda t: t.full_name,
    )

    statuses = {}
    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(xlsx_path, f"{root}/Reyting_{safe_name(f'{dept}_{period.period_label}')}.xlsx")

        for teacher in teachers:
            teacher_folder = safe_name(teacher.full_name)
            for kind in DOCUMENTS:
                used = set()
                for row in rows_by_kind[kind.sheet].get(teacher.pk, []):
                    source = _source_path(row.file)
                    if source is None:
                        statuses[id(row)] = MISSING_ON_DISK if row.file else NO_FILE
                        continue
                    name = _unique(safe_name(Path(row.file.name).name), used)
                    relative = f"{teacher_folder}/{safe_name(kind.folder)}/{name}"
                    zf.write(source, f"{root}/{relative}")
                    statuses[id(row)] = relative

        register = _register(period, teachers, rows_by_kind, statuses)
        with tempfile.TemporaryFile() as reg_tmp:
            register.save(reg_tmp)
            reg_tmp.seek(0)
            zf.writestr(f"{root}/Hujjatlar_royxati.xlsx", reg_tmp.read())

    tmp.seek(0)
    return tmp, f"{root}.zip"
