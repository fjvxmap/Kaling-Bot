from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="rpg_home"),
    path("api/bootstrap/", views.bootstrap, name="rpg_bootstrap"),
    path("api/action/", views.action, name="rpg_action"),
]
