from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/", views.profile, name="profile"),
    path("patents/", views.patents_list, name="patents_list"),
    path("patents/add/", views.patents_form, name="patents_add"),
    path("patents/<int:pk>/edit/", views.patents_form, name="patents_edit"),
    path("<slug:slug>/", views.generic_list, name="list"),
    path("<slug:slug>/add/", views.generic_form, name="add"),
    path("<slug:slug>/<int:pk>/edit/", views.generic_form, name="edit"),
]
