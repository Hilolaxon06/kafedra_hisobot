"""Четыре типа занятости, по кодам которых exporter раскладывает людей по
секциям листа «5». Существующие записи не трогаем."""

from django.db import migrations

STANDARD = [
    ("asosiy", "Asosiy shtat", 1),
    ("ichki_orindosh", "Ichki o‘rindosh", 2),
    ("tashqi_orindosh", "Tashqi o‘rindosh", 3),
    ("soatbay", "Soatbay", 4),
]


def create(apps, schema_editor):
    EmploymentType = apps.get_model("dictionaries", "EmploymentType")
    for code, name, order in STANDARD:
        EmploymentType.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})


class Migration(migrations.Migration):
    dependencies = [("dictionaries", "0001_initial")]

    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
