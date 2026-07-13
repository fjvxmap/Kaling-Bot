from __future__ import annotations

import json
import os
import secrets
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

import requests
from django.shortcuts import render
from django.utils import timezone
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from .models import Availability, Guild, Member, Schedule


def _week_start(anchor: date, start_weekday: int = 3) -> date:
    delta = (anchor.weekday() - start_weekday) % 7
    return anchor - timedelta(days=delta)


def _ensure_week_schedule(week_start: date) -> Schedule:
    tz = timezone.get_current_timezone()
    schedule_start = timezone.make_aware(datetime.combine(week_start, time(0, 0)), tz)
    schedule_end = schedule_start + timedelta(days=7)
    guild, _ = Guild.objects.get_or_create(
        guild_id="default", defaults={"name": "Default"}
    )
    schedule, _ = Schedule.objects.get_or_create(
        guild=guild,
        title=f"Weekly availability ({week_start.isoformat()})",
        defaults={
            "description": "Auto-created weekly availability board.",
            "start_time": schedule_start,
            "end_time": schedule_end,
            "created_by": None,
        },
    )
    return schedule


def _get_member(guild: Guild, user_id: str, display_name: str) -> Member:
    member, _ = Member.objects.get_or_create(
        guild=guild,
        user_id=user_id,
        defaults={"display_name": display_name},
    )
    if member.display_name != display_name:
        member.display_name = display_name
        member.save(update_fields=["display_name"])
    return member


def _get_discord_oauth_config() -> dict[str, str] | None:
    client_id = os.getenv("DISCORD_CLIENT_ID", "").strip()
    client_secret = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "").strip()
    if not client_id or not client_secret or not redirect_uri:
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def discord_login(request: HttpRequest) -> HttpResponse:
    config = _get_discord_oauth_config()
    if not config:
        return HttpResponse("Discord OAuth is not configured.", status=500)

    state = secrets.token_urlsafe(16)
    request.session["discord_oauth_state"] = state

    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": "identify",
        "state": state,
    }
    auth_url = "https://discord.com/oauth2/authorize"
    query = urlencode(params)
    return HttpResponseRedirect(f"{auth_url}?{query}")


def discord_callback(request: HttpRequest) -> HttpResponse:
    config = _get_discord_oauth_config()
    if not config:
        return HttpResponse("Discord OAuth is not configured.", status=500)

    state = request.GET.get("state")
    code = request.GET.get("code")
    if not code or state != request.session.get("discord_oauth_state"):
        return HttpResponse("Invalid OAuth state.", status=400)

    token_response = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config["redirect_uri"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    token_response.raise_for_status()
    token_payload = token_response.json()
    access_token = token_payload.get("access_token")
    if not access_token:
        return HttpResponse("Failed to fetch access token.", status=400)

    user_response = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    user_response.raise_for_status()
    user = user_response.json()
    request.session["discord_user"] = {
        "id": str(user.get("id", "")),
        "username": user.get("username", ""),
        "global_name": user.get("global_name") or user.get("username", ""),
    }

    return HttpResponseRedirect(reverse("calendar"))


def discord_logout(request: HttpRequest) -> HttpResponse:
    request.session.pop("discord_user", None)
    return HttpResponseRedirect(reverse("calendar"))


def calendar_view(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    week_start = _week_start(today, start_weekday=3)
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    time_slots: list[time] = []
    for hour in range(24):
        time_slots.append(time(hour, 0))
        time_slots.append(time(hour, 30))
    schedule = _ensure_week_schedule(week_start)
    guild = schedule.guild

    oauth_user = request.session.get("discord_user", {})
    display_name = (
        oauth_user.get("global_name")
        or oauth_user.get("username")
        or ""
    )
    user_id = oauth_user.get("id") or ""
    selected_slots: set[tuple[str, str]] = set()
    success_message = ""

    if request.method == "POST" and oauth_user.get("id"):
        display_name = oauth_user.get("global_name") or oauth_user.get("username") or ""
        user_id = oauth_user.get("id") or ""
        raw_slots = request.POST.get("selected_slots", "[]")
        try:
            submitted_slots = json.loads(raw_slots)
        except json.JSONDecodeError:
            submitted_slots = []

        if display_name:
            member = _get_member(guild, user_id, display_name)
            Availability.objects.filter(schedule=schedule, member=member).delete()

            tz = timezone.get_current_timezone()
            for slot in submitted_slots:
                slot_date = slot.get("date")
                slot_hour = slot.get("hour")
                if not slot_date or slot_hour is None:
                    continue
                try:
                    slot_day = date.fromisoformat(slot_date)
                    slot_time = datetime.strptime(slot_hour, "%H:%M").time()
                except (ValueError, TypeError):
                    continue
                start_dt = timezone.make_aware(
                    datetime.combine(slot_day, slot_time), tz
                )
                end_dt = start_dt + timedelta(minutes=30)
                Availability.objects.create(
                    schedule=schedule,
                    member=member,
                    start_time=start_dt,
                    end_time=end_dt,
                    status=Availability.Status.AVAILABLE,
                )
            success_message = "Availability saved."

    if oauth_user.get("id"):
        member = _get_member(guild, user_id, display_name)
        existing = Availability.objects.filter(schedule=schedule, member=member)
        for availability in existing:
            local_start = timezone.localtime(availability.start_time)
            selected_slots.add((local_start.date().isoformat(), local_start.strftime("%H:%M")))

    availability_map: dict[str, list[str]] = {}
    member_ids = set()
    for availability in Availability.objects.filter(schedule=schedule).select_related("member"):
        local_start = timezone.localtime(availability.start_time)
        key = f"{local_start.date().isoformat()}::{local_start.strftime('%H:%M')}"
        availability_map.setdefault(key, []).append(availability.member.display_name)
        member_ids.add(availability.member_id)

    total_members = len(member_ids)
    all_available_map = {
        key: (len(set(names)) == total_members and total_members > 0)
        for key, names in availability_map.items()
    }

    selected_slots_json = json.dumps(sorted(selected_slots))
    availability_map_json = json.dumps(availability_map)
    all_available_map_json = json.dumps(all_available_map)
    context = {
        "week_label": f"Week of {week_start.isoformat()}",
        "days": days,
        "slots": time_slots,
        "selected_slots_json": selected_slots_json,
        "availability_map_json": availability_map_json,
        "all_available_map_json": all_available_map_json,
        "display_name": display_name,
        "user_id": user_id,
        "success_message": success_message,
        "oauth_user": oauth_user,
    }
    return render(request, "scheduler/calendar.html", context)
