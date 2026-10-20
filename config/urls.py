from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

from apps.analytics import views as analytics_views
from apps.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("kabinet/", include("apps.portal.urls")),
    path("reyting/", analytics_views.reyting, name="reyting"),
    path("statistika/", include("apps.analytics.urls")),
    path("sozlamalar/", core_views.sozlamalar, name="sozlamalar"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("apps.dashboard.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

