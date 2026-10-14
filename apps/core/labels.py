"""
Понятные узбекские названия разделов админки для завкафедрой — общие для
главной страницы админки (templatetags/kafedra_admin.py), левого меню и
таблицы прав группы (permissions.py).
"""

# app_label.model_name -> (раздел, название, описание, иконка)
MODELS = {
    "staff.teacher": ("staff", "O‘qituvchilar", "Kafedra professor-o‘qituvchilari, ularga kabinet uchun login yaratish", "users"),
    "staff.teacherperiodsnapshot": ("staff", "Shtat jadvali", "Har bir davr uchun lavozim, stavka, ilmiy daraja va unvon", "table"),

    "reports.publication": ("science", "Maqolalar", "Scopus, Web of Science, OAK jurnallari va boshqa maqolalar", "doc"),
    "reports.teacherhindex": ("science", "H-indeks", "O‘qituvchilarning Hirsh indeksi (davr bo‘yicha)", "chart"),
    "reports.patent": ("science", "Patentlar", "Ixtiro, foydali model, sanoat namunalari", "award"),
    "reports.patentauthor": ("science", "Patent mualliflari", "Patent va o‘qituvchi bog‘lanishi", "users"),
    "reports.funding": ("science", "Jalb qilingan mablag‘lar", "Grantlar, xo‘jalik shartnomalari, xorijiy mablag‘lar", "money"),
    "reports.postgraddefense": ("science", "Dissertatsiya himoyalari", "Ilmiy rahbarligida himoya qilingan PhD / DSc", "cap"),
    "reports.reputationvote": ("science", "Xalqaro obro‘ ovozlari", "THE / QS / ARWU ekspertlari va hamkorlar ovozlari", "star"),
    "reports.teachermobility": ("science", "O‘qituvchilar mobilligi", "Xorijiy OTMlarga chiqish va kelish", "plane"),

    "students.student": ("students", "Talabalar", "Kafedra talabalari ro‘yxati", "cap"),
    "students.graduate": ("students", "Bitiruvchilar", "Bitiruvchilar ro‘yxati", "users"),
    "reports.studentmobility": ("students", "Talabalar mobilligi", "Almashinuv va qo‘shma dasturlar", "plane"),
    "reports.graduateemployment": ("students", "Bitiruvchilar bandligi", "Ishga joylashish va o‘rtacha daromad", "brief"),

    "workflow.reportingperiod": ("periods", "Hisobot davrlari", "Davr yaratish, tasdiqlashga yuborish", "calendar"),

    "core.department": ("refs", "Kafedra", "Kafedra nomi va fakulteti", "home"),
    "core.faculty": ("refs", "Fakultetlar", "", "home"),
    "core.university": ("refs", "Universitet", "", "home"),
    "dictionaries.employmenttype": ("refs", "Bandlik turlari", "Asosiy, o‘rindosh va h.k.", "list"),
    "dictionaries.position": ("refs", "Lavozimlar", "", "list"),
    "dictionaries.academicdegree": ("refs", "Ilmiy darajalar", "", "list"),
    "dictionaries.academictitle": ("refs", "Ilmiy unvonlar", "", "list"),
    "dictionaries.country": ("refs", "Davlatlar", "", "list"),
    "reports.nationalavgsalary": ("refs", "O‘rtacha ish haqi (Davstat)", "", "money"),
    "reports.indicatorvalue": ("refs", "Qo‘shimcha ko‘rsatkichlar", "Hali alohida jadvali yo‘q ko‘rsatkichlar", "list"),

    "auth.user": ("system", "Foydalanuvchilar", "Loginlar va parollar", "key"),
    "auth.group": ("system", "Guruhlar va huquqlar", "Kim nimani ko‘ra va o‘zgartira oladi", "key"),
}

SECTIONS = [
    ("staff", "Kadrlar", "Avval o‘qituvchilarni va ularning shtat ma’lumotlarini kiriting"),
    ("periods", "Hisobot davrlari", "Har bir hisobot shu davrlarga bog‘lanadi"),
    ("science", "Ilmiy ko‘rsatkichlar", "O‘qituvchilar kabinetda kiritgan ma’lumotlarni shu yerda tekshirasiz"),
    ("students", "Talabalar va bitiruvchilar", ""),
    ("refs", "Ma’lumotnomalar", "Odatda o‘zgartirish shart emas"),
    ("system", "Tizim", ""),
    ("other", "Boshqa", ""),
]

APP_NAMES = {
    "staff": "Kadrlar",
    "workflow": "Hisobot davrlari",
    "reports": "Ko‘rsatkichlar",
    "students": "Talabalar va bitiruvchilar",
    "dictionaries": "Ma’lumotnomalar",
    "core": "Tuzilma: OTM / fakultet / kafedra",
    "auth": "Foydalanuvchilar va guruhlar",
}
