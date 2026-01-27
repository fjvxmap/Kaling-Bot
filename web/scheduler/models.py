from __future__ import annotations

from django.db import models


class Guild(models.Model):
    guild_id = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return f"{self.name} ({self.guild_id})"


class Member(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="members")
    user_id = models.CharField(max_length=32)
    display_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ("guild", "user_id")

    def __str__(self) -> str:
        return f"{self.display_name} ({self.user_id})"


class Schedule(models.Model):
    guild = models.ForeignKey(Guild, on_delete=models.CASCADE, related_name="schedules")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_by = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, related_name="created_schedules"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.title} ({self.start_time})"


class Availability(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        MAYBE = "maybe", "Maybe"
        UNAVAILABLE = "unavailable", "Unavailable"

    schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name="availabilities"
    )
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="availabilities"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("schedule", "member", "start_time", "end_time")

    def __str__(self) -> str:
        return f"{self.member} -> {self.status}"

