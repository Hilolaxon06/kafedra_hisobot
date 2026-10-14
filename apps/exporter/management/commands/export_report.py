from django.core.management.base import BaseCommand, CommandError

from apps.workflow.models import ReportingPeriod
from apps.exporter.engine import export_report


class Command(BaseCommand):
    help = "Сформировать .xlsx отчёт кафедры за указанный отчётный период."

    def add_arguments(self, parser):
        parser.add_argument("department_id", type=int)
        parser.add_argument("period_label", type=str)

    def handle(self, *args, **options):
        try:
            period = ReportingPeriod.objects.select_related("department").get(
                department_id=options["department_id"],
                period_label=options["period_label"],
            )
        except ReportingPeriod.DoesNotExist as exc:
            raise CommandError(
                "Отчётный период не найден. Проверьте department_id и period_label "
                "(создаются в /admin/workflow/reportingperiod/)."
            ) from exc

        path, filled, skipped = export_report(period.department, period)
        self.stdout.write(self.style.SUCCESS(f"Готово: {path}"))
        self.stdout.write(f"Заполненные листы: {', '.join(filled) or '—'}")
        if skipped:
            self.stdout.write(
                self.style.WARNING(
                    f"Листы без автозаполнения (нужно дописать fill_* в apps/exporter/sheets.py): "
                    f"{', '.join(skipped)}"
                )
            )
