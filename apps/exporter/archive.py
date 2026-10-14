"""
Полный пакет кафедры за период одним ZIP-архивом — то, что завкафедрой
скачивает кнопкой «Скачать всё (ZIP)»:

    <Кафедра>_<период>/
        Reyting_<Кафедра>_<период>.xlsx      — рейтинговая таблица (все листы)
        Maqolalar_royxati.xlsx               — кто какую статью внёс, h-индекс, есть ли PDF
        Maqolalar/
            <Ф.И.Ш. преподавателя>/
                <PDF статьи>
                ...

Папка на каждого преподавателя — чтобы сразу было видно, кто что загрузил.
"""

import re
import tempfile
import zipfile
from pathlib import Path

import openpyxl
from django.db.models import Q
from openpyxl.styles import Font

from apps.reports.models import Publication, TeacherHIndex
from apps.staff.models import Teacher
from .engine import export_report

_UNSAFE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def safe_name(text, limit=120):
    """Имя файла/папки, которое откроется и в Windows, и в Linux."""
    cleaned = _UNSAFE.sub(" ", str(text)).strip(" .")
    return cleaned[:limit].strip() or "nomsiz"


def _publications_register(period, teachers, pubs_by_teacher, file_paths):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Maqolalar"
    ws.append([
        "T/r", "O‘qituvchi F.I.Sh.", "h-indeks", "Maqola nomi", "Qayerda chop etilgan", "Jurnal", "Yili",
        "Kvartil", "Iqtiboslar", "Havola", "Fayl (arxivdagi yo‘li)",
    ])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    hindex = {
        rec.teacher_id: rec.h_index
        for rec in TeacherHIndex.objects.filter(reporting_period=period)
    }
    n = 0
    for teacher in teachers:
        pubs = pubs_by_teacher.get(teacher.pk) or [None]
        for pub in pubs:
            n += 1
            if pub is None:
                ws.append([n, teacher.full_name, hindex.get(teacher.pk), "— maqola kiritilmagan —"])
                continue
            ws.append([
                n, teacher.full_name, hindex.get(teacher.pk), pub.article_title, pub.get_indexing_display(),
                pub.journal_name, pub.publish_year, pub.quartile, pub.citations_count, pub.scopus_url,
                file_paths.get(pub.pk, "fayl yuklanmagan"),
            ])

    for col, width in zip("ABCDEFGHIJK", (5, 38, 9, 50, 26, 30, 7, 8, 10, 40, 60)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    return wb


def build_package(department, period):
    """Собирает ZIP во временный файл и возвращает (открытый файл, имя архива).
    Временный файл удаляется сам при закрытии (FileResponse его закроет)."""
    xlsx_path, _filled, _skipped = export_report(department, period)

    root = safe_name(f"{department.short_name or department.name}_{period.period_label}")
    pubs_by_teacher = {}
    for pub in (Publication.objects.filter(reporting_period=period)
                .select_related("teacher").order_by("teacher__full_name", "id")):
        pubs_by_teacher.setdefault(pub.teacher_id, []).append(pub)

    # все преподаватели кафедры + авторы статей этого периода (на случай перевода с другой кафедры)
    teachers = list(Teacher.objects.filter(
        Q(department=department, is_active=True) | Q(pk__in=pubs_by_teacher.keys())
    ).order_by("full_name"))

    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(xlsx_path, f"{root}/Reyting_{safe_name(xlsx_path.stem)}.xlsx")

        file_paths = {}
        for teacher in teachers:
            folder = f"{root}/Maqolalar/{safe_name(teacher.full_name)}"
            used = set()
            for pub in pubs_by_teacher.get(teacher.pk, []):
                if not pub.article_file:
                    continue
                try:
                    source = Path(pub.article_file.path)
                except (NotImplementedError, ValueError):
                    continue
                if not source.exists():
                    continue
                name = safe_name(Path(pub.article_file.name).name)
                stem, suffix = Path(name).stem, Path(name).suffix
                k = 2
                while name.lower() in used:
                    name = f"{stem}_{k}{suffix}"
                    k += 1
                used.add(name.lower())
                arcname = f"{folder}/{name}"
                zf.write(source, arcname)
                file_paths[pub.pk] = arcname.split("/", 1)[1]
            if not used:
                # пустая папка — видно, что преподаватель ничего не загрузил
                zf.writestr(f"{folder}/", "")

        register = _publications_register(period, teachers, pubs_by_teacher, file_paths)
        with tempfile.TemporaryFile() as reg_tmp:
            register.save(reg_tmp)
            reg_tmp.seek(0)
            zf.writestr(f"{root}/Maqolalar_royxati.xlsx", reg_tmp.read())

    tmp.seek(0)
    return tmp, f"{root}.zip"
