from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from scheduler.views import discord_callback, discord_login, discord_logout

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/discord/", discord_login, name="discord_login"),
    path("auth/discord/callback/", discord_callback, name="discord_callback"),
    path("auth/discord/logout/", discord_logout, name="discord_logout"),
    path("", include("rpg_web.urls")),
]
