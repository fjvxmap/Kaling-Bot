from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES_BY_BASE_ID,
    CRAFTING_RECIPES,
    DUNGEONS,
    ENHANCEMENT_METHODS,
    GACHA_POOLS,
    ITEM_BY_ID,
    JOBS,
    LIBERATION,
    MATERIAL_BY_ID,
    MATERIALS,
    MAX_EQUIPPED_ITEMS,
    MAX_EQUIPPED_SKILLS,
    POTENTIAL_GRADE_LABELS,
    RARITIES,
    RARITY_LABELS,
    SKILL_BY_ID,
    scaled_item_stats,
)
from bot.services.rpg.manager import PotentialCandidate, RewardReport
from bot.services.rpg.models import ItemInstance, PlayerProfile, PotentialLine

from .runtime import PendingPotential, WebRPGRuntime, get_runtime


def _identity(request: HttpRequest) -> tuple[int, str] | None:
    user = request.session.get("discord_user") or {}
    user_id = str(user.get("id", "")).strip()
    if user_id.isdigit():
        name = str(user.get("global_name") or user.get("username") or "Player")
        return int(user_id), name
    if settings.DEBUG:
        dev_id = os.getenv("KALING_WEB_DEV_USER_ID", "").strip()
        if dev_id.isdigit():
            return int(dev_id), os.getenv("KALING_WEB_DEV_USER_NAME", "Web Tester")
    return None


def _json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _auth_error() -> JsonResponse:
    return JsonResponse({"ok": False, "message": "Discord 로그인이 필요합니다."}, status=401)


def _item_payload(runtime: WebRPGRuntime, profile: PlayerProfile, item: ItemInstance) -> dict[str, Any]:
    service = runtime.engine.service
    template = ITEM_BY_ID.get(item.template_id)
    if template is None:
        return {
            "uid": item.uid,
            "name": item.template_id,
            "rarity": "normal",
            "stars": item.stars,
            "destroyed": item.destroyed,
            "equipped": False,
            "unknown": True,
        }
    return {
        "uid": item.uid,
        "template_id": item.template_id,
        "name": template.name,
        "rarity": template.rarity,
        "rarity_label": RARITY_LABELS.get(template.rarity, template.rarity),
        "stars": item.stars,
        "destroyed": item.destroyed,
        "equipped": item.uid in profile.equipped_item_uids,
        "enhancement_disabled": template.enhancement_disabled,
        "unsellable": template.unsellable,
        "genesis_weapon": template.genesis_weapon,
        "stats": scaled_item_stats(item.template_id, item.stars),
        "stats_text": service.item_stats_text(item),
        "effects_text": service.item_template_effects_text(item.template_id),
        "potential_grade": item.potential_grade,
        "potential_grade_label": POTENTIAL_GRADE_LABELS.get(item.potential_grade, item.potential_grade),
        "potential_locked": item.potential_locked,
        "potential_text": service.potential_text(item),
        "potential_reroll_cost": service.potential_reroll_cost(item),
        "potential_progress": service.potential_tier_progress_text(profile, item.potential_grade)
        if item.potential_grade
        else "",
        "sell_price": service.item_sell_price(item),
        "score": round(service.item_score(item), 3),
    }


def _profile_payload(runtime: WebRPGRuntime, profile: PlayerProfile) -> dict[str, Any]:
    service = runtime.engine.service
    stats = service.profile_stats(profile)
    progress, required = service.level_progress(profile)
    rarity_rank = {rarity: index for index, rarity in enumerate(RARITIES)}
    inventory = sorted(
        (_item_payload(runtime, profile, item) for item in profile.inventory),
        key=lambda item: (
            not item.get("equipped", False),
            item.get("destroyed", False),
            -rarity_rank.get(str(item.get("rarity", "normal")), 0),
            -int(item.get("stars", 0)),
            -float(item.get("score", 0)),
            str(item.get("name", "")),
        ),
    )
    current_job = service.current_job(profile)
    genesis = service.genesis_item(profile)
    next_stage = service.liberation_next_stage(profile)
    pending = runtime.pending_potentials.get(profile.user_id)
    return {
        "user_id": str(profile.user_id),
        "display_name": profile.display_name,
        "level": profile.level,
        "exp": profile.exp,
        "exp_progress": progress,
        "exp_required": required,
        "gold": profile.gold,
        "job_id": current_job.id,
        "job_name": current_job.name,
        "job_tier": current_job.tier,
        "stats": {**asdict(stats), "final_hp": stats.final_hp},
        "stats_text": service.format_stats(stats),
        "daily_remaining": service.daily_remaining(profile),
        "daily_unlimited": service.daily_remaining(profile) < 0,
        "materials": [
            {
                "id": material.id,
                "name": material.name,
                "rarity": material.rarity,
                "rarity_label": RARITY_LABELS.get(material.rarity, material.rarity),
                "amount": int(profile.materials.get(material.id, 0)),
                "description": material.description,
            }
            for material in MATERIALS
            if int(profile.materials.get(material.id, 0)) > 0
        ],
        "material_amounts": dict(profile.materials),
        "inventory": inventory,
        "equipped_item_uids": list(profile.equipped_item_uids),
        "max_equipped_items": MAX_EQUIPPED_ITEMS,
        "auto_sell_rarities": list(profile.auto_sell_rarities),
        "potential_pity": dict(profile.potential_pity),
        "equipped_skill_ids": list(profile.equipped_skill_ids),
        "equipped_special_skill_id": profile.equipped_special_skill_id,
        "max_equipped_skills": MAX_EQUIPPED_SKILLS,
        "unlocked_skill_ids": [skill.id for skill in service.unlocked_skills(profile)],
        "unlocked_special_skill_ids": [skill.id for skill in service.unlocked_special_skills(profile)],
        "available_job_ids": [job.id for job in service.available_jobs(profile)],
        "free_advance_job_ids": [job.id for job in service.free_advance_jobs(profile)],
        "weekly_remaining": {
            base_id: service.boss_start_remaining(profile, variants[0].id)
            for base_id, variants in BOSSES_BY_BASE_ID.items()
            if variants
        },
        "solo_cleared_boss_ids": list(profile.solo_cleared_boss_ids),
        "cleared_boss_ids": list(profile.cleared_boss_ids),
        "liberation": {
            "stage": profile.genesis_liberation_stage,
            "item_uid": genesis.uid if genesis is not None else 0,
            "item_name": ITEM_BY_ID[genesis.template_id].name if genesis is not None else "",
            "claimable": genesis is None and LIBERATION.boss_id in profile.cleared_boss_ids,
            "target_item_name": ITEM_BY_ID.get(service.liberation_weapon_template_id(profile)).name
            if service.liberation_weapon_template_id(profile) in ITEM_BY_ID
            else "",
            "next_stage": (
                {
                    "stage": next_stage.stage,
                    "name": next_stage.name,
                    "stars": next_stage.stars,
                    "materials": dict(next_stage.materials),
                }
                if next_stage is not None
                else None
            ),
        },
        "pending_potential": _pending_potential_payload(runtime, pending) if pending else None,
    }


def _pending_potential_payload(runtime: WebRPGRuntime, pending: PendingPotential) -> dict[str, Any]:
    service = runtime.engine.service
    return {
        "item_uid": pending.item_uid,
        "before_grade": pending.before_grade,
        "required_grade": pending.required_grade,
        "candidates": [
            {
                "index": index,
                "grade": candidate.grade,
                "grade_label": service.potential_grade_label(candidate.grade),
                "tier_up": candidate.tier_up,
                "text": service.potential_lines_text(candidate.lines),
                "lines": [asdict(line) for line in candidate.lines],
            }
            for index, candidate in enumerate(pending.candidates)
        ],
    }


def _reward_payload(runtime: WebRPGRuntime, reward: RewardReport | None) -> dict[str, Any] | None:
    if reward is None:
        return None
    service = runtime.engine.service
    return {
        "gold": reward.gold,
        "exp": reward.exp,
        "levels_gained": reward.levels_gained,
        "items": [service.item_title(item) for item in reward.dropped_items],
        "materials": [
            {"id": material_id, "name": service.material_name(material_id), "amount": amount}
            for material_id, amount in reward.materials.items()
        ],
        "auto_sold_count": len(reward.auto_sold_items),
        "auto_sold_gold": reward.auto_sold_gold,
    }


def _content_payload(runtime: WebRPGRuntime, profile: PlayerProfile) -> dict[str, Any]:
    service = runtime.engine.service
    festival = service.active_gacha_festival()
    return {
        "rarities": [
            {"id": rarity, "name": RARITY_LABELS.get(rarity, rarity)} for rarity in RARITIES
        ],
        "dungeons": [
            {
                "id": dungeon.id,
                "name": dungeon.name,
                "level": dungeon.level_req,
                "description": dungeon.description,
                "enemies": [
                    {"id": enemy.id, "name": enemy.name, "rare": enemy.rare}
                    for enemy in dungeon.enemies
                ],
            }
            for dungeon in DUNGEONS
        ],
        "bosses": [
            {
                "base_id": base_id,
                "name": variants[0].name,
                "variants": [
                    {
                        "id": boss.id,
                        "difficulty": boss.difficulty,
                        "difficulty_label": "하드" if boss.difficulty == "hard" else "일반",
                        "level": boss.level_req,
                        "description": boss.description,
                        "gold": boss.gold,
                        "exp": boss.exp,
                        "rewards": list(dict.fromkeys(
                            [
                                ITEM_BY_ID[drop.template_id].name
                                for drop in boss.rewards.item_drops
                                if drop.template_id in ITEM_BY_ID
                            ]
                            + [
                                MATERIAL_BY_ID[drop.id].name
                                for drop in boss.rewards.material_drops
                                if drop.id in MATERIAL_BY_ID
                            ]
                        )),
                    }
                    for boss in variants
                ],
            }
            for base_id, variants in BOSSES_BY_BASE_ID.items()
            if variants
        ],
        "skills": [
            {
                "id": skill.id,
                "name": skill.name,
                "level": skill.unlock_level,
                "role": skill.role,
                "special": skill.special,
                "summary": service.skill_summary(skill),
                "note": skill.note,
            }
            for skill in SKILL_BY_ID.values()
        ],
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "tier": job.tier,
                "level": job.level_req,
                "parent_id": job.parent_id,
                "description": job.description,
                "stats_text": service.format_stats(job.stats, signed=True),
            }
            for job in JOBS
        ],
        "recipes": [
            {
                "id": recipe.id,
                "name": recipe.name,
                "level": recipe.level_req,
                "gold": recipe.gold,
                "description": recipe.description,
                "result_item_id": recipe.result_item_id,
                "result_name": ITEM_BY_ID.get(recipe.result_item_id).name
                if recipe.result_item_id in ITEM_BY_ID
                else recipe.result_item_id,
                "result_rarity": ITEM_BY_ID.get(recipe.result_item_id).rarity
                if recipe.result_item_id in ITEM_BY_ID
                else "normal",
                "result_stars": recipe.result_stars,
                "materials": [
                    {
                        "id": material_id,
                        "name": service.material_name(material_id),
                        "amount": amount,
                    }
                    for material_id, amount in recipe.materials.items()
                ],
            }
            for recipe in CRAFTING_RECIPES
        ],
        "gacha_pools": [
            {
                "id": pool.id,
                "name": pool.name,
                "description": pool.description,
                "cost_material_id": pool.cost_material_id,
                "cost_material_name": service.material_name(pool.cost_material_id),
                "base_draws": pool.draws,
                "base_cost": pool.cost_material_amount,
                "draw_options": list(dict.fromkeys([1, int(pool.draws), 50, 100])),
            }
            for pool in GACHA_POOLS
        ],
        "festival": (
            {
                "id": festival.id,
                "name": festival.name,
                "description": festival.description,
                "period": runtime.engine._gacha_festival_period_text(festival),
                "overrides": [
                    {
                        "name": runtime.engine._gacha_festival_target_label(override.type, override.target_id),
                        "chance": override.chance,
                    }
                    for override in festival.overrides
                ],
            }
            if festival is not None
            else None
        ),
        "enhancement_methods": [
            {
                "id": method.id,
                "name": method.name,
                "description": method.description,
                "min_stars": method.min_stars,
                "max_stars": method.max_stars,
            }
            for method in ENHANCEMENT_METHODS
        ],
    }


def _joinable_sessions(runtime: WebRPGRuntime, user_id: int) -> list[dict[str, Any]]:
    rows = []
    for session in runtime.engine.boss_sessions.values():
        if session.started or session.completed or session.failed or session.cancelled:
            continue
        if user_id in session.participants:
            continue
        owner = session.participants.get(session.owner_id)
        rows.append({
            "id": session.id,
            "boss_name": session.boss.name,
            "difficulty": "하드" if session.boss.difficulty == "hard" else "일반",
            "owner": owner.display_name if owner else "알 수 없음",
            "participants": len(session.participants),
            "practice": session.practice,
        })
    return rows


def _boss_session_payload(runtime: WebRPGRuntime, session, user_id: int) -> dict[str, Any]:
    engine = runtime.engine
    participant = session.participants.get(user_id)
    warning = participant.pending_warning if participant is not None else None
    skills = []
    if participant is not None:
        profile = engine.service.get_profile(user_id, participant.display_name)
        for skill in engine.service.combat_skills(profile):
            cooldown = participant.ability_cooldowns.get(skill.id, 0)
            skills.append({
                "id": skill.id,
                "name": skill.name,
                "summary": engine.service.skill_summary(skill),
                "state": engine._ability_state_text(participant, skill, cooldown_prefix=True),
                "ready": cooldown <= 0 and not engine._ability_used_out(participant, skill) and participant.alive,
            })
    detail = participant.last_damage_detail if participant is not None else None
    return {
        "id": session.id,
        "boss_id": session.boss.id,
        "boss_name": session.boss.name,
        "boss_level": session.boss.level_req,
        "difficulty": session.boss.difficulty,
        "difficulty_label": "하드" if session.boss.difficulty == "hard" else "일반",
        "practice": session.practice,
        "owner_id": str(session.owner_id),
        "is_owner": session.owner_id == user_id,
        "started": session.started,
        "completed": session.completed,
        "failed": session.failed,
        "cancelled": session.cancelled,
        "boss_hp": session.boss_hp,
        "boss_max_hp": session.boss_max_hp,
        "boss_hp_ratio": round(session.boss_hp / max(1, session.boss_max_hp), 4),
        "participant": (
            {
                "hp": participant.hp,
                "max_hp": participant.max_hp,
                "alive": participant.alive,
                "turn": participant.turn,
                "ct": participant.ct if engine._boss_has_ct_system(session) else None,
                "ct_max": session.ct_max if engine._boss_has_ct_system(session) else None,
                "warning": engine._warning_display_text(warning, participant) if warning else "",
                "player_effects": engine._effects_text(participant.player_effects, limit=1600),
                "boss_effects": engine._effects_text(participant.boss_effects, limit=1600),
                "player_stacks": engine._stack_effects_text(participant.player_stack_effects),
                "boss_stacks": engine._stack_effects_text(participant.boss_stack_effects),
                "hp_lock": engine._boss_hp_lock_text(session, participant),
            }
            if participant is not None
            else None
        ),
        "participants": [
            {
                "user_id": str(member.user_id),
                "name": member.display_name,
                "level": member.level,
                "hp": member.hp,
                "max_hp": member.max_hp,
                "alive": member.alive,
            }
            for member in session.participants.values()
        ],
        "skills": skills,
        "log": session.log[-16:],
        "log_start_index": max(0, len(session.log) - 16),
        "rewards": {str(key): value for key, value in session.rewards.items()},
        "damage_detail": (
            {
                "action": detail.action,
                "target": detail.target,
                "summary": detail.summary,
                "total_damage": detail.total_damage,
                "detail_lines": detail.detail_lines,
                "received_damage": detail.received_damage,
                "received_summary": detail.received_summary,
                "received_source": detail.received_source,
                "received_detail_lines": detail.received_detail_lines,
            }
            if detail is not None
            else None
        ),
    }


def _enhancement_payload(runtime: WebRPGRuntime, preview) -> dict[str, Any]:
    service = runtime.engine.service
    return {
        "ok": preview.ok,
        "message": preview.message,
        "item_uid": preview.item.uid if preview.item else 0,
        "cost": preview.cost,
        "odds": {
            "success": preview.odds[0],
            "fail": preview.odds[1],
            "destroy": preview.odds[2],
        },
        "before_stars": preview.before_stars,
        "after_stars": preview.after_stars,
        "before_stats": preview.before_stats,
        "after_stats": preview.after_stats,
        "delta_text": runtime.engine.service.format_stats(preview.delta_stats, signed=True),
        "method_id": preview.method_id,
        "method_name": preview.method_name,
        "material_costs": preview.material_costs,
        "material_cost_rows": [
            {
                "id": material_id,
                "name": service.material_name(material_id),
                "amount": amount,
                "owned": int(preview.profile.materials.get(material_id, 0)),
            }
            for material_id, amount in preview.material_costs.items()
        ],
        "spare_uid": preview.spare_item.uid if preview.spare_item else 0,
    }


def _enhancement_result_payload(
    runtime: WebRPGRuntime,
    result,
    *,
    include_next_preview: bool = True,
) -> dict[str, Any]:
    service = runtime.engine.service
    next_preview = None
    if include_next_preview and result.item is not None and not result.item.destroyed:
        preview = service.enhancement_preview(
            result.profile.user_id,
            result.profile.display_name,
            result.item.uid,
            result.method_id or None,
        )
        next_preview = _enhancement_payload(runtime, preview)
    return {
        "item_uid": result.item.uid if result.item else 0,
        "outcome": result.outcome,
        "before_stars": result.before_stars,
        "after_stars": result.after_stars,
        "cost": result.cost,
        "odds": {
            "success": result.odds[0],
            "fail": result.odds[1],
            "destroy": result.odds[2],
        },
        "method_id": result.method_id,
        "method_name": result.method_name,
        "material_cost_rows": [
            {
                "id": material_id,
                "name": service.material_name(material_id),
                "amount": amount,
            }
            for material_id, amount in result.material_costs.items()
        ],
        "remaining_gold": result.profile.gold,
        "next_preview": next_preview,
    }


def _api_response(
    runtime: WebRPGRuntime,
    profile: PlayerProfile,
    *,
    ok: bool = True,
    message: str = "",
    result: dict[str, Any] | None = None,
    session=None,
) -> JsonResponse:
    payload: dict[str, Any] = {
        "ok": ok,
        "message": message,
        "profile": _profile_payload(runtime, profile),
        "joinable_sessions": _joinable_sessions(runtime, profile.user_id),
    }
    if result is not None:
        payload["result"] = result
    if session is not None:
        payload["boss_session"] = _boss_session_payload(runtime, session, profile.user_id)
    else:
        active = runtime.active_session(profile.user_id)
        payload["boss_session"] = _boss_session_payload(runtime, active, profile.user_id) if active else None
    return JsonResponse(payload)


@ensure_csrf_cookie
def home(request: HttpRequest):
    return render(request, "rpg_web/index.html", {"signed_in": _identity(request) is not None})


@require_GET
def bootstrap(request: HttpRequest) -> JsonResponse:
    identity = _identity(request)
    if identity is None:
        return _auth_error()
    user_id, display_name = identity
    runtime = get_runtime()
    with runtime.lock:
        profile = runtime.engine.service.get_profile(user_id, display_name)
        session = runtime.active_session(user_id)
        return JsonResponse({
            "ok": True,
            "profile": _profile_payload(runtime, profile),
            "content": _content_payload(runtime, profile),
            "boss_session": _boss_session_payload(runtime, session, user_id) if session else None,
            "joinable_sessions": _joinable_sessions(runtime, user_id),
        })


@require_POST
def action(request: HttpRequest) -> JsonResponse:
    identity = _identity(request)
    if identity is None:
        return _auth_error()
    user_id, display_name = identity
    payload = _json_body(request)
    action_type = str(payload.get("type", ""))
    runtime = get_runtime()
    engine = runtime.engine
    service = engine.service

    with runtime.lock:
        profile = service.get_profile(user_id, display_name)
        try:
            if action_type == "explore":
                result = service.explore_many(user_id, display_name, str(payload.get("dungeon_id", "")), int(payload.get("count", 1)))
                rows = []
                for run in result.results:
                    rows.append({
                        "enemy": run.enemy.name if run.enemy else "",
                        "won": run.battle.won if run.battle else False,
                        "turns": run.battle.turns if run.battle else 0,
                        "player_hp": run.battle.player_hp if run.battle else 0,
                        "reward": _reward_payload(runtime, run.reward),
                    })
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message, result={"runs": rows})

            if action_type == "equipment_set":
                result = service.set_equipped_items(user_id, display_name, [int(uid) for uid in payload.get("uids", [])])
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "equipment_auto":
                result = service.auto_equip_best(user_id, display_name)
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "sell":
                result = service.sell_items_by_uids(user_id, display_name, [int(uid) for uid in payload.get("uids", [])])
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message, result={"gold": result.gold, "count": result.sold_count})
            if action_type == "auto_sell_set":
                result = service.set_auto_sell_rarities(user_id, display_name, [str(value) for value in payload.get("rarities", [])])
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "auto_sell_now":
                result = service.sell_auto_sell_items(user_id, display_name)
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message, result={"gold": result.gold, "count": result.sold_count})

            if action_type == "skills_set":
                result = service.set_equipped_skills(user_id, display_name, [str(value) for value in payload.get("skill_ids", [])])
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "special_skill_set":
                result = service.set_equipped_special_skill(user_id, display_name, str(payload.get("skill_id", "")))
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)

            if action_type in {"job_advance", "job_free_advance"}:
                method = service.free_advance_job if action_type == "job_free_advance" else service.advance_job
                result = method(user_id, display_name, str(payload.get("job_id", "")))
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)

            if action_type == "craft":
                result = service.craft_item(user_id, display_name, str(payload.get("recipe_id", "")))
                detail = {"item": service.item_title(result.item) if result.item else ""}
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message, result=detail)
            if action_type == "gacha":
                result = service.roll_gacha(user_id, display_name, str(payload.get("pool_id", "")), int(payload.get("draws", 1)))
                detail = {
                    "items": [service.item_title(item) for item in result.items],
                    "materials": [
                        {"name": service.material_name(material_id), "amount": amount}
                        for material_id, amount in result.materials.items()
                    ],
                    "spent": result.spent_material_amount,
                    "auto_sold_count": len(result.auto_sold_items),
                    "auto_sold_gold": result.auto_sold_gold,
                }
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message, result=detail)

            if action_type == "enhancement_preview":
                preview = service.enhancement_preview(user_id, display_name, int(payload.get("item_uid", 0)), str(payload.get("method_id", "")) or None)
                return _api_response(runtime, preview.profile, ok=True, message=preview.message, result=_enhancement_payload(runtime, preview))
            if action_type == "enhance":
                result = service.enhance(user_id, display_name, int(payload.get("item_uid", 0)), str(payload.get("method_id", "")) or None)
                return _api_response(
                    runtime,
                    result.profile,
                    ok=result.ok,
                    message=result.message,
                    result=_enhancement_result_payload(runtime, result),
                )
            if action_type == "restore_preview":
                spare = int(payload.get("spare_uid", 0)) or None
                preview = service.restore_preview(user_id, display_name, int(payload.get("item_uid", 0)), spare)
                return _api_response(runtime, preview.profile, ok=True, message=preview.message, result=_enhancement_payload(runtime, preview))
            if action_type == "restore":
                spare = int(payload.get("spare_uid", 0)) or None
                result = service.restore(user_id, display_name, int(payload.get("item_uid", 0)), spare)
                return _api_response(
                    runtime,
                    result.profile,
                    ok=result.ok,
                    message=result.message,
                    result=_enhancement_result_payload(
                        runtime,
                        result,
                        include_next_preview=False,
                    ),
                )

            if action_type == "potential_roll":
                pending = runtime.pending_potentials.get(user_id)
                if pending and pending.required_grade:
                    return _api_response(runtime, profile, ok=False, message="등급이 상승한 잠재능력을 먼저 적용해야 합니다.")
                result = service.reroll_potential(user_id, display_name, int(payload.get("item_uid", 0)), int(payload.get("count", 1)))
                if result.ok:
                    runtime.pending_potentials[user_id] = PendingPotential(
                        int(payload.get("item_uid", 0)),
                        result.before_grade,
                        [PotentialLine(line.option_id, line.grade) for line in result.before_lines],
                        [PotentialCandidate(candidate.grade, [PotentialLine(line.option_id, line.grade) for line in candidate.lines], candidate.tier_up) for candidate in result.candidates],
                        result.required_grade,
                    )
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "potential_apply":
                pending = runtime.pending_potentials.get(user_id)
                index = int(payload.get("candidate_index", -1))
                if pending is None or index < 0 or index >= len(pending.candidates):
                    return _api_response(runtime, profile, ok=False, message="적용할 메모리얼 결과가 없습니다.")
                result = service.apply_potential_candidate(
                    user_id,
                    display_name,
                    pending.item_uid,
                    pending.before_grade,
                    pending.before_lines,
                    pending.candidates[index],
                    pending.required_grade,
                )
                if result.ok:
                    runtime.pending_potentials.pop(user_id, None)
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)

            if action_type == "liberation_claim":
                result = service.claim_genesis_weapon(user_id, display_name)
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)
            if action_type == "liberation_advance":
                result = service.advance_genesis_liberation(user_id, display_name)
                return _api_response(runtime, result.profile, ok=result.ok, message=result.message)

            if action_type == "boss_create":
                boss = BOSS_BY_ID.get(str(payload.get("boss_id", "")))
                if boss is None:
                    return _api_response(runtime, profile, ok=False, message="알 수 없는 보스입니다.")
                session, message = engine._create_boss_session(boss, user_id, display_name, practice=bool(payload.get("practice", False)))
                return _api_response(runtime, profile, ok=session is not None, message=message, session=session)
            if action_type == "boss_join":
                session = engine.boss_sessions.get(int(payload.get("session_id", 0)))
                if session is None:
                    return _api_response(runtime, profile, ok=False, message="참가할 보스전을 찾지 못했습니다.")
                ok, message = engine._add_boss_participant(session, user_id, display_name)
                return _api_response(runtime, profile, ok=ok, message=message, session=session)

            if action_type == "boss_batch_skip":
                if runtime.active_session(user_id) is not None:
                    return _api_response(runtime, profile, ok=False, message="진행 중인 보스전을 먼저 종료해 주세요.")
                skipped: list[str] = []
                failures: list[str] = []
                for boss in engine._boss_batch_skip_candidates(profile):
                    session, create_message = engine._create_boss_session(boss, user_id, display_name)
                    if session is None:
                        failures.append(f"{boss.name}: {create_message}")
                        continue
                    ok, skip_message = engine._skip_boss_session(session, user_id)
                    if ok:
                        skipped.append(engine._boss_display_name(boss))
                    else:
                        failures.append(f"{boss.name}: {skip_message}")
                profile = service.get_profile(user_id, display_name)
                if not skipped:
                    return _api_response(
                        runtime,
                        profile,
                        ok=False,
                        message=failures[0] if failures else "스킵할 수 있는 보스가 없습니다.",
                        result={"skipped": [], "failures": failures},
                    )
                return _api_response(
                    runtime,
                    profile,
                    message=f"보스 {len(skipped)}종을 일괄 스킵했습니다.",
                    result={"skipped": skipped, "failures": failures},
                )

            if action_type.startswith("boss_"):
                session = runtime.active_session(user_id)
                if session is None:
                    return _api_response(runtime, profile, ok=False, message="진행 중인 보스전이 없습니다.")
                if action_type == "boss_start":
                    ok, message = engine._start_boss_session(session, user_id)
                elif action_type == "boss_skip":
                    ok, message = engine._skip_boss_session(session, user_id)
                elif action_type == "boss_attack":
                    ok, message = engine._boss_attack(session, user_id, display_name)
                elif action_type == "boss_guard":
                    ok, message = engine._boss_guard(session, user_id, display_name)
                elif action_type == "boss_ability":
                    ok, message = engine._boss_use_ability(session, user_id, display_name, str(payload.get("skill_id", "")))
                elif action_type == "boss_cancel":
                    ok, message = engine._cancel_waiting_boss_participation(session, user_id, display_name)
                elif action_type == "boss_leave":
                    ok, message = engine._give_up_boss_session(session, user_id, display_name)
                else:
                    ok, message = False, "지원하지 않는 보스 액션입니다."
                profile = service.get_profile(user_id, display_name)
                if action_type in {"boss_cancel", "boss_leave"} and runtime.active_session(user_id) is None:
                    return _api_response(runtime, profile, ok=ok, message=message)
                return _api_response(runtime, profile, ok=ok, message=message, session=session)

            return _api_response(runtime, profile, ok=False, message="지원하지 않는 요청입니다.")
        except (TypeError, ValueError) as exc:
            return _api_response(runtime, profile, ok=False, message=f"입력값을 확인해 주세요: {exc}")
