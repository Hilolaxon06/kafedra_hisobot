from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("hisobot/", views.index, name="index"),
    path("oqituvchilar/", views.teachers, name="teachers"),
    path("periods/<int:period_id>/download/", views.download_report, name="download_report"),
    path("periods/<int:period_id>/package/", views.download_package, name="download_package"),
]
