from django import forms

from apps.reports.models import Patent
from apps.staff.models import Teacher


class PatentSelfForm(forms.ModelForm):
    class Meta:
        model = Patent
        fields = ["reporting_period", "title", "patent_type", "registered_in_scopus",
                  "has_license_agreement", "document_file"]


class TeacherProfileForm(forms.ModelForm):
    """Преподаватель сам вносит данные о своём дипломе об учёной степени и
    приказе о приёме на работу (лист «1,1»). Ставку, должность, тип занятости
    и сам факт наличия степени/звания за конкретный период (штатная
    ведомость, лист «5») по-прежнему задаёт кафедра через admin — это
    кадровые данные, а не то, что преподаватель вводит о себе."""

    class Meta:
        model = Teacher
        fields = [
            "specialty_name", "diploma_series", "diploma_number", "diploma_file",
            "foreign_university_name",
            "hire_order_number", "hire_order_date",
        ]
        widgets = {
            "hire_order_date": forms.DateInput(attrs={"type": "date"}),
        }
