"""
Генератор отчёта: берёт оригинальный файл-шаблон (тот самый .xlsx, который
кафедра сдаёт в деканат/отдел рейтинга) и заполняет его данными из БД за
выбранный ReportingPeriod — вместо того чтобы каждый раз набирать всё заново
руками.

Статус: подключены два листа как рабочий пример архитектуры —
"5" (штатная ведомость) и "1,1" (доля ППС с учёной степенью). Остальные ~17
листов заполняются по тому же принципу: см. README «Как добавить новый
лист» — там пошагово описано, как дописать ещё один fill_* и
зарегистрировать его в SHEET_FILLERS.
"""

from pathlib import Path

import openpyxl
from django.conf import settings

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates_store" / "kafedra_hisobot_template.xlsx"


def load_template() -> openpyxl.Workbook:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Файл-шаблон не найден: {TEMPLATE_PATH}. Положите официальную форму "
            "министерства в apps/exporter/templates_store/."
        )
    return openpyxl.load_workbook(TEMPLATE_PATH)


def output_path(department, period) -> Path:
    safe_dept = (department.short_name or department.name).replace(" ", "_")
    safe_period = period.period_label.replace(" ", "_")
    filename = f"{safe_dept}_{safe_period}.xlsx"
    return Path(settings.EXPORTS_DIR) / filename


def clear_row(ws, row, columns):
    for col in columns:
        ws.cell(row=row, column=col).value = None


def write_row(ws, row, values_by_col):
    """values_by_col: {номер_колонки (1-based): значение}"""
    for col, value in values_by_col.items():
        ws.cell(row=row, column=col).value = value


def export_report(department, period):
    """
    Собирает итоговый .xlsx для одной кафедры за один отчётный период.
    Возвращает (путь к сохранённому файлу, заполненные листы, пропущенные листы).
    """
    from .sheets import SHEET_FILLERS

    wb = load_template()
    for ws in wb.worksheets:
        title = ws["A1"].value
        if isinstance(title, str) and "{kafedra}" in title:
            ws["A1"].value = title.replace("{kafedra}", department.name)

    filled_sheets = []
    skipped_sheets = []
    for sheet_name, filler in SHEET_FILLERS.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        filler(ws, period)
        filled_sheets.append(sheet_name)

    for name in wb.sheetnames:
        if name not in SHEET_FILLERS:
            skipped_sheets.append(name)

    path = output_path(department, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path, filled_sheets, skipped_sheets
