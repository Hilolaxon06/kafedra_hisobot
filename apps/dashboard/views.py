from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.access import managed_departments
from apps.staff.models import Teacher, TeacherPeriodSnapshot
from apps.workflow.models import ReportingPeriod
from apps.exporter.archive import build_package
from apps.exporter.engine import export_report


def _staff_only(view):
    """Отчёты кафедры (с персональными данными всех сотрудников) — только
    для сотрудников кафедры; преподавателя отправляем в его кабинет."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect("portal:index")
        return view(request, *args, **kwargs)

    return wrapped


@_staff_only
def _my_periods(request):
    return ReportingPeriod.objects.filter(department__in=managed_departments(request.user))


@_staff_only
def index(request):
    periods = (
        _my_periods(request).select_related("department")
        .annotate(
            publications_count=Count("publications", distinct=True),
            files_count=Count("publications", filter=~Q(publications__article_file=""), distinct=True),
        )
        .order_by("-period_date")[:100]
    )
    return render(request, "dashboard/index.html", {
        "periods": periods,
        "no_department": not managed_departments(request.user).exists(),
    })


@_staff_only
def download_report(request, period_id):
    period = get_object_or_404(_my_periods(request).select_related("department"), pk=period_id)
    try:
        path, filled, skipped = export_report(period.department, period)
    except FileNotFoundError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


@_staff_only
def download_package(request, period_id):
    """Один ZIP: рейтинговая таблица + реестр документов + подтверждающие файлы
    (дипломы, статьи, патенты, договоры) по папкам преподавателей и листов."""
    period = get_object_or_404(_my_periods(request).select_related("department"), pk=period_id)
    try:
        archive, filename = build_package(period.department, period)
    except FileNotFoundError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(archive, as_attachment=True, filename=filename, content_type="application/zip")


@login_required
def home(request):
    """Сотрудника кафедры — к отчётам, преподавателя — в его кабинет."""
    if request.user.is_staff:
        return redirect("dashboard:index")
    return redirect("portal:index")


def _degree_column(snap):
    """1,1-jadvaldagi qaysi ustunlar guruhiga tushishini aniqlaydi:
    akademik / dsc (DSc, fan doktori yoki professor) / phd (PhD, fan nomzodi yoki dotsent)."""
    if not snap:
        return None
    degree = f"{snap.academic_degree.code} {snap.academic_degree.name}".lower() if snap.academic_degree else ""
    title = snap.academic_title.name.lower() if snap.academic_title else ""
    if "akademik" in degree:
        return "akademik"
    if "dsc" in degree or "doktori" in degree or "professor" in title:
        return "dsc"
    if "phd" in degree or "nomzod" in degree or "dotsent" in title:
        return "phd"
    return None


@login_required
def teachers(request):
    """1,1-jadval: ilmiy daraja (unvon)ga ega professor-o'qituvchilar ulushi,
    kafedralar bo'yicha. Daraja/unvon va bandlik turi o'qituvchining eng
    so'nggi davr snimkasidan (TeacherPeriodSnapshot) olinadi."""
    if not request.user.is_staff:
        return redirect("portal:index")

    my_departments = managed_departments(request.user).order_by("name")
    departments = my_departments
    selected = request.GET.get("kafedra")
    if selected and selected.isdigit():
        departments = departments.filter(pk=selected)

    teacher_qs = Teacher.objects.filter(is_active=True).order_by("full_name")
    snapshot_qs = (TeacherPeriodSnapshot.objects
                   .select_related("employment_type", "academic_degree", "academic_title")
                   .order_by("-reporting_period__period_date", "-id"))

    blocks = []
    for dept in departments.prefetch_related(
            Prefetch("teachers", queryset=teacher_qs.prefetch_related(
                Prefetch("period_snapshots", queryset=snapshot_qs, to_attr="snaps")))):
        main, ichki = [], []
        totals = {"akademik": 0, "dsc": 0, "phd": 0}
        for t in dept.teachers.all():
            snap = t.snaps[0] if t.snaps else None
            column = _degree_column(snap)
            if column:
                totals[column] += 1
            order = t.hire_order_number
            if order and t.hire_order_date:
                order = f"{order.rstrip(', ')}, {t.hire_order_date:%d.%m.%Y}"
            row = {"teacher": t, "column": column, "order": order}
            if snap and snap.employment_type.code == "ichki_orindosh":
                ichki.append(row)
            else:
                main.append(row)
        blocks.append({"department": dept, "main": main, "ichki": ichki, "totals": totals,
                       "count": len(main) + len(ichki)})

    return render(request, "dashboard/teachers.html", {
        "blocks": blocks,
        "all_departments": my_departments,
        "selected": selected,
    })
