from django.urls import path

from . import views

app_name = "analytics"

# /statistika/ — saytning oddiy sahifasi (reyting kabi), admin va kafedra mudirlari uchun
urlpatterns = [
    path("", views.statistika, name="statistika"),
    path("taqdimot/", views.taqdimot, name="taqdimot"),
]
