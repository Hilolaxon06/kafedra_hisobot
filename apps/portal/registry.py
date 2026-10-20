"""
Конфигурация самообслуживания преподавателя: какие модели он может вести
сам (список, добавление, редактирование только своих записей), какими
полями и что показывать в списке.

Patent сюда не входит — у него авторство M2M (через PatentAuthor), для него
отдельные view-функции в views.py (patents_list/patents_form), логика та же,
только регистрация автора идёт через промежуточную таблицу.

Чтобы добавить преподавателям возможность вести ещё один тип показателя —
достаточно дописать сюда одну запись, отдельная страница/форма не нужна:
generic_list/generic_form в views.py работают с любым слагом из REGISTRY.
"""

from django.utils.translation import gettext_lazy as _

from apps.reports.models import Publication, Funding, TeacherMobility, PostgradDefense, TeacherHIndex

REGISTRY = {
    "publications": {
        "model": Publication,
        "teacher_field": "teacher",
        "title": _("Maqolalar (Scopus va boshqalar)"),
        "fields": [
            "reporting_period", "indexing", "journal_name", "publish_year", "publish_month",
            "article_title", "language", "scopus_url", "quartile", "citation_tier",
            "citations_count", "department_co_authors_count", "article_file",
        ],
        "list_columns": ["reporting_period", "indexing", "article_title", "quartile", "article_file"],
    },
    "hindex": {
        "model": TeacherHIndex,
        "teacher_field": "teacher",
        "title": _("H-indeks (Scopus)"),
        "fields": ["reporting_period", "h_index"],
        "list_columns": ["reporting_period", "h_index"],
    },
    "fundings": {
        "model": Funding,
        "teacher_field": "teacher",
        "title": _("Jalb qilingan mablag‘lar"),
        "fields": ["reporting_period", "source_type", "amount", "document_file"],
        "list_columns": ["reporting_period", "source_type", "amount"],
    },
    "mobility": {
        "model": TeacherMobility,
        "teacher_field": "teacher",
        "title": _("Xalqaro mobillik"),
        "fields": ["reporting_period", "direction", "partner_institution_name"],
        "list_columns": ["reporting_period", "direction", "partner_institution_name"],
    },
    "defenses": {
        "model": PostgradDefense,
        "teacher_field": "advisor_teacher",
        "title": _("Mening rahbarligimdagi himoyalar"),
        "fields": ["reporting_period", "degree_type", "defended_full_name"],
        "list_columns": ["reporting_period", "degree_type", "defended_full_name"],
    },
}
