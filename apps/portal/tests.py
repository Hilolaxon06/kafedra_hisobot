"""
Личный кабинет: преподаватель вносит свои записи и не видит чужие.
Тот же сценарий, что в e2e_portal_test.py, но на своих данных (без seed).
"""

import datetime
import shutil
import tempfile

from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings

from apps.core.models import Department, Faculty, University
from apps.reports.models import Funding, Patent, PostgradDefense, Publication, TeacherMobility
from apps.staff.admin import TeacherAdmin
from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod

MEDIA = tempfile.mkdtemp(prefix="kafedra_test_media_")


@override_settings(MEDIA_ROOT=MEDIA)
class PortalIsolationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        uni = University.objects.create(name="Test universiteti")
        fac = Faculty.objects.create(university=uni, name="Test fakulteti")
        cls.dep = Department.objects.create(faculty=fac, name="Test kafedrasi", short_name="TK")
        cls.period = ReportingPeriod.objects.create(
            department=cls.dep, period_label="2026-mart", period_date=datetime.date(2026, 3, 31),
        )
        cls.t1 = Teacher.objects.create(department=cls.dep, full_name="Aliyev Ali")
        cls.t2 = Teacher.objects.create(department=cls.dep, full_name="Boboyev Bobur")

        # логины — через тот же admin-action, которым пользуется завкафедрой
        request = RequestFactory().post("/admin/staff/teacher/")
        request.session = {}
        request._messages = FallbackStorage(request)
        TeacherAdmin(Teacher, AdminSite()).create_login(
            request, Teacher.objects.filter(pk__in=[cls.t1.pk, cls.t2.pk]))
        for teacher in (cls.t1, cls.t2):
            teacher.refresh_from_db()
            teacher.user.set_password("pass-12345-test")
            teacher.user.save()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def login(self, teacher):
        self.assertTrue(self.client.login(username=teacher.user.username, password="pass-12345-test"))

    def test_teacher_adds_own_records_and_cannot_see_others(self):
        self.login(self.t1)
        self.assertEqual(self.client.get("/kabinet/").status_code, 200)

        pdf = SimpleUploadedFile("article.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        self.client.post("/kabinet/publications/add/", {
            "reporting_period": self.period.id,
            "indexing": "scopus",
            "journal_name": "Test Journal",
            "publish_year": 2026,
            "publish_month": 3,
            "article_title": "Moy test maqolasi",
            "language": "uz",
            "scopus_url": "https://scopus.com/x",
            "quartile": "Q2",
            "citation_tier": "",
            "citations_count": 0,
            "department_co_authors_count": 2,
            "article_file": pdf,
        })
        pub = Publication.objects.get(teacher=self.t1, article_title="Moy test maqolasi")
        self.assertTrue(pub.article_file)

        self.client.post("/kabinet/patents/add/", {
            "reporting_period": self.period.id,
            "title": "Test patenti",
            "patent_type": "invention",
            "registered_in_scopus": "on",
        })
        self.assertIn(self.t1, Patent.objects.get(title="Test patenti").authors.all())

        self.client.post("/kabinet/fundings/add/", {
            "reporting_period": self.period.id, "source_type": "business_contract", "amount": "2500000",
        })
        self.assertTrue(Funding.objects.filter(teacher=self.t1, amount=2500000).exists())

        self.client.post("/kabinet/mobility/add/", {
            "reporting_period": self.period.id, "direction": "outbound",
            "partner_institution_name": "Test University",
        })
        self.assertTrue(TeacherMobility.objects.filter(teacher=self.t1, direction="outbound").exists())

        self.client.post("/kabinet/defenses/add/", {
            "reporting_period": self.period.id, "degree_type": "PhD", "defended_full_name": "Ivanov I.I.",
        })
        self.assertTrue(PostgradDefense.objects.filter(advisor_teacher=self.t1).exists())

        self.client.post("/kabinet/profile/", {
            "specialty_name": "Differensial tenglamalar",
            "diploma_series": "AB",
            "diploma_number": "123456",
            "foreign_university_name": "",
            "hire_order_number": "45-k",
            "hire_order_date": "2019-09-01",
        })
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.hire_order_number, "45-k")
        self.assertEqual(self.t1.hire_order_date, datetime.date(2019, 9, 1))
        self.t2.refresh_from_db()
        self.assertNotEqual(self.t2.hire_order_number, "45-k")

        # второй преподаватель не видит и не открывает чужое
        self.client.logout()
        self.login(self.t2)
        response = self.client.get("/kabinet/publications/")
        self.assertNotContains(response, "Moy test maqolasi")
        self.assertEqual(self.client.get(f"/kabinet/publications/{pub.id}/edit/").status_code, 404)
        self.assertNotContains(self.client.get("/kabinet/patents/"), "Test patenti")
