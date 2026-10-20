"""
Sahifalar:

- statistika — tanlangan yil bo'yicha ko'rsatkichlar, pie-diagrammalar va
  yillar dinamikasi (o'z kafedralari: superuser — hammasi, mudir — o'ziniki);
- reyting   — /reyting/, saytning chap menyusida («Jadval» va «Admin-panel»
  orasida), admin-panel ichida emas. Kafedralar reytingi. Solishtirish uchun BARCHA kafedralar
  ko'rsatiladi, lekin faqat jamlangan sonlar (shaxsiy ma'lumotlarsiz);
  mudirning o'z kafedrasi ajratib ko'rsatiladi;
- statistika va taqdimot — /statistika/, chap menyuda «Reyting» ostida;
- taqdimot  — yillik hisobot bo'yicha .pptx taqdimot.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.core.access import managed_departments
from apps.core.models import Department

from . import stats
from .presentation import build_presentation

PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _filters(request, departments):
    """Yil va kafedra filtrlari (GET ?yil=2026&kafedra=3)."""
    years = stats.available_years(departments)
    year = request.GET.get("yil")
    year = int(year) if year and year.isdigit() and int(year) in years else (years[0] if years else None)
    selected = request.GET.get("kafedra")
    chosen = departments
    if selected and selected.isdigit() and departments.filter(pk=selected).exists():
        chosen = departments.filter(pk=selected)
    else:
        selected = ""
    return years, year, selected, chosen


def _staff_only(view):
    """Statistika va taqdimot — admin va kafedra mudirlari (is_staff) uchun;
    o'qituvchini uning kabinetiga yo'naltiramiz."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect("portal:index")
        return view(request, *args, **kwargs)

    return wrapped


@_staff_only
def statistika(request):
    departments = managed_departments(request.user).order_by("name")
    years, year, selected, chosen = _filters(request, departments)
    rows, total = stats.overview(chosen, year) if year else ([], None)
    return render(request, "analytics/statistika.html", {
        "departments": departments, "years": years, "year": year, "selected": selected,
        "rows": rows, "total": total, "charts": stats.charts(total) if total else [],
        "series": stats.yearly_series(chosen),
    })


@_staff_only
def reyting(request):
    # ajratib ko'rsatiladigan "o'z" kafedra: mudir — o'zi boshqaradigan; superuser — kartochkasidagi (bo'lsa)
    teacher = getattr(request.user, "teacher_profile", None)
    if request.user.is_superuser:
        mine = {teacher.department_id} if teacher else set()
    else:
        mine = set(managed_departments(request.user).values_list("pk", flat=True))
    everyone = Department.objects.select_related("faculty").order_by("name")
    years = stats.available_years(everyone)
    year = request.GET.get("yil")
    year = int(year) if year and year.isdigit() and int(year) in years else (years[0] if years else None)
    rows = stats.ranking(everyone, year) if year else []
    top = max((r["score_per_teacher"] for r in rows), default=0) or 1
    for row in rows:
        row["mine"] = row["department"].pk in mine
        row["bar"] = round(100 * row["score_per_teacher"] / top)
    return render(request, "analytics/reyting.html", {
        "years": years, "year": year, "rows": rows, "weights": stats.WEIGHTS,
        "has_mine": any(r["mine"] for r in rows),
    })


@_staff_only
def taqdimot(request):
    departments = managed_departments(request.user).order_by("name")
    years, year, selected, chosen = _filters(request, departments)
    if not year:
        return redirect("analytics:statistika")
    content, filename = build_presentation(chosen, year, request.user)
    response = HttpResponse(content, content_type=PPTX_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
