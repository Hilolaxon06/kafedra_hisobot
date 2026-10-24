"""
Statistika va reyting: hammualliflik ulushi, patent balli, ma'lumot xatolari
haqida ogohlantirish va sahifalar ochilishi.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.core.models import Department, Faculty, University
from apps.reports.models import Patent, PatentAuthor, Publication, TeacherHIndex
from apps.staff.models import Teacher
from apps.workflow.models import ReportingPeriod
from . import stats

User = get_user_model()

PLAIN_STATIC = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=PLAIN_STATIC)
class StatsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        uni = University.objects.create(name="Test universiteti")
        fac = Faculty.objects.create(university=uni, name="Test fakulteti")
        cls.dep = Department.objects.create(faculty=fac, name="Birinchi kafedra")
        cls.other = Department.objects.create(faculty=fac, name="Ikkinchi kafedra")
        cls.period = ReportingPeriod.objects.create(
            department=cls.dep, period_label="2026-mart", period_date=datetime.date(2026, 3, 31))
        cls.other_period = ReportingPeriod.objects.create(
            department=cls.other, period_label="2026-mart", period_date=datetime.date(2026, 3, 31))
        cls.ali = Teacher.objects.create(department=cls.dep, full_name="Aliyev Ali")
        cls.vali = Teacher.objects.create(department=cls.dep, full_name="Valiyev Vali")

        head = User.objects.create_user("mudir", password="pass-12345-test", is_staff=True)
        Teacher.objects.create(department=cls.dep, full_name="Mudir Mudirov", user=head)
        User.objects.create_superuser("admin", password="pass-12345-test")

    def pub(self, teacher, title, n=1, **extra):
        return Publication.objects.create(
            teacher=teacher, reporting_period=self.period, article_title=title,
            quartile="Q1", department_co_authors_count=n, **extra)

    def test_same_article_by_two_teachers_counts_once(self):
        # ikkalasi ham N=1 deb kiritgan — maqola kafedraga 2 emas, 1 marta hisoblanadi
        self.pub(self.ali, "Bir  Maqola")
        self.pub(self.vali, "bir maqola")
        data = stats.department_year(self.dep, 2026)
        self.assertEqual(data["publications"], 1.0)
        self.assertEqual(data["quartiles"]["Q1"], 1.0)
        warnings = stats.data_warnings(Department.objects.filter(pk=self.dep.pk), 2026)
        self.assertEqual(len(warnings["coauthors"]), 2)

    def test_correct_n_gives_no_warning(self):
        self.pub(self.ali, "Maqola", n=2)
        self.pub(self.vali, "Maqola", n=2)
        self.pub(self.ali, "Boshqa maqola", n=3)       # qolgan hammualliflar hali kiritmagan — normal
        data = stats.department_year(self.dep, 2026)
        self.assertEqual(data["publications"], 1.33)
        self.assertEqual(stats.data_warnings(Department.objects.filter(pk=self.dep.pk), 2026)["coauthors"], [])

    def test_certificates_score_only_with_license(self):
        for ptype, licensed in [(Patent.PatentType.INVENTION, False),
                                (Patent.PatentType.SOFTWARE_CERTIFICATE, False),
                                (Patent.PatentType.DATABASE_CERTIFICATE, True)]:
            patent = Patent.objects.create(reporting_period=self.period, patent_type=ptype,
                                           has_license_agreement=licensed)
            PatentAuthor.objects.create(patent=patent, teacher=self.ali)
        data = stats.department_year(self.dep, 2026)
        self.assertEqual(data["patents"], 2)
        self.assertEqual(sum(data["patent_types"].values()), 3)   # diagrammada hammasi
        self.assertEqual(data["score_parts"]["Patentlar"], 10.0)

    def test_record_in_other_department_period(self):
        # eski xato yozuv (validatsiyadan oldin kiritilgan) — ogohlantirishda ko'rinadi
        TeacherHIndex.objects.create(teacher=self.ali, reporting_period=self.other_period, h_index=6)
        warnings = stats.data_warnings(Department.objects.filter(pk=self.dep.pk), 2026)
        self.assertEqual(len(warnings["misfiled"]), 1)
        self.assertEqual(warnings["misfiled"][0]["teacher"], self.ali)

        # yangisini endi kiritib bo'lmaydi
        record = TeacherHIndex(teacher=self.vali, reporting_period=self.other_period, h_index=3)
        with self.assertRaises(ValidationError):
            record.full_clean()

    def test_pages_open(self):
        self.pub(self.ali, "Maqola")
        self.pub(self.vali, "Maqola")
        for username in ("mudir", "admin"):
            self.client.login(username=username, password="pass-12345-test")
            for url in ("/statistika/", "/statistika/?yil=2026", "/reyting/", "/statistika/taqdimot/"):
                self.assertEqual(self.client.get(url).status_code, 200, (username, url))
            page = self.client.get("/statistika/")
            self.assertContains(page, "kh-warn")
