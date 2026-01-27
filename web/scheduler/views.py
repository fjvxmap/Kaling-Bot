from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from .models import Availability, Schedule


@dataclass
class CalendarDay:
    day: date | None
    in_month: bool


def calendar_view(request):
    today = timezone.localdate()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    next_month = (last_day.replace(day=28) + timezone.timedelta(days=4)).replace(day=1)

    schedules = (
        Schedule.objects.filter(start_time__lt=next_month, end_time__gte=first_day)
        .select_related("guild", "created_by")
        .annotate(
            available_count=Count(
                "availabilities",
                filter=Q(availabilities__status=Availability.Status.AVAILABLE),
            ),
            maybe_count=Count(
                "availabilities",
                filter=Q(availabilities__status=Availability.Status.MAYBE),
            ),
            unavailable_count=Count(
                "availabilities",
                filter=Q(availabilities__status=Availability.Status.UNAVAILABLE),
            ),
        )
        .order_by("start_time")
    )

    cal = calendar.Calendar(firstweekday=0)
    weeks: list[list[CalendarDay]] = []
    for week in cal.monthdatescalendar(year, month):
        weeks.append(
            [
                CalendarDay(day=day, in_month=(day.month == month))
                for day in week
            ]
        )

    context = {
        "today": today,
        "month_label": datetime(year, month, 1).strftime("%B %Y"),
        "weeks": weeks,
        "schedules": schedules,
    }
    return render(request, "scheduler/calendar.html", context)

