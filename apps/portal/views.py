from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.exporter import personal
from apps.reports.models import Patent, PatentAuthor
from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod
from .forms import PatentSelfForm, TeacherProfileForm
from .registry import REGISTRY


def _teacher_or_none(request):
    return getattr(request.user, "teacher_profile", None)


def _require_teacher(view):
    """Пускает только пользователей, у которых есть привязанная карточка
    Teacher (её создаёт кафедра действием «Создать логин» в admin)."""

    @login_required
    def wrapped(request, *args, **kwargs):
        teacher = _teacher_or_none(request)
        if teacher is None:
            messages.error(
                request,
                _("Hisobingizga o‘qituvchi kartochkasi biriktirilmagan. Kafedra mudiriga murojaat qiling."),
            )
            return render(request, "portal/no_profile.html", status=403)
        request.teacher = teacher
        return view(request, *args, **kwargs)

    return wrapped


def _indicator_counts(teacher):
    counts = {}
    for slug, cfg in REGISTRY.items():
        counts[slug] = {
            "title": cfg["title"],
            "count": cfg["model"].objects.filter(**{cfg["teacher_field"]: teacher}).count(),
        }
    counts["patents"] = {
        "title": _("Patentlar"),
        "count": Patent.objects.filter(patentauthor__teacher=teacher).distinct().count(),
    }
    return counts


@_require_teacher
def index(request):
    teacher = request.teacher
    periods = ReportingPeriod.objects.filter(department=teacher.department).order_by("-period_date")
    return render(request, "portal/index.html", {
        "teacher": teacher, "counts": _indicator_counts(teacher), "periods": periods,
    })


@_require_teacher
def profile(request):
    """Все данные преподавателя на одной странице: карточка (кафедра, логин),
    кадровые данные из последнего снимка штатной ведомости, диплом и приказ,
    история по периодам — плюс форма для полей, которые преподаватель
    заполняет сам."""
    teacher = (Teacher.objects
               .select_related("department__faculty__university", "user")
               .get(pk=request.teacher.pk))
    if request.method == "POST":
        form = TeacherProfileForm(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, _("Profil ma’lumotlari saqlandi."))
            return redirect("portal:profile")
    else:
        form = TeacherProfileForm(instance=teacher)

    snapshots = list(teacher.period_snapshots
                     .select_related("reporting_period", "employment_type", "position",
                                     "academic_degree", "academic_title")
                     .order_by("-reporting_period__period_date", "-id"))
    return render(request, "portal/profile.html", {
        "teacher": teacher,
        "form": form,
        "snapshot": snapshots[0] if snapshots else None,
        "snapshots": snapshots,
    })


def _report_period(request):
    """Davrlar ro'yxati va tanlangan davr (?davr=<id>; yo'q — barcha davrlar)."""
    periods = personal.teacher_periods(request.teacher)
    davr = request.GET.get("davr")
    period = periods.filter(pk=davr).first() if davr and davr.isdigit() else None
    return periods, period


@_require_teacher
def report(request):
    """Mening hisobotim: kiritilgan maqolalar va ilmiy ishlar bo'yicha jamlanma
    va ularni fayllari bilan bitta ZIP qilib yuklab olish."""
    periods, period = _report_period(request)
    return render(request, "portal/report.html", {
        "teacher": request.teacher, "periods": periods, "period": period,
        "rows": personal.summary(request.teacher, period),
    })


@_require_teacher
def report_zip(request):
    _periods, period = _report_period(request)
    archive, filename = personal.build_teacher_package(request.teacher, period)
    return FileResponse(archive, as_attachment=True, filename=filename, content_type="application/zip")


@_require_teacher
def generic_list(request, slug):
    cfg = REGISTRY.get(slug)
    if cfg is None:
        raise Http404
    qs = cfg["model"].objects.filter(**{cfg["teacher_field"]: request.teacher}).order_by("-id")
    return render(request, "portal/list.html", {
        "cfg": cfg, "slug": slug, "objects": qs,
    })


@_require_teacher
def generic_form(request, slug, pk=None):
    cfg = REGISTRY.get(slug)
    if cfg is None:
        raise Http404
    teacher = request.teacher

    FormClass = modelform_factory(
        cfg["model"], fields=cfg["fields"],
        widgets={"reporting_period": django_forms.Select},
    )
    # преподаватель работает только со своими периодами своей кафедры
    period_qs = ReportingPeriod.objects.filter(department=teacher.department)

    instance = None
    if pk is not None:
        qs = cfg["model"].objects.filter(**{cfg["teacher_field"]: teacher})
        instance = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, instance=instance)
        form.fields["reporting_period"].queryset = period_qs
        if form.is_valid():
            obj = form.save(commit=False)
            setattr(obj, cfg["teacher_field"], teacher)
            # преподаватель изменил число соавторов — завкафедрой должен проверить заново
            if "department_co_authors_count" in form.changed_data:
                obj.co_authors_checked = False
            # поле преподавателя не входит в форму, поэтому unique_together
            # (напр. один h-индекс на период) проверяем сами, а не ловим IntegrityError
            try:
                obj.validate_unique()
            except ValidationError:
                form.add_error("reporting_period", _("Bu davr uchun yozuv allaqachon bor — uni ochib o‘zgartiring."))
            else:
                obj.save()
                messages.success(request, _("Saqlandi."))
                return redirect("portal:list", slug=slug)
    else:
        form = FormClass(instance=instance)
        form.fields["reporting_period"].queryset = period_qs

    return render(request, "portal/form.html", {"form": form, "title": cfg["title"], "slug": slug})


@_require_teacher
def patents_list(request):
    teacher = request.teacher
    objects = Patent.objects.filter(patentauthor__teacher=teacher).distinct().order_by("-id")
    return render(request, "portal/patents_list.html", {"objects": objects})


@_require_teacher
def patents_form(request, pk=None):
    teacher = request.teacher
    period_qs = ReportingPeriod.objects.filter(department=teacher.department)

    instance = None
    if pk is not None:
        instance = get_object_or_404(
            Patent.objects.filter(patentauthor__teacher=teacher).distinct(), pk=pk,
        )

    if request.method == "POST":
        form = PatentSelfForm(request.POST, request.FILES, instance=instance)
        form.fields["reporting_period"].queryset = period_qs
        if form.is_valid():
            patent = form.save()
            PatentAuthor.objects.get_or_create(patent=patent, teacher=teacher)
            messages.success(request, _("Saqlandi."))
            return redirect("portal:patents_list")
    else:
        form = PatentSelfForm(instance=instance)
        form.fields["reporting_period"].queryset = period_qs

    return render(request, "portal/form.html", {"form": form, "title": _("Patent")})
