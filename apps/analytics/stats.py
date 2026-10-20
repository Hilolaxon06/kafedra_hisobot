"""
Yillik statistika va kafedralar reytingi.

Yil — ReportingPeriod.period_date ning yili ("holatiga" sanasi). Bir yilda
kafedrada bir nechta davr bo'lsa (masalan, mart va dekabr), fakt-jadvallar
(maqolalar, patentlar, mablag'lar...) shu yilning barcha davrlari bo'yicha
yig'iladi, shtat (daraja, o'qituvchilar soni) esa yilning eng so'nggi
davridagi snimkadan olinadi.

Reyting balli — WEIGHTS dagi vaznlar bilan hisoblangan jami ball, bir
o'qituvchiga bo'lingan (katta va kichik kafedralarni adolatli solishtirish
uchun). Metodika o'zgarsa — faqat WEIGHTS ni tahrirlang.
"""

from collections import OrderedDict
from decimal import Decimal

from django.db.models import Max, Sum
from django.utils.translation import gettext as _g, gettext_lazy as _

from apps.dashboard.views import _degree_column
from apps.reports.models import (
    Funding, GraduateEmployment, Patent, PostgradDefense, Publication,
    StudentMobility, TeacherHIndex, TeacherMobility,
)
from apps.staff.models import Teacher, TeacherPeriodSnapshot
from apps.workflow.models import ReportingPeriod

# Reyting vaznlari (ball). Maqolalar 1/N ulush bilan hisoblanadi.
WEIGHTS = {
    "pub_Q1": 10, "pub_Q2": 8, "pub_Q3": 6, "pub_Q4": 4,
    "pub_ranked_noq": 3,          # Scopus / WoS, kvartilsiz
    "pub_oak": 2, "pub_foreign": 2, "pub_local": 1,
    "pub_conference": 0.5, "pub_other": 1,
    "hindex": 1,                  # har bir h-indeks birligi
    "patent": 5,
    "funding_per_mln": 0.5,       # har 1 mln so'm uchun
    "defense_PhD": 6, "defense_DSc": 10,
    "mobility": 2,                # o'qituvchi mobilligi (har biri)
    "degree_share_pct": 0.1,      # daraja ulushining har 1 foizi (1 o'qituvchiga)
}

INDEXING_LABELS = OrderedDict([
    ("scopus", "Scopus"), ("wos", "Web of Science"), ("oak", _("OAK jurnallari")),
    ("foreign", _("Boshqa xorijiy")), ("local", _("Respublika jurnallari")),
    ("conference", _("Konferensiya")), ("other", _("Boshqa")),
])
QUARTILE_LABELS = OrderedDict([("Q1", "Q1"), ("Q2", "Q2"), ("Q3", "Q3"), ("Q4", "Q4"), ("none", _("Kvartilsiz"))])
DEGREE_LABELS = OrderedDict([("dsc", _("DSc / fan doktori")), ("phd", _("PhD / fan nomzodi")), ("none", _("Darajasiz"))])
PATENT_LABELS = OrderedDict([
    ("invention", _("Ixtiro")), ("utility_model", _("Foydali model")),
    ("industrial_design", _("Sanoat namunasi")), ("selection_achievement", _("Seleksiya yutug'i")),
])
FUNDING_LABELS = OrderedDict([
    ("foreign_international", _("Xorijiy / xalqaro")), ("state_program", _("Davlat dasturlari")),
    ("business_contract", _("Xo'jalik shartnomalari")),
])
MOBILITY_LABELS = OrderedDict([("outbound", _("Chiqish (outbound)")), ("inbound", _("Kelish (inbound)"))])
EMPLOYMENT_LABELS = OrderedDict([
    ("employed_state_or_business", _("Ishga joylashgan")), ("entrepreneur_or_founder", _("Tadbirkor / ta'sischi")),
    ("further_education_or_exempt", _("O'qishni davom ettiradi / boshqa")),
])


def available_years(departments):
    years = (ReportingPeriod.objects.filter(department__in=departments)
             .values_list("period_date__year", flat=True).distinct())
    return sorted(set(years), reverse=True)


def _share(pub):
    return Decimal(1) / Decimal(pub.department_co_authors_count or 1)


def _r(value, digits=2):
    return float(round(Decimal(value), digits))


def department_year(department, year):
    """Bitta kafedraning bir yillik barcha ko'rsatkichlari (dict)."""
    periods = list(ReportingPeriod.objects.filter(department=department, period_date__year=year)
                   .order_by("-period_date", "-id"))
    data = {"department": department, "year": year, "periods": periods, "has_data": bool(periods)}

    # --- shtat: yilning so'nggi davri snimkasi; snimka bo'lmasa — faol o'qituvchilar
    degrees = OrderedDict((k, 0) for k in DEGREE_LABELS)
    staff = 0
    if periods:
        snaps = (TeacherPeriodSnapshot.objects.filter(reporting_period=periods[0])
                 .select_related("academic_degree", "academic_title"))
        for snap in snaps:
            staff += 1
            column = _degree_column(snap)
            degrees["dsc" if column in ("dsc", "akademik") else "phd" if column == "phd" else "none"] += 1
        extra = Teacher.objects.filter(department=department, is_active=True).exclude(
            pk__in=snaps.values("teacher_id")).count()
        staff += extra
        degrees["none"] += extra
    with_degree = degrees["dsc"] + degrees["phd"]
    data.update(staff=staff, degrees=degrees, with_degree=with_degree,
                degree_share=_r(100 * with_degree / staff, 1) if staff else 0.0)

    # --- maqolalar (1/N ulush)
    indexing = OrderedDict((k, Decimal(0)) for k in INDEXING_LABELS)
    quartiles = OrderedDict((k, Decimal(0)) for k in QUARTILE_LABELS)
    citations = 0
    for pub in Publication.objects.filter(reporting_period__in=periods):
        share = _share(pub)
        indexing[pub.indexing] = indexing.get(pub.indexing, Decimal(0)) + share
        if pub.indexing in Publication.RANKED_INDEXINGS:
            quartiles[pub.quartile or "none"] += share
        citations += pub.citations_count
    data.update(
        indexing=OrderedDict((k, _r(v)) for k, v in indexing.items()),
        quartiles=OrderedDict((k, _r(v)) for k, v in quartiles.items()),
        publications=_r(sum(indexing.values())),
        scopus_wos=_r(indexing["scopus"] + indexing["wos"]),
        citations=citations,
    )

    # --- h-indeks: har bir o'qituvchining yildagi eng yuqori qiymati, yig'indisi
    hmax = (TeacherHIndex.objects.filter(reporting_period__in=periods)
            .values("teacher").annotate(h=Max("h_index")))
    data["hindex"] = sum(row["h"] for row in hmax)

    # --- patentlar
    patents = OrderedDict((k, 0) for k in PATENT_LABELS)
    for ptype in Patent.objects.filter(reporting_period__in=periods).values_list("patent_type", flat=True):
        patents[ptype] = patents.get(ptype, 0) + 1
    data.update(patent_types=patents, patents=sum(patents.values()))

    # --- jalb qilingan mablag'lar
    funding = OrderedDict((k, 0.0) for k in FUNDING_LABELS)
    for row in (Funding.objects.filter(reporting_period__in=periods)
                .values("source_type").annotate(total=Sum("amount"))):
        funding[row["source_type"]] = float(row["total"] or 0)
    data.update(funding_sources=funding, funding=sum(funding.values()))
    data["funding_mln"] = round(data["funding"] / 1_000_000, 1)

    # --- himoyalar, mobillik, bitiruvchilar
    defenses = OrderedDict([("PhD", 0), ("DSc", 0)])
    for dtype in PostgradDefense.objects.filter(reporting_period__in=periods).values_list("degree_type", flat=True):
        defenses[dtype] = defenses.get(dtype, 0) + 1
    mobility = OrderedDict((k, 0) for k in MOBILITY_LABELS)
    for direction in TeacherMobility.objects.filter(reporting_period__in=periods).values_list("direction", flat=True):
        mobility[direction] = mobility.get(direction, 0) + 1
    employment = OrderedDict((k, 0) for k in EMPLOYMENT_LABELS)
    for status in GraduateEmployment.objects.filter(reporting_period__in=periods).values_list("status", flat=True):
        employment[status] = employment.get(status, 0) + 1
    data.update(
        defense_types=defenses, defenses=sum(defenses.values()),
        mobility_dirs=mobility, mobility=sum(mobility.values()),
        student_mobility=StudentMobility.objects.filter(reporting_period__in=periods).count(),
        employment=employment, graduates=sum(employment.values()),
    )

    data["score"], data["score_per_teacher"], data["score_parts"] = _score(data)
    return data


def _score(d):
    w = WEIGHTS
    q = d["quartiles"]
    ix = d["indexing"]
    parts = OrderedDict([
        (_g("Maqolalar"), sum(q[k] * w[f"pub_{k}"] for k in ("Q1", "Q2", "Q3", "Q4"))
         + q["none"] * w["pub_ranked_noq"]
         + ix["oak"] * w["pub_oak"] + ix["foreign"] * w["pub_foreign"] + ix["local"] * w["pub_local"]
         + ix["conference"] * w["pub_conference"] + ix["other"] * w["pub_other"]),
        (_g("H-indeks"), d["hindex"] * w["hindex"]),
        (_g("Patentlar"), d["patents"] * w["patent"]),
        (_g("Mablag'lar"), d["funding"] / 1_000_000 * w["funding_per_mln"]),
        (_g("Himoyalar"), d["defense_types"].get("PhD", 0) * w["defense_PhD"]
         + d["defense_types"].get("DSc", 0) * w["defense_DSc"]),
        (_g("Mobillik"), d["mobility"] * w["mobility"]),
    ])
    total = sum(parts.values())
    per_teacher = total / d["staff"] if d["staff"] else 0.0
    # daraja ulushi — allaqachon nisbiy ko'rsatkich, 1 o'qituvchiga ballga qo'shiladi
    per_teacher += d["degree_share"] * w["degree_share_pct"]
    return _r(total, 1), _r(per_teacher, 2), OrderedDict((k, _r(v, 1)) for k, v in parts.items())


def ranking(departments, year):
    """Shu yili kamida bitta davri bor kafedralar, 1 o'qituvchiga ball bo'yicha."""
    rows = [department_year(dept, year) for dept in departments]
    rows = [r for r in rows if r["has_data"]]
    rows.sort(key=lambda r: (-r["score_per_teacher"], -r["score"], r["department"].name))
    for place, row in enumerate(rows, start=1):
        row["place"] = place
    return rows


SUM_KEYS = ("staff", "with_degree", "publications", "scopus_wos", "citations", "hindex",
            "patents", "funding", "defenses", "mobility", "student_mobility", "graduates", "score")
DICT_KEYS = ("degrees", "indexing", "quartiles", "patent_types", "funding_sources",
             "defense_types", "mobility_dirs", "employment")


def combine(rows):
    """Bir nechta kafedra ko'rsatkichlarini bitta jamlangan dict ga yig'ish."""
    total = {key: 0 for key in SUM_KEYS}
    for key in DICT_KEYS:
        total[key] = OrderedDict()
    for row in rows:
        for key in SUM_KEYS:
            total[key] += row[key]
        for key in DICT_KEYS:
            for k, v in row[key].items():
                total[key][k] = total[key].get(k, 0) + v
    for key in ("publications", "scopus_wos", "score"):
        total[key] = round(total[key], 2)
    for key in ("indexing", "quartiles"):
        total[key] = OrderedDict((k, round(v, 2)) for k, v in total[key].items())
    total["degree_share"] = round(100 * total["with_degree"] / total["staff"], 1) if total["staff"] else 0.0
    total["departments_count"] = len(rows)
    return total


def overview(departments, year):
    rows = ranking(departments, year)
    return rows, combine(rows)


def yearly_series(departments):
    """Yillar dinamikasi: [(yil, jamlangan dict), ...] o'sish tartibida."""
    return [(year, combine(ranking(departments, year))) for year in sorted(available_years(departments))]


def slices(values, labels):
    """Pie-diagramma uchun: [(nom, qiymat), ...] — faqat noldan katta qismlar."""
    return [(str(labels.get(k, k)), v) for k, v in values.items() if v]


def charts(total):
    """Pie-diagrammalar ro'yxati: [(sarlavha, [(nom, qiymat)...], birlik), ...]."""
    return [
        (_g("Maqolalar (nashr turi bo‘yicha)"), slices(total["indexing"], INDEXING_LABELS), ""),
        (_g("Scopus / WoS kvartillari"), slices(total["quartiles"], QUARTILE_LABELS), ""),
        (_g("Ilmiy salohiyat (o‘qituvchilar)"), slices(total["degrees"], DEGREE_LABELS), ""),
        (_g("Jalb qilingan mablag‘lar"), slices(total["funding_sources"], FUNDING_LABELS), " " + _g("so‘m")),
        (_g("Patentlar turi bo‘yicha"), slices(total["patent_types"], PATENT_LABELS), ""),
        (_g("O‘qituvchilar mobilligi"), slices(total["mobility_dirs"], MOBILITY_LABELS), ""),
        (_g("Dissertatsiya himoyalari"), slices(total["defense_types"], {}), ""),
        (_g("Bitiruvchilar bandligi"), slices(total["employment"], EMPLOYMENT_LABELS), ""),
    ]
