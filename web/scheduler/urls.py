from __future__ import annotations

from django.urls import path

from .views import calendar_view, discord_callback, discord_login, discord_logout

urlpatterns = [
    path("", calendar_view, name="calendar"),
    path("auth/discord/", discord_login, name="discord_login"),
    path("auth/discord/callback/", discord_callback, name="discord_callback"),
    path("auth/discord/logout/", discord_logout, name="discord_logout"),
]
