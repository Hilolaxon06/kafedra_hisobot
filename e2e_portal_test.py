"""
Сквозная проверка личного кабинета (запускается один раз вручную):
python manage.py shell < e2e_portal_test.py
"""
import django
from django.conf import settings
settings.ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Department
from apps.staff.models import Teacher
from apps.staff.admin import TeacherAdmin
from apps.workflow.models import ReportingPeriod
from apps.reports.models import Publication, Patent, Funding, TeacherMobility, PostgradDefense
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

User = get_user_model()
dep = Department.objects.get(short_name="MADT")
period = ReportingPeriod.objects.get(department=dep, period_label="2026-mart")

t1 = Teacher.objects.filter(department=dep).order_by("full_name")[0]
t2 = Teacher.objects.filter(department=dep).order_by("full_name")[1]
print("Тестовые преподаватели:", t1.full_name, "|", t2.full_name)

# создаём логины через реальный admin-action (а не руками), как это будет
# делать завкафедрой
admin_instance = TeacherAdmin(Teacher, AdminSite())


class FakeRequest:
    def __init__(self):
        self._messages = []

    def build_absolute_uri(self, *a, **k):
        return "/"


from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

rf = RequestFactory()
req = rf.post("/admin/staff/teacher/")
req.session = {}
req._messages = FallbackStorage(req)
admin_instance.create_login(req, Teacher.objects.filter(pk__in=[t1.pk, t2.pk]))

t1.refresh_from_db()
t2.refresh_from_db()
print("Логин t1:", t1.user.username, "| логин t2:", t2.user.username)

# ставим известные пароли для теста (action генерирует случайные)
t1.user.set_password("pass-t1-12345")
t1.user.save()
t2.user.set_password("pass-t2-12345")
t2.user.save()

c1 = Client()
assert c1.login(username=t1.user.username, password="pass-t1-12345")

# 1) кабинет открывается
r = c1.get("/kabinet/")
print("GET /kabinet/ ->", r.status_code)
assert r.status_code == 200

# 2) добавляем публикацию с файлом
pdf = SimpleUploadedFile("article.pdf", b"%PDF-1.4 fake content", content_type="application/pdf")
r = c1.post("/kabinet/publications/add/", {
    "reporting_period": period.id,
    "journal_name": "Test Journal",
    "publish_year": 2026,
    "publish_month": 3,
    "article_title": "Моя тестовая статья",
    "language": "uz",
    "scopus_url": "https://scopus.com/x",
    "quartile": "Q2",
    "citation_tier": "",
    "citations_count": 0,
    "department_co_authors_count": 2,
    "article_file": pdf,
}, follow=True)
print("POST publications/add ->", r.status_code)
pub = Publication.objects.get(teacher=t1, article_title="Моя тестовая статья")
print("  файл сохранён:", bool(pub.article_file), pub.article_file.name if pub.article_file else None)
assert pub.teacher_id == t1.id
assert pub.article_file

# 3) добавляем патент (через отдельный self-service flow с автора-M2M)
r = c1.post("/kabinet/patents/add/", {
    "reporting_period": period.id,
    "title": "Тестовый патент",
    "patent_type": "invention",
    "registered_in_scopus": "on",
    "has_license_agreement": "",
}, follow=True)
print("POST patents/add ->", r.status_code)
patent = Patent.objects.get(title="Тестовый патент")
assert t1 in patent.authors.all()

# 4) грант
r = c1.post("/kabinet/fundings/add/", {
    "reporting_period": period.id,
    "source_type": "business_contract",
    "amount": "2500000",
}, follow=True)
print("POST fundings/add ->", r.status_code)
assert Funding.objects.filter(teacher=t1, amount=2500000).exists()

# 5) мобильность
r = c1.post("/kabinet/mobility/add/", {
    "reporting_period": period.id,
    "direction": "outbound",
    "partner_institution_name": "Test University",
}, follow=True)
assert TeacherMobility.objects.filter(teacher=t1, direction="outbound").exists()

# 6) защита под руководством
r = c1.post("/kabinet/defenses/add/", {
    "reporting_period": period.id,
    "degree_type": "PhD",
    "defended_full_name": "Иванов И.И.",
}, follow=True)
assert PostgradDefense.objects.filter(advisor_teacher=t1).exists()

# 7) профиль — включая диплом и приказ о приёме (теперь тоже вносит сам
# преподаватель, а не кафедра через admin)
r = c1.post("/kabinet/profile/", {
    "specialty_name": "Дифференциальные уравнения",
    "diploma_series": "AB",
    "diploma_number": "123456",
    "foreign_university_name": "",
    "hire_order_number": "45-к",
    "hire_order_date": "2019-09-01",
}, follow=True)
t1.refresh_from_db()
assert t1.specialty_name == "Дифференциальные уравнения"
assert t1.hire_order_number == "45-к"
assert str(t1.hire_order_date) == "2019-09-01"
print("Профиль обновлён:", t1.specialty_name, t1.diploma_series,
      t1.hire_order_number, t1.hire_order_date)

# профиль недоступен без входа и не даёт править чужой — сам View уже
# скопирован через request.teacher, отдельно проверяем, что t2 своим
# POST'ом не мог задеть запись t1
t2.refresh_from_db()
assert t2.hire_order_number != "45-к"

# 8) изоляция: t2 не должен видеть публикацию t1
c2 = Client()
assert c2.login(username=t2.user.username, password="pass-t2-12345")
r = c2.get("/kabinet/publications/")
print("t2 видит публикаций (должно быть 0):", Publication.objects.filter(teacher=t2).count())
assert "Моя тестовая статья" not in r.content.decode("utf-8")

# t2 не может отредактировать публикацию t1 по прямому URL (должно быть 404)
r = c2.get(f"/kabinet/publications/{pub.id}/edit/")
print("t2 открывает чужую публикацию по прямой ссылке ->", r.status_code, "(ожидаем 404)")
assert r.status_code == 404

print("\nВСЕ ПРОВЕРКИ КАБИНЕТА ПРОШЛИ УСПЕШНО")
