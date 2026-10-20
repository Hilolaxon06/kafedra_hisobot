"""
Настройки проекта «Кафедра — хисобот».

Архитектура намеренно разбита на отдельные Django-приложения (apps/*),
каждое отвечает за один слой схемы данных:

- core          — университет / факультет / кафедра
- dictionaries  — справочники (должности, степени, звания, страны и т.п.)
- staff         — преподаватели и их посрочные снимки статуса (штатная ведомость)
- students      — студенты и выпускники
- workflow      — отчётные периоды и их статус согласования
- reports       — все факт-таблицы показателей (публикации, патенты, гранты...)
- exporter      — генерация исходного .xlsx-отчёта по данным периода
- dashboard     — минимальный веб-интерфейс поверх admin (список периодов + экспорт)
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY", default="dev-insecure-secret-key")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1, 192.168.137.1", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "import_export",

    "apps.core",
    "apps.dictionaries",
    "apps.staff",
    "apps.students",
    "apps.workflow",
    "apps.reports",
    "apps.exporter",
    "apps.dashboard",
    "apps.portal",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# База данных: MySQL в проде, SQLite — для быстрого локального запуска и тестов
# (DB_ENGINE=sqlite в .env). Схема одинакова для обоих движков.
# ---------------------------------------------------------------------------
if config("DB_ENGINE", default="sqlite") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="3306"),
            "OPTIONS": {"charset": "utf8mb4"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Interfeys tillari: o'zbek (asosiy), rus, ingliz. Foydalanuvchi tilni
# /sozlamalar/ sahifasida tanlaydi (cookie). Tarjimalar — locale/*/django.po,
# yangilash va kompilyatsiya: python scripts/i18n.py --compile
LANGUAGE_CODE = config("LANGUAGE_CODE", default="uz")
LANGUAGES = [
    ("uz", "O‘zbekcha"),
    ("ru", "Русский"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = config("TIME_ZONE", default="Asia/Tashkent")
USE_I18N = True
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Куда exporter кладёт сгенерированные .xlsx перед отдачей пользователю
EXPORTS_DIR = BASE_DIR / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
