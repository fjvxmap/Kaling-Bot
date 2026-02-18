from __future__ import annotations

from django.contrib import admin

from .models import Availability, Guild, Member, Schedule


@admin.register(Guild)
class GuildAdmin(admin.ModelAdmin):
    list_display = ("name", "guild_id")
    search_fields = ("name", "guild_id")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user_id", "guild")
    search_fields = ("display_name", "user_id")
    list_filter = ("guild",)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("title", "guild", "start_time", "end_time")
    list_filter = ("guild",)


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("member", "schedule", "status", "start_time", "end_time")
    list_filter = ("status", "schedule")
    actions = ("clear_all_availability",)

    @admin.action(description="Delete all availability entries")
    def clear_all_availability(self, request, queryset) -> None:
        Availability.objects.all().delete()
