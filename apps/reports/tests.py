"""
Число соавторов-сотрудников кафедры (доля 1/N): преподаватель вводит,
завкафедрой проверяет и исправляет.
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from apps.core.models import Department, Faculty, University
from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod
from .models import Publication

User = get_user_model()

# admin-страницы ссылаются на static; в тестах collectstatic не делается,
# поэтому — хранилище без манифеста
PLAIN_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=PLAIN_STATIC)
class CoAuthorsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        uni = University.objects.create(name="Test universiteti")
        fac = Faculty.objects.create(university=uni, name="Test fakulteti")
        cls.dep = Department.objects.create(faculty=fac, name="Test kafedrasi", short_name="TK")
        cls.period = ReportingPeriod.objects.create(
            department=cls.dep, period_label="2026-mart", period_date=datetime.date(2026, 3, 31),
        )
        # завкафедрой — сотрудник (is_staff) с карточкой преподавателя своей кафедры
        cls.head_user = User.objects.create_user("mudir", password="pass-12345-test", is_staff=True)
        cls.head_user.user_permissions.set(Permission.objects.filter(
            content_type__app_label="reports", codename__in=["view_publication", "change_publication"]))
        Teacher.objects.create(department=cls.dep, full_name="Mudir Mudirov", user=cls.head_user)

        cls.teacher_user = User.objects.create_user("oqituvchi", password="pass-12345-test")
        cls.teacher = Teacher.objects.create(department=cls.dep, full_name="Aliyev Ali", user=cls.teacher_user)

    def setUp(self):
        self.pub = Publication.objects.create(
            teacher=self.teacher, reporting_period=self.period, article_title="Maqola",
            quartile="Q1", department_co_authors_count=2,
        )

    def admin_form_data(self, **overrides):
        data = {
            "teacher": self.teacher.pk, "reporting_period": self.period.pk, "indexing": "scopus",
            "journal_name": "", "publish_year": "", "publish_month": "", "article_title": "Maqola",
            "language": "", "scopus_url": "", "quartile": "Q1", "citation_tier": "", "citations_count": 0,
            "department_co_authors_count": 2, "_save": "Saqlash",
        }
        data.update(overrides)
        return data

    def test_share_is_one_over_n(self):
        self.assertEqual(self.pub.share, Decimal("0.5"))
        self.pub.department_co_authors_count = 3
        self.assertEqual(round(self.pub.share, 2), Decimal("0.33"))

    def test_head_corrects_number_and_it_becomes_checked(self):
        self.client.login(username="mudir", password="pass-12345-test")
        url = f"/admin/reports/publication/{self.pub.pk}/change/"
        response = self.client.post(url, self.admin_form_data(department_co_authors_count=3))
        self.assertEqual(response.status_code, 302)
        self.pub.refresh_from_db()
        self.assertEqual(self.pub.department_co_authors_count, 3)
        self.assertTrue(self.pub.co_authors_checked)

        changelist = self.client.get("/admin/reports/publication/")
        self.assertContains(changelist, "0.33")

    def test_head_confirms_in_bulk(self):
        self.client.login(username="mudir", password="pass-12345-test")
        self.client.post("/admin/reports/publication/", {
            "action": "mark_co_authors_checked", "_selected_action": [self.pub.pk],
        })
        self.pub.refresh_from_db()
        self.assertTrue(self.pub.co_authors_checked)

    def teacher_post(self, count):
        return self.client.post(f"/kabinet/publications/{self.pub.pk}/edit/", {
            "reporting_period": self.period.pk, "indexing": "scopus", "article_title": "Maqola",
            "quartile": "Q1", "citation_tier": "", "citations_count": 0,
            "department_co_authors_count": count,
        })

    def test_teacher_change_resets_check(self):
        Publication.objects.filter(pk=self.pub.pk).update(co_authors_checked=True)
        self.client.login(username="oqituvchi", password="pass-12345-test")

        self.teacher_post(2)                                   # число не менялось — отметка остаётся
        self.pub.refresh_from_db()
        self.assertTrue(self.pub.co_authors_checked)

        self.teacher_post(4)
        self.pub.refresh_from_db()
        self.assertEqual(self.pub.department_co_authors_count, 4)
        self.assertFalse(self.pub.co_authors_checked)

        listing = self.client.get("/kabinet/publications/")
        self.assertContains(listing, "0.25")

    def test_zero_co_authors_rejected(self):
        self.client.login(username="oqituvchi", password="pass-12345-test")
        response = self.teacher_post(0)
        self.assertEqual(response.status_code, 200)            # форма с ошибкой, не редирект
        self.pub.refresh_from_db()
        self.assertEqual(self.pub.department_co_authors_count, 2)
