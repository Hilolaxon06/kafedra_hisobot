"""
Совместные статьи внутри кафедры.

Каждый соавтор-сотрудник вносит статью в свой кабинет сам и указывает N —
число соавторов с кафедры (Publication.department_co_authors_count). Если
двое внесли одну статью, а N указали 1, статья засчиталась бы кафедре
дважды. Поэтому «одной статьёй» считаются записи одной кафедры за один год
с одинаковым названием (без учёта регистра и пробелов) или одинаковой
ссылкой, и действующее N = max(указанное N, сколько раз статью внесли):
одна статья никогда не даёт кафедре больше 1.

Записи, где внесших больше, чем указанное N, завкафедрой видит в админке
(фильтр «N не совпадает») и исправляет.
"""

from collections import Counter
from decimal import Decimal


def _title_key(pub):
    return " ".join((pub.article_title or "").lower().split())


def _url_key(pub):
    return (pub.scopus_url or "").strip().lower().rstrip("/")


def _scope(pub):
    period = pub.reporting_period
    return period.department_id, period.period_date.year


def entries_per_article(pubs):
    """{pub.pk: сколько записей этой же статьи внесено на кафедре за год}.
    pubs должны покрывать всю кафедру за год (или больше) — иначе соавторы
    вне выборки не будут учтены."""
    pubs = list(pubs)
    by_title, by_url = Counter(), Counter()
    for pub in pubs:
        if _title_key(pub):
            by_title[(_scope(pub), _title_key(pub))] += 1
        if _url_key(pub):
            by_url[(_scope(pub), _url_key(pub))] += 1
    return {
        pub.pk: max(1, by_title.get((_scope(pub), _title_key(pub)), 0) if _title_key(pub) else 0,
                    by_url.get((_scope(pub), _url_key(pub)), 0) if _url_key(pub) else 0)
        for pub in pubs
    }


def effective_shares(pubs):
    """{pub.pk: Decimal-доля} с учётом повторных записей одной статьи."""
    pubs = list(pubs)
    entries = entries_per_article(pubs)
    return {
        pub.pk: Decimal(1) / Decimal(max(pub.department_co_authors_count or 1, entries[pub.pk]))
        for pub in pubs
    }


def department_year_publications(department_id, year):
    from .models import Publication
    return (Publication.objects.filter(reporting_period__department_id=department_id,
                                       reporting_period__period_date__year=year)
            .select_related("reporting_period", "teacher"))


def mismatched(pubs):
    """Записи, где статью внесли больше сотрудников, чем указано в N."""
    pubs = list(pubs)
    entries = entries_per_article(pubs)
    return [pub for pub in pubs if entries[pub.pk] > (pub.department_co_authors_count or 1)]
