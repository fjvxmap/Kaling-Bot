from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "bot" / "services" / "rpg" / "content"
STATIC_DIR = Path(__file__).with_name("static")
BACKUP_DIR = ROOT / ".rpg_content_backups"
DEFAULT_BACKUP_RETENTION = 20

SIMPLE_FILES = {
    "settings": "settings.json",
    "stats": "stats.json",
    "rarities": "rarities.json",
    "level_curve": "level_curve.json",
    "player": "player.json",
    "stat_allocation": "stat_allocation.json",
    "enhancement": "enhancement.json",
    "gacha": "gacha.json",
    "items": "items.json",
    "jobs": "jobs.json",
    "skills": "skills.json",
    "stack_effects": "stack_effects.json",
    "materials": "materials.json",
    "crafting_recipes": "crafting_recipes.json",
}

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
OBJECTIVE_IDS = {
    "damage",
    "hits",
    "debuff",
    "dispel",
    "clear_all",
    "triple_attack",
    "double_attack",
    "ability",
    "ability_damage",
    "warning_success",
    "warning_failure",
}
STACK_CONDITION_OBJECTIVE_IDS = OBJECTIVE_IDS | {"received_damage"}
EFFECT_ACTION_IDS = {"dispel", "clear_all"}
STACK_EFFECT_ACTION_IDS = {"stack_increase", "stack_decrease", "stack_set", "stack_remove", "stack_max"}
EFFECT_ACTION_IDS = EFFECT_ACTION_IDS | STACK_EFFECT_ACTION_IDS
WARNING_ACTIVATION_CONDITION_IDS = {"stack", "turn_multiple", "turn_range", "boss_hp_ratio", "ct_ready"}
WARNING_ACTIVATION_STACK_TARGET_IDS = {"boss", "player"}
EFFECT_TARGET_IDS = {"self", "me", "enemy", "ally", "allies", "opponent", "opponents", "enemies"}
EFFECT_ACTION_CONDITION_TARGET_IDS = {"self", "enemy", "allies", "opponents", "boss", "player"}
STAT_EFFECT_TARGET_IDS = {"self", "allies"}
HEAL_CAP_MODES = {"none", "flat", "max_hp_ratio"}
PLAIN_DAMAGE_MODES = {"none", "flat", "target_max_hp_ratio"}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_content() -> dict[str, Any]:
    content = {
        key: read_json(CONTENT_DIR / filename)
        for key, filename in SIMPLE_FILES.items()
    }
    content["dungeons"] = read_split_dir(CONTENT_DIR / "dungeons")
    content["bosses"] = read_split_dir(CONTENT_DIR / "bosses")
    return content


def read_split_dir(path: Path) -> list[dict[str, Any]]:
    rows = [read_json(file) for file in sorted(path.glob("*.json"))]
    return sorted(rows, key=lambda row: (int(row.get("sort_order", 9999)), str(row.get("id", ""))))


def save_content(content: dict[str, Any], backup_retention: int = DEFAULT_BACKUP_RETENTION) -> Path:
    normalize_content(content)
    errors = validate_content(content)
    if errors:
        raise ValueError("\n".join(errors))

    backup_path = backup_content(backup_retention)
    for key, filename in SIMPLE_FILES.items():
        write_json(CONTENT_DIR / filename, content.get(key, [] if key in list_keys() else {}))
    write_split_dir(CONTENT_DIR / "dungeons", content.get("dungeons", []))
    write_split_dir(CONTENT_DIR / "bosses", content.get("bosses", []))
    return backup_path


def list_keys() -> set[str]:
    return {"items", "jobs", "skills", "materials", "crafting_recipes", "stack_effects"}


def normalize_content(content: dict[str, Any]) -> None:
    stat_order = [str(stat) for stat in content.get("stats", {}).get("order", [])]
    stat_order_index = {stat: index for index, stat in enumerate(stat_order)}
    max_enhancement_stars = safe_int(content.get("settings", {}).get("max_enhancement_stars"), 10)
    normalize_enhancement(content.setdefault("enhancement", {}), max_enhancement_stars)
    for item in content.get("items", []):
        if isinstance(item, dict):
            normalize_stats_map(item, "stats", stat_order_index)
            normalize_fixed_stats(item, "stats", "fixed_stats", stat_order_index)
            normalize_stat_effects(item, "stat_effect_mods", "stat_effects", -1, bool(item.get("undispellable", True)), stat_order_index)
            item.pop("stat_effect_mods", None)
            normalize_combat_effects(item, "effects", bool(item.get("undispellable", True)), -1)
    for job in content.get("jobs", []):
        if isinstance(job, dict):
            normalize_stats_map(job, "stats", stat_order_index)
            normalize_stat_effects(job, "stat_effect_mods", "stat_effects", -1, bool(job.get("undispellable", True)), stat_order_index)
            job.pop("stat_effect_mods", None)
            normalize_combat_effects(job, "effects", bool(job.get("undispellable", True)), -1)
    for effect in content.get("stack_effects", []):
        if isinstance(effect, dict):
            normalize_stack_effect(effect, stat_order_index)
    for skill in content.get("skills", []):
        if isinstance(skill, dict):
            duration = safe_int(skill.get("duration"), 1)
            player_undispellable = bool(skill.get("player_undispellable", skill.get("undispellable", False)))
            enemy_undispellable = bool(skill.get("enemy_undispellable", False))
            normalize_stat_effects(skill, "player_mods", "player_stat_effects", duration, player_undispellable, stat_order_index)
            normalize_stat_effects(skill, "enemy_mods", "enemy_stat_effects", duration, enemy_undispellable, stat_order_index)
            damage_cut = safe_float(skill.get("damage_cut"), 0.0)
            if damage_cut > 0 and not any(effect.get("stat") == "damage_cut" for effect in skill.get("player_stat_effects", [])):
                skill.setdefault("player_stat_effects", []).append({
                    "stat": "damage_cut",
                    "target": "self",
                    "value": damage_cut,
                    "duration": duration,
                    "undispellable": player_undispellable,
                })
            skill["damage_cut"] = 0
            skill.pop("player_undispellable", None)
            skill.pop("enemy_undispellable", None)
            skill.pop("undispellable", None)
            normalize_combat_effects(skill, "effects", player_undispellable, duration)
            normalize_combat_effects(skill, "player_effects", player_undispellable, duration)
            normalize_combat_effects(skill, "enemy_effects", enemy_undispellable, duration)
            normalize_effect_actions(skill, "effect_actions")
            normalize_heal_cap(skill)
            skill["heal_target"] = normalize_stat_effect_target(skill.get("heal_target"))
            skill.pop("duration", None)
    for dungeon in content.get("dungeons", []):
        if not isinstance(dungeon, dict):
            continue
        normalize_stats_map(dungeon, "stats", stat_order_index)
        dungeon.pop("rank", None)
        for enemy in dungeon.get("enemies", []):
            if isinstance(enemy, dict):
                normalize_stats_map(enemy, "stats", stat_order_index)
                enemy.pop("rank", None)
                enemy.pop("drop_chance", None)
                normalize_reward(enemy.get("rewards", {}))
                enemy.pop("consolation_rewards", None)
    for boss in content.get("bosses", []):
        if isinstance(boss, dict):
            normalize_stats_map(boss, "stats", stat_order_index)
            boss.pop("drop_chance", None)
            boss.pop("rank", None)
            boss.pop("stat_points", None)
            normalize_boss_stack_effects(boss)
            normalize_boss_hp_locks(boss)
            normalize_boss_hp_effects(boss, stat_order_index)
            for warning in boss.get("warnings", []):
                if isinstance(warning, dict):
                    if isinstance(warning.get("pattern"), dict):
                        warning["pattern"]["id"] = str(warning.get("id", warning["pattern"].get("id", "")))
                        warning["pattern"]["name"] = str(warning.get("name", warning["pattern"].get("name", "")))
                        normalize_pattern_effects(warning["pattern"], stat_order_index)
                    normalize_warning_success_pattern(warning, stat_order_index)
                    normalize_warning_followups(warning)
                    normalize_warning_activation_conditions(warning)
                    normalize_warning_failure_variants(warning, stat_order_index)
            for pattern in boss.get("patterns", []):
                if isinstance(pattern, dict):
                    normalize_pattern_effects(pattern, stat_order_index)
            normalize_reward(boss.get("rewards", {}))
    if not isinstance(content.get("gacha"), dict):
        content["gacha"] = {}
    normalize_gacha(content["gacha"])


def normalize_stack_effect(effect: dict[str, Any], stat_order_index: dict[str, int]) -> None:
    effect["max_stacks"] = max(1, safe_int(effect.get("max_stacks", effect.get("max")), 1))
    tiers = effect.get("tiers", effect.get("stacks", []))
    if not isinstance(tiers, list):
        tiers = []
    normalized_tiers = []
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        tier["stack"] = max(1, safe_int(tier.get("stack", tier.get("stacks")), 1))
        normalize_stat_effects(tier, "mods", "stat_effects", -1, True, stat_order_index)
        force_self_stat_effect_targets(tier.get("stat_effects"))
        tier.pop("mods", None)
        normalize_combat_effects(tier, "effects", True, -1)
        force_self_combat_effect_targets(tier.get("effects"))
        normalized_tiers.append(tier)
    normalized_tiers.sort(key=lambda tier: safe_int(tier.get("stack"), 1))
    effect["tiers"] = normalized_tiers
    effect.pop("stacks", None)
    conditions = effect.get("conditions")
    if not isinstance(conditions, list):
        conditions = []
    effect["conditions"] = [
        normalize_stack_condition(condition)
        for condition in conditions
        if isinstance(condition, dict)
    ]


def force_self_stat_effect_targets(rows: Any) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        if isinstance(row, dict):
            row["target"] = "self"


def force_self_combat_effect_targets(effects: Any) -> None:
    if not isinstance(effects, dict):
        return
    for key in ("flurry", "double_strike"):
        if isinstance(effects.get(key), dict):
            effects[key]["target"] = "self"
            effects[key]["duration"] = -1
            effects[key]["undispellable"] = True
    for key in (
        "bonus_damage",
        "critical_reinforce",
        "final_damage",
        "post_attack_ability_damage",
        "ability_recast",
        "dispel_guard",
        "veil",
    ):
        if isinstance(effects.get(key), list):
            for item in effects[key]:
                if isinstance(item, dict):
                    item["target"] = "self"
                    item["duration"] = -1
                    item["undispellable"] = True
                    if key in {"dispel_guard", "veil"}:
                        item["mode"] = "duration"
                        item["count"] = 0


def normalize_stack_condition(condition: dict[str, Any]) -> dict[str, Any]:
    operation = str(condition.get("operation", condition.get("op", "increase")) or "increase")
    if operation.startswith("stack_"):
        operation = operation.removeprefix("stack_")
    if operation not in {"increase", "decrease", "set", "remove", "max"}:
        operation = "increase"
    objective = str(condition.get("objective", condition.get("kind", "damage")) or "damage")
    if objective in {"warning_success", "warning_failure"}:
        target = "none"
        required = 1
    else:
        target = str(condition.get("target", "self") or "self")
        if target in {"enemy", "opponent"}:
            target = "opponent"
        else:
            target = "self"
        required = max(1, safe_int(condition.get("required"), 1))
    return {
        "objective": objective,
        "target": target,
        "operation": operation,
        "value": max(1, safe_int(condition.get("value", condition.get("stacks")), 1)),
        "required": required,
        "min_damage": max(0, safe_int(condition.get("min_damage"), 0)),
    }


def normalize_pattern_effects(pattern: dict[str, Any], stat_order_index: dict[str, int] | None = None) -> None:
    duration = safe_int(pattern.get("duration"), 1)
    player_undispellable = bool(pattern.get("player_undispellable", False))
    boss_undispellable = bool(pattern.get("boss_undispellable", pattern.get("undispellable", False)))
    normalize_stat_effects(pattern, "player_mods", "player_stat_effects", duration, player_undispellable, stat_order_index)
    normalize_stat_effects(pattern, "boss_mods", "boss_stat_effects", duration, boss_undispellable, stat_order_index)
    pattern.pop("player_undispellable", None)
    pattern.pop("boss_undispellable", None)
    pattern.pop("undispellable", None)
    normalize_combat_effects(pattern, "effects", boss_undispellable, duration)
    normalize_combat_effects(pattern, "player_effects", player_undispellable, duration)
    normalize_combat_effects(pattern, "boss_effects", boss_undispellable, duration)
    normalize_effect_actions(pattern, "effect_actions")
    normalize_plain_damage(pattern)
    normalize_self_hp_loss(pattern)


def normalize_plain_damage(pattern: dict[str, Any]) -> None:
    raw = pattern.get("plain_damage", pattern.get("neutral_damage", pattern.get("true_damage")))
    pattern.pop("neutral_damage", None)
    pattern.pop("true_damage", None)
    if raw in (None, "", 0, 0.0):
        pattern.pop("plain_damage", None)
        return
    if isinstance(raw, dict):
        mode = str(raw.get("mode", raw.get("type", "flat")) or "flat")
        if mode in {"fixed", "amount", "value"}:
            mode = "flat"
        elif mode in {"target_max_hp", "target_max_hp_percent", "max_hp", "max_hp_ratio", "max_hp_percent", "hp_percent", "percent", "ratio"}:
            mode = "target_max_hp_ratio"
        elif mode not in PLAIN_DAMAGE_MODES:
            mode = "none"
        value = safe_float(raw.get("value", raw.get("amount", raw.get("ratio", raw.get("percent", 0.0)))), 0.0)
        if mode == "target_max_hp_ratio" and ("percent" in raw or (value or 0) > 1):
            value = (value or 0) / 100.0
    else:
        mode = "flat"
        value = safe_float(raw, 0.0)
    value = max(0.0, float(value or 0.0))
    if mode == "none" or value <= 0:
        pattern.pop("plain_damage", None)
        return
    pattern["plain_damage"] = {"mode": mode, "value": value}


def normalize_self_hp_loss(pattern: dict[str, Any]) -> None:
    raw = pattern.get(
        "self_hp_loss_ratio",
        pattern.get("self_hp_loss", pattern.get("hp_loss_ratio", pattern.get("hp_loss"))),
    )
    pattern.pop("self_hp_loss", None)
    pattern.pop("hp_loss_ratio", None)
    pattern.pop("hp_loss", None)
    if raw in (None, "", 0, 0.0):
        pattern.pop("self_hp_loss_ratio", None)
        return
    if isinstance(raw, dict):
        value = safe_float(raw.get("value", raw.get("ratio", raw.get("amount", raw.get("percent", 0.0)))), 0.0)
        if "percent" in raw:
            value = (value or 0.0) / 100.0
    else:
        value = safe_float(raw, 0.0)
    value = max(0.0, float(value or 0.0))
    if value <= 0:
        pattern.pop("self_hp_loss_ratio", None)
        return
    pattern["self_hp_loss_ratio"] = value


def normalize_warning_success_pattern(warning: dict[str, Any], stat_order_index: dict[str, int] | None = None) -> None:
    pattern = warning.get("success_pattern", warning.get("success_effect", warning.get("on_success")))
    warning.pop("success_effect", None)
    warning.pop("on_success", None)
    if not isinstance(pattern, dict):
        warning.pop("success_pattern", None)
        return
    warning_id = str(warning.get("id", "warning") or "warning")
    warning_name = str(warning.get("name", warning_id) or warning_id)
    pattern.setdefault("id", f"{warning_id}_success")
    pattern.setdefault("name", f"{warning_name} 성공 효과")
    normalize_pattern_effects(pattern, stat_order_index)
    warning["success_pattern"] = pattern


def normalize_warning_followups(warning: dict[str, Any]) -> None:
    success = warning.get(
        "success_warning_id",
        warning.get("on_success_warning_id", warning.get("next_success_warning_id", "")),
    )
    failure = warning.get(
        "failure_warning_id",
        warning.get("on_failure_warning_id", warning.get("next_failure_warning_id", "")),
    )
    warning.pop("on_success_warning_id", None)
    warning.pop("next_success_warning_id", None)
    warning.pop("on_failure_warning_id", None)
    warning.pop("next_failure_warning_id", None)
    if success:
        warning["success_warning_id"] = str(success)
    else:
        warning.pop("success_warning_id", None)
    if failure:
        warning["failure_warning_id"] = str(failure)
    else:
        warning.pop("failure_warning_id", None)


def warning_activation_condition_kind(value: Any) -> str:
    kind = str(value or "stack")
    aliases = {
        "stack_count": "stack",
        "stacks": "stack",
        "stack_level": "stack",
        "turn_mod": "turn_multiple",
        "turn_modulo": "turn_multiple",
        "turn_divisible": "turn_multiple",
        "turn_count_multiple": "turn_multiple",
        "turn": "turn_range",
        "turn_count": "turn_range",
        "boss_hp": "boss_hp_ratio",
        "hp": "boss_hp_ratio",
        "hp_ratio": "boss_hp_ratio",
        "hp_range": "boss_hp_ratio",
        "ct": "ct_ready",
    }
    return aliases.get(kind, kind)


def normalize_warning_activation_condition_target(value: Any) -> str:
    target = str(value or "boss")
    if target in {"player", "self", "participant", "user"}:
        return "player"
    return "boss"


def normalize_warning_activation_condition(condition: dict[str, Any]) -> dict[str, Any] | None:
    kind = warning_activation_condition_kind(condition.get("kind", condition.get("type", condition.get("condition", "stack"))))
    if kind not in WARNING_ACTIVATION_CONDITION_IDS:
        kind = "stack"
    if kind == "stack":
        effect_id = str(condition.get("stack_effect_id", condition.get("effect_id", condition.get("id", ""))) or "")
        if not effect_id:
            return None
        return {
            "kind": "stack",
            "stack_effect_id": effect_id,
            "target": normalize_warning_activation_condition_target(condition.get("target", "boss")),
            "min_stacks": max(0, safe_int(condition.get("min_stacks", condition.get("min", condition.get("stacks"))), 1)),
            "max_stacks": safe_int(condition.get("max_stacks", condition.get("max")), -1),
        }
    if kind == "turn_multiple":
        return {
            "kind": "turn_multiple",
            "multiple": max(1, safe_int(condition.get("multiple", condition.get("mod", condition.get("divisor", condition.get("value")))), 1)),
        }
    if kind == "turn_range":
        return {
            "kind": "turn_range",
            "min_turn": max(1, safe_int(condition.get("min_turn", condition.get("min", condition.get("turn"))), 1)),
            "max_turn": safe_int(condition.get("max_turn", condition.get("max")), -1),
        }
    if kind == "boss_hp_ratio":
        return {
            "kind": "boss_hp_ratio",
            "min_ratio": normalize_hp_threshold(condition.get("min_ratio", condition.get("min_hp", condition.get("min_hp_ratio", condition.get("min", 0.0))))),
            "max_ratio": normalize_hp_threshold(condition.get("max_ratio", condition.get("max_hp", condition.get("max_hp_ratio", condition.get("max", 1.0))))),
        }
    if kind == "ct_ready":
        return {
            "kind": "ct_ready",
            "ct_ready": safe_bool(condition.get("ct_ready", condition.get("ready")), True),
        }
    return None


def normalize_warning_activation_conditions(warning: dict[str, Any]) -> None:
    rows = warning.get(
        "activation_conditions",
        warning.get("trigger_conditions", warning.get("spawn_conditions", warning.get("conditions", []))),
    )
    warning.pop("trigger_conditions", None)
    warning.pop("spawn_conditions", None)
    warning.pop("conditions", None)
    if not isinstance(rows, list):
        warning.pop("activation_conditions", None)
        return
    normalized = [
        condition
        for row in rows
        if isinstance(row, dict)
        for condition in [normalize_warning_activation_condition(row)]
        if condition is not None
    ]
    if normalized:
        warning["activation_conditions"] = normalized
    else:
        warning.pop("activation_conditions", None)


def normalize_warning_failure_variants(warning: dict[str, Any], stat_order_index: dict[str, int] | None = None) -> None:
    variants = warning.get("failure_variants")
    if not isinstance(variants, list):
        warning.pop("failure_variants", None)
        return
    normalized = []
    warning_id = str(warning.get("id", "warning") or "warning")
    warning_name = str(warning.get("name", warning_id) or warning_id)
    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, dict):
            continue
        pattern = variant.get("pattern")
        if not isinstance(pattern, dict):
            pattern = {
                key: value
                for key, value in variant.items()
                if key not in {"conditions", "name"}
            }
        pattern.setdefault("id", f"{warning_id}_failure_variant_{index}")
        pattern.setdefault("name", variant.get("name") or f"{warning_name} 변형 {index}")
        normalize_pattern_effects(pattern, stat_order_index)
        conditions = []
        for condition in variant.get("conditions", []):
            if not isinstance(condition, dict):
                continue
            effect_id = str(condition.get("stack_effect_id", condition.get("effect_id", condition.get("id", ""))) or "")
            if not effect_id:
                continue
            target = str(condition.get("target", "boss") or "boss")
            if target in {"player", "self", "participant", "user"}:
                target = "player"
            else:
                target = "boss"
            min_stacks = max(0, safe_int(condition.get("min_stacks", condition.get("min", condition.get("stacks"))), 1))
            max_stacks = safe_int(condition.get("max_stacks", condition.get("max")), -1)
            conditions.append({
                "stack_effect_id": effect_id,
                "target": target,
                "min_stacks": min_stacks,
                "max_stacks": max_stacks,
            })
        if not conditions:
            continue
        normalized.append({
            "name": str(variant.get("name", pattern.get("name", f"{warning_name} 변형 {index}"))),
            "conditions": conditions,
            "pattern": pattern,
        })
    if normalized:
        warning["failure_variants"] = normalized
    else:
        warning.pop("failure_variants", None)


def normalize_hp_threshold(value: Any) -> float:
    threshold = safe_float(value, 0.0) or 0.0
    if threshold > 1:
        threshold /= 100.0
    return max(0.0, min(1.0, threshold))


def normalize_hp_thresholds(value: Any) -> list[float]:
    source = value if isinstance(value, list) else [value]
    thresholds = [normalize_hp_threshold(threshold) for threshold in source]
    unique = sorted({round(threshold, 6) for threshold in thresholds}, reverse=True)
    return unique or [0.0]


def normalize_boss_hp_locks(boss: dict[str, Any]) -> None:
    rows = boss.get("hp_locks", boss.get("hp_lock_thresholds", []))
    boss.pop("hp_lock_thresholds", None)
    if not isinstance(rows, list):
        boss.pop("hp_locks", None)
        return
    locks: set[float] = set()
    for row in rows:
        value = row.get("threshold", row.get("hp", row.get("value", 0.0))) if isinstance(row, dict) else row
        threshold = normalize_hp_threshold(value)
        if 0 < threshold < 1:
            locks.add(round(threshold, 6))
    if locks:
        boss["hp_locks"] = sorted(locks, reverse=True)
    else:
        boss.pop("hp_locks", None)


def normalize_boss_hp_effects(boss: dict[str, Any], stat_order_index: dict[str, int] | None = None) -> None:
    rows = boss.get("hp_effects", boss.get("hp_instant_effects", boss.get("instant_hp_effects", [])))
    boss.pop("hp_instant_effects", None)
    boss.pop("instant_hp_effects", None)
    if not isinstance(rows, list):
        boss.pop("hp_effects", None)
        return
    normalized = []
    boss_id = str(boss.get("id", "boss") or "boss")
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        pattern = row.get("pattern")
        if not isinstance(pattern, dict):
            pattern = {
                key: value
                for key, value in row.items()
                if key not in {"threshold", "thresholds", "name"}
            }
        thresholds = normalize_hp_thresholds(row.get("thresholds", row.get("threshold", pattern.get("threshold", 0))))
        pattern.setdefault("id", row.get("id") or f"{boss_id}_hp_effect_{index}")
        pattern.setdefault("name", row.get("name") or f"HP 즉시 효과 {index}")
        pattern["threshold"] = thresholds[0]
        normalize_pattern_effects(pattern, stat_order_index)
        normalized.append({
            "thresholds": thresholds,
            "pattern": pattern,
        })
    if normalized:
        boss["hp_effects"] = sorted(normalized, key=lambda effect: effect["thresholds"][0], reverse=True)
    else:
        boss.pop("hp_effects", None)


def normalize_boss_stack_effects(boss: dict[str, Any]) -> None:
    rows = boss.get("stack_effects")
    if not isinstance(rows, list):
        boss["stack_effects"] = []
        return
    normalized = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        effect_id = str(row.get("stack_effect_id", row.get("id", row.get("effect_id", ""))) or "")
        if not effect_id or effect_id in seen:
            continue
        seen.add(effect_id)
        normalized.append({
            "stack_effect_id": effect_id,
            "initial_stacks": max(0, safe_int(row.get("initial_stacks", row.get("stacks")), 0)),
        })
    boss["stack_effects"] = normalized


def normalize_gacha(gacha: Any) -> None:
    if not isinstance(gacha, dict):
        return
    gacha.setdefault("default_pool_id", "default")
    gacha.setdefault("material_id", "crystal")
    gacha["cost"] = max(1, safe_int(gacha.get("cost"), 3000))
    gacha["draws"] = max(1, safe_int(gacha.get("draws"), 10))
    pools = gacha.get("pools")
    if not isinstance(pools, list):
        pools = []
    gacha["pools"] = [pool for pool in pools if isinstance(pool, dict)]
    for index, pool in enumerate(gacha["pools"], start=1):
        pool.setdefault("id", f"pool_{index}")
        pool.setdefault("name", pool["id"])
        pool.setdefault("description", "")
        entries = pool.get("entries")
        if not isinstance(entries, list):
            entries = []
        pool["entries"] = [entry for entry in entries if isinstance(entry, dict)]
        for entry in pool["entries"]:
            entry.setdefault("type", "item_rarity")
            entry["chance"] = max(0.0, safe_float(entry.get("chance"), 0.0) or 0.0)
            if entry["type"] == "item":
                normalize_gacha_targets(entry, "item_ids", "items", "item_id", 1)
                entry["stars"] = max(0, safe_int(entry.get("stars"), 0))
            if entry["type"] == "item_rarity":
                entry["stars"] = max(0, safe_int(entry.get("stars"), 0))
            if entry["type"] == "material":
                default_amount = max(1, safe_int(entry.get("amount", entry.get("min")), 1))
                normalize_gacha_targets(entry, "material_ids", "materials", "material_id", default_amount)
                entry.pop("min", None)
                entry.pop("max", None)
            if entry["type"] == "material_rarity":
                entry["min"] = max(1, safe_int(entry.get("min", entry.get("amount")), 1))
                entry["max"] = max(entry["min"], safe_int(entry.get("max"), entry["min"]))


def normalize_gacha_targets(
    entry: dict[str, Any],
    key: str,
    legacy_key: str,
    id_key: str,
    default_amount: int,
) -> None:
    raw_targets = entry.get(key, entry.get(legacy_key, []))
    if not isinstance(raw_targets, list):
        raw_targets = []
    targets = []
    for raw_target in raw_targets:
        if isinstance(raw_target, dict):
            target_id = str(raw_target.get("id", raw_target.get(id_key, "")))
            amount = safe_int(raw_target.get("amount"), default_amount)
        else:
            target_id = str(raw_target)
            amount = default_amount
        if not target_id:
            continue
        targets.append({"id": target_id, "amount": max(1, amount)})
    entry[key] = targets
    entry.pop(legacy_key, None)


def normalize_stats_map(row: dict[str, Any], key: str, stat_order_index: dict[str, int]) -> None:
    stats = row.get(key)
    if stats in (None, {}):
        row[key] = {}
        return
    if not isinstance(stats, dict):
        row[key] = {}
        return
    row[key] = dict(sorted(
        stats.items(),
        key=lambda item: (
            stat_order_index.get(str(item[0]), len(stat_order_index)),
            str(item[0]),
        ),
    ))


def normalize_fixed_stats(
    row: dict[str, Any],
    stats_key: str,
    fixed_key: str,
    stat_order_index: dict[str, int],
) -> None:
    raw = row.get(fixed_key)
    stats = row.get(stats_key)
    if raw in (None, [], {}):
        row.pop(fixed_key, None)
        return
    if not isinstance(raw, list) or not isinstance(stats, dict):
        row.pop(fixed_key, None)
        return
    stat_keys = {str(key) for key in stats}
    fixed = sorted(
        {str(stat) for stat in raw if str(stat) in stat_keys},
        key=lambda stat: (stat_order_index.get(stat, len(stat_order_index)), stat),
    )
    if fixed:
        row[fixed_key] = fixed
    else:
        row.pop(fixed_key, None)


def normalize_stat_effects(
    row: dict[str, Any],
    legacy_key: str,
    effect_key: str,
    default_duration: int,
    fallback_undispellable: bool,
    stat_order_index: dict[str, int] | None = None,
) -> None:
    rows = row.get(effect_key)
    if not isinstance(rows, list):
        legacy = row.get(legacy_key)
        legacy_items = legacy.items() if isinstance(legacy, dict) else []
        rows = [
            {
                "stat": stat,
                "target": "self",
                "value": value,
                "duration": default_duration,
                "undispellable": fallback_undispellable,
            }
            for stat, value in legacy_items
            if safe_float(value, 0.0) != 0
        ]
    normalized = []
    for effect in rows:
        if not isinstance(effect, dict):
            continue
        stat = str(effect.get("stat", effect.get("key", "")))
        value = safe_float(effect.get("value"), 0.0)
        if not stat:
            continue
        normalized_effect = {
            "stat": stat,
            "target": normalize_stat_effect_target(effect.get("target")),
            "value": value,
            "duration": safe_int(effect.get("duration"), default_duration),
            "undispellable": bool(effect.get("undispellable", fallback_undispellable)),
        }
        normalized.append(normalized_effect)
    if stat_order_index is not None:
        normalized.sort(key=lambda effect: (
            stat_order_index.get(str(effect.get("stat", "")), len(stat_order_index)),
            str(effect.get("stat", "")),
        ))
    if normalized:
        row[effect_key] = normalized
    else:
        row.pop(effect_key, None)
    row[legacy_key] = {}


def normalize_stat_effect_target(value: Any) -> str:
    target = str(value or "self")
    if target in {"ally", "allies", "party"}:
        return "allies"
    return "self"


def normalize_heal_cap(row: dict[str, Any]) -> None:
    raw_cap = row.get("heal_cap")
    if isinstance(raw_cap, dict):
        raw_mode = str(raw_cap.get("mode", raw_cap.get("type", raw_cap.get("kind", "none"))) or "none")
        value = safe_float(raw_cap.get("value", raw_cap.get("amount", 0.0)), 0.0) or 0.0
    else:
        raw_mode = str(row.get("heal_cap_mode", row.get("heal_cap_type", "none")) or "none")
        value = safe_float(row.get("heal_cap_value", raw_cap if raw_cap is not None else 0.0), 0.0) or 0.0
        if raw_cap is not None and raw_mode == "none":
            raw_mode = "flat"
    aliases = {
        "fixed": "flat",
        "value": "flat",
        "amount": "flat",
        "max_hp": "max_hp_ratio",
        "max_hp_percent": "max_hp_ratio",
        "hp_percent": "max_hp_ratio",
        "percent": "max_hp_ratio",
    }
    mode = aliases.get(raw_mode, raw_mode)
    if raw_mode in {"max_hp_percent", "hp_percent", "percent"} or (mode == "max_hp_ratio" and value > 1):
        value /= 100.0
    row.pop("heal_cap_mode", None)
    row.pop("heal_cap_type", None)
    row.pop("heal_cap_value", None)
    if mode not in {"flat", "max_hp_ratio"} or value <= 0:
        row.pop("heal_cap", None)
        return
    row["heal_cap"] = {
        "mode": mode,
        "value": value,
    }


def normalize_combat_effects(
    row: dict[str, Any],
    key: str,
    fallback_undispellable: bool = False,
    default_duration: int = 1,
) -> None:
    effects = row.get(key)
    if not isinstance(effects, dict):
        row.pop(key, None)
        return
    default_duration = safe_int(default_duration, 1)
    if default_duration == 0:
        default_duration = 1
    flurry = effects.get("flurry")
    if isinstance(flurry, dict):
        flurry.setdefault("undispellable", fallback_undispellable)
        flurry.setdefault("duration", default_duration)
        flurry["target"] = normalize_stat_effect_target(flurry.get("target"))
    double_strike = effects.get("double_strike")
    if isinstance(double_strike, dict):
        double_strike.setdefault("undispellable", fallback_undispellable)
        double_strike.setdefault("duration", default_duration)
        double_strike["target"] = normalize_stat_effect_target(double_strike.get("target"))
        double_strike["count"] = max(2, safe_int(double_strike.get("count", double_strike.get("actions", 2)), 2))
    bonus = effects.get("bonus_damage")
    if isinstance(bonus, list):
        for item in bonus:
            if isinstance(item, dict):
                item.setdefault("undispellable", fallback_undispellable)
                item.setdefault("duration", default_duration)
                item["target"] = normalize_stat_effect_target(item.get("target"))
        effects["bonus_damage"] = [
            item for item in bonus
            if isinstance(item, dict) and safe_float(item.get("ratio", item.get("percent")), 0.0) > 0
        ]
        if not effects["bonus_damage"]:
            effects.pop("bonus_damage", None)
    elif bonus in (None, [], {}):
        effects.pop("bonus_damage", None)
    reinforce = effects.get("critical_reinforce")
    if isinstance(reinforce, list):
        for item in reinforce:
            if isinstance(item, dict):
                item.setdefault("undispellable", fallback_undispellable)
                item.setdefault("duration", default_duration)
                item["target"] = normalize_stat_effect_target(item.get("target"))
        effects["critical_reinforce"] = [
            item for item in reinforce
            if isinstance(item, dict) and safe_float(item.get("ratio", item.get("percent")), 0.0) > 0
        ]
        if not effects["critical_reinforce"]:
            effects.pop("critical_reinforce", None)
    elif reinforce in (None, [], {}):
        effects.pop("critical_reinforce", None)
    final_damage = effects.get("final_damage")
    if isinstance(final_damage, (list, dict)):
        final_damage_rows = final_damage if isinstance(final_damage, list) else [final_damage]
        for item in final_damage_rows:
            if isinstance(item, dict):
                item.setdefault("undispellable", fallback_undispellable)
                item.setdefault("duration", default_duration)
                item["target"] = normalize_stat_effect_target(item.get("target"))
        effects["final_damage"] = [
            item for item in final_damage_rows
            if isinstance(item, dict) and -1 < safe_effect_ratio(item) != 0
        ]
        if not effects["final_damage"]:
            effects.pop("final_damage", None)
    elif final_damage in (None, [], {}):
        effects.pop("final_damage", None)
    post_attack = effects.get("post_attack_ability_damage")
    if isinstance(post_attack, (list, dict)):
        post_attack_rows = post_attack if isinstance(post_attack, list) else [post_attack]
        for item in post_attack_rows:
            if isinstance(item, dict):
                item.setdefault("undispellable", fallback_undispellable)
                item.setdefault("duration", default_duration)
                item["target"] = normalize_stat_effect_target(item.get("target"))
                item["count"] = max(1, safe_int(item.get("count", item.get("hits", 1)), 1))
        effects["post_attack_ability_damage"] = [
            item for item in post_attack_rows
            if isinstance(item, dict) and safe_float(item.get("ratio", item.get("percent")), 0.0) > 0
        ]
        if not effects["post_attack_ability_damage"]:
            effects.pop("post_attack_ability_damage", None)
    elif post_attack in (None, [], {}):
        effects.pop("post_attack_ability_damage", None)
    recast = effects.get("ability_recast")
    if isinstance(recast, (list, dict)):
        recast_rows = recast if isinstance(recast, list) else [recast]
        for item in recast_rows:
            if isinstance(item, dict):
                item.setdefault("undispellable", fallback_undispellable)
                item.setdefault("duration", default_duration)
                item["target"] = normalize_stat_effect_target(item.get("target"))
                item["count"] = max(1, safe_int(item.get("count", item.get("recasts", item.get("times", 1))), 1))
        effects["ability_recast"] = [
            item for item in recast_rows
            if isinstance(item, dict) and safe_int(item.get("count", item.get("recasts", item.get("times", 1))), 0) > 0
        ]
        if not effects["ability_recast"]:
            effects.pop("ability_recast", None)
    elif recast in (None, [], {}):
        effects.pop("ability_recast", None)
    normalize_guard_effects(effects, "dispel_guard", fallback_undispellable, default_duration)
    normalize_guard_effects(effects, "veil", fallback_undispellable, default_duration)
    normalize_guard_effects(effects, "mount", fallback_undispellable, default_duration)
    if "mount" in effects:
        effects.setdefault("veil", []).extend(effects.pop("mount"))
    if effects.get("flurry") in (None, False, {}):
        effects.pop("flurry", None)
    if effects.get("double_strike") in (None, False, {}):
        effects.pop("double_strike", None)
    if not effects:
        row.pop(key, None)


def normalize_guard_effects(
    effects: dict[str, Any],
    key: str,
    fallback_undispellable: bool,
    default_duration: int,
) -> None:
    raw = effects.get(key)
    if raw in (None, False, {}, []):
        effects.pop(key, None)
        return
    rows = raw if isinstance(raw, list) else [raw]
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            item = {}
        mode = str(item.get("mode", item.get("type", "")) or "")
        count = safe_int(item.get("count", item.get("uses", item.get("charges", 0))), 0)
        if mode == "count" or count > 0:
            count = max(1, count)
            duration = safe_int(item.get("duration"), -1) if "duration" in item else -1
            mode = "count"
        else:
            count = 0
            duration = safe_int(item.get("duration"), default_duration)
            if duration == 0:
                duration = default_duration or 1
            mode = "duration"
        normalized.append({
            "mode": mode,
            "target": normalize_stat_effect_target(item.get("target")),
            "duration": duration,
            "count": count,
            "undispellable": bool(item.get("undispellable", fallback_undispellable)),
        })
    effects[key] = normalized


def safe_effect_ratio(effect: dict[str, Any]) -> float:
    if "percent" in effect:
        return safe_float(effect.get("percent"), 0.0) / 100.0
    return safe_float(effect.get("ratio", effect.get("value")), 0.0)


def normalize_effect_actions(row: dict[str, Any], key: str) -> None:
    actions = row.get(key)
    if not isinstance(actions, list):
        row.pop(key, None)
        return
    normalized = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action", action.get("type", "")))
        if action_id not in EFFECT_ACTION_IDS:
            continue
        target = str(action.get("target", default_effect_action_target(action_id)) or default_effect_action_target(action_id))
        if target not in EFFECT_TARGET_IDS:
            continue
        action["action"] = action_id
        action["target"] = target
        action["count"] = max(1, safe_int(action.get("count"), 1))
        if action_id in STACK_EFFECT_ACTION_IDS:
            action["stack_effect_id"] = str(action.get("stack_effect_id", action.get("effect_id", "")) or "")
            action["value"] = max(1, safe_int(action.get("value", action.get("stacks", action.get("count"))), 1))
            action.pop("effect_id", None)
            action.pop("stacks", None)
        conditions = normalize_effect_action_stack_conditions(action.get("conditions", action.get("stack_conditions")))
        action.pop("stack_conditions", None)
        if conditions:
            action["conditions"] = conditions
        else:
            action.pop("conditions", None)
        normalized.append(action)
    row[key] = normalized
    if not row[key]:
        row.pop(key, None)


def default_effect_action_target(action_id: str) -> str:
    return "self" if action_id in STACK_EFFECT_ACTION_IDS else "enemy"


def normalize_effect_action_stack_conditions(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    conditions = []
    for condition in raw:
        if not isinstance(condition, dict):
            continue
        effect_id = str(condition.get("stack_effect_id", condition.get("effect_id", condition.get("id", ""))) or "")
        if not effect_id:
            continue
        conditions.append({
            "stack_effect_id": effect_id,
            "target": normalize_effect_action_stack_condition_target(condition.get("target")),
            "min_stacks": max(0, safe_int(condition.get("min_stacks", condition.get("min", condition.get("stacks"))), 1)),
            "max_stacks": safe_int(condition.get("max_stacks", condition.get("max")), -1),
        })
    return conditions


def normalize_effect_action_stack_condition_target(value: Any) -> str:
    target = str(value or "self")
    if target == "boss":
        return "boss"
    if target in {"player", "participant", "user"}:
        return "player"
    if target in {"me", "caster", "holder"}:
        return "self"
    if target in {"enemy", "opponent", "target"}:
        return "enemy"
    if target in {"ally", "allies", "party"}:
        return "allies"
    if target in {"opponents", "enemies"}:
        return "opponents"
    return "self"


def normalize_reward(reward: Any) -> None:
    if not isinstance(reward, dict):
        return
    reward.pop("gold", None)
    reward.pop("exp", None)
    reward.pop("stat_points", None)
    reward["items"] = [
        drop
        for drop in reward.get("items", [])
        if isinstance(drop, dict) and normalize_reward_item_drop(drop)
    ]
    reward["materials"] = [
        drop
        for drop in reward.get("materials", [])
        if isinstance(drop, dict) and normalize_reward_material_drop(drop)
    ]


def normalize_reward_item_drop(drop: dict[str, Any]) -> bool:
    drop.pop("rank", None)
    drop["chance"] = normalize_chance(drop.get("chance"), 0.0)
    drop["stars"] = max(0, safe_int(drop.get("stars"), 0))
    normalize_reward_count_fields(drop, default_min=1, default_max=1)
    return bool(drop.get("template_id") or drop.get("item_id") or drop.get("rarity"))


def normalize_reward_material_drop(drop: dict[str, Any]) -> bool:
    if not drop.get("id"):
        return False
    drop["chance"] = normalize_chance(drop.get("chance"), 1.0)
    normalize_reward_count_fields(drop, default_min=1, default_max=1)
    return True


def normalize_reward_count_fields(drop: dict[str, Any], *, default_min: int, default_max: int) -> None:
    minimum = max(1, safe_int(drop.get("min", drop.get("amount")), default_min))
    maximum = max(minimum, safe_int(drop.get("max"), default_max))
    drop["min"] = minimum
    drop["max"] = maximum
    drop.pop("amount", None)
    for prefix in ("owner", "participant"):
        chance_key = f"{prefix}_chance"
        if chance_key in drop:
            if drop[chance_key] in (None, ""):
                drop.pop(chance_key, None)
            else:
                drop[chance_key] = normalize_chance(drop.get(chance_key), 0.0)
        min_key = f"{prefix}_min"
        max_key = f"{prefix}_max"
        role_min = drop.get(min_key)
        role_max = drop.get(max_key)
        if role_min in (None, ""):
            drop.pop(min_key, None)
        else:
            drop[min_key] = max(1, safe_int(role_min, minimum))
        if role_max in (None, ""):
            drop.pop(max_key, None)
        else:
            lower = max(1, safe_int(drop.get(min_key), minimum))
            drop[max_key] = max(lower, safe_int(role_max, lower))


def normalize_chance(value: Any, default: float) -> float:
    chance = safe_float(value, default)
    if chance is None:
        chance = default
    return max(0.0, min(1.0, chance))


def normalize_enhancement(enhancement: dict[str, Any], max_enhancement_stars: int = 10) -> None:
    if not isinstance(enhancement, dict):
        return
    enhancement.setdefault("star_multiplier", {})
    enhancement.setdefault("odds", {})
    enhancement.setdefault("sell_rates", {})
    methods = enhancement.get("methods")
    if not isinstance(methods, list) or not methods:
        methods = [
            {
                "id": "gold",
                "name": "일반 강화",
                "gold": {"mode": "formula", "amount": 0},
                "materials": {},
                "odds": {"mode": "formula"},
            }
        ]
    enhancement["methods"] = [
        normalize_enhancement_method(method, index, max_enhancement_stars)
        for index, method in enumerate(methods, start=1)
        if isinstance(method, dict)
    ]


def normalize_enhancement_method(method: dict[str, Any], index: int, max_enhancement_stars: int = 10) -> dict[str, Any]:
    method["id"] = str(method.get("id") or f"method_{index}")
    method["name"] = str(method.get("name") or method["id"])
    method["description"] = str(method.get("description", ""))
    gold = method.get("gold", method.get("gold_cost", {}))
    if not isinstance(gold, dict):
        gold = {"mode": "fixed", "amount": safe_int(gold, 0)}
    mode = str(gold.get("mode", "formula") or "formula")
    if mode not in {"formula", "fixed", "none"}:
        mode = "formula"
    method["gold"] = {
        "mode": mode,
        "amount": max(0, safe_int(gold.get("amount", gold.get("value", 0)), 0)),
    }
    odds = method.get("odds", {})
    odds = odds if isinstance(odds, dict) else {}
    odds_mode = str(odds.get("mode", "formula") or "formula")
    if odds_mode not in {"formula", "fixed"}:
        odds_mode = "formula"
    normalized_odds = {"mode": odds_mode}
    for key in ("success", "fail", "destroy"):
        if odds.get(key) not in (None, ""):
            normalized_odds[key] = normalize_chance(odds.get(key), 0.0)
    method["odds"] = normalized_odds
    materials = method.get("materials", method.get("material_costs", {}))
    method["materials"] = {
        str(material_id): max(1, safe_int(amount, 1))
        for material_id, amount in (materials.items() if isinstance(materials, dict) else [])
        if str(material_id)
    }
    method["min_stars"] = max(0, safe_int(method.get("min_stars"), 0))
    method["max_stars"] = max(method["min_stars"] + 1, safe_int(method.get("max_stars"), max_enhancement_stars))
    method.pop("gold_cost", None)
    method.pop("material_costs", None)
    return method


def backup_content(retention: int = DEFAULT_BACKUP_RETENTION) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / timestamp
    suffix = 2
    while destination.exists():
        destination = BACKUP_DIR / f"{timestamp}_{suffix}"
        suffix += 1
    if CONTENT_DIR.exists():
        shutil.copytree(CONTENT_DIR, destination)
    prune_backups(retention)
    return destination


def prune_backups(retention: int = DEFAULT_BACKUP_RETENTION) -> None:
    retention = max(1, int(retention))
    if not BACKUP_DIR.exists():
        return
    backups = [
        path for path in BACKUP_DIR.iterdir()
        if path.is_dir()
    ]
    if len(backups) <= retention:
        return
    backups.sort(key=lambda path: (path.stat().st_mtime, path.name))
    for backup in backups[:-retention]:
        shutil.rmtree(backup, ignore_errors=True)


def write_split_dir(path: Path, rows: list[dict[str, Any]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    desired = set()
    for index, row in enumerate(rows, start=1):
        row_id = str(row["id"])
        row.setdefault("sort_order", index * 10)
        desired.add(f"{row_id}.json")
        write_json(path / f"{row_id}.json", row)
    for file in path.glob("*.json"):
        if file.name not in desired:
            file.unlink()


def validate_content(content: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rarities = set(content.get("rarities", {}).get("order", []))
    stat_ids = set(content.get("stats", {}).get("order", []))
    items = ensure_unique_ids(content.get("items", []), "item", errors)
    materials = ensure_unique_ids(content.get("materials", []), "material", errors)
    jobs = ensure_unique_ids(content.get("jobs", []), "job", errors)
    skills = ensure_unique_ids(content.get("skills", []), "skill", errors)
    stack_effects = ensure_unique_ids(content.get("stack_effects", []), "stack effect", errors)
    recipes = ensure_unique_ids(content.get("crafting_recipes", []), "crafting recipe", errors)
    dungeons = ensure_unique_ids(content.get("dungeons", []), "dungeon", errors)
    bosses = ensure_unique_ids(content.get("bosses", []), "boss", errors)
    validate_settings(content.get("settings", {}), errors)
    validate_enhancement(content.get("enhancement", {}), materials, errors)

    for item in content.get("items", []):
        check_rarity(item.get("rarity"), rarities, f"item {item.get('id')}", errors)
        validate_fixed_stats(item.get("fixed_stats"), item.get("stats"), f"item {item.get('id')} fixed stats", errors)
        validate_stat_effects(item.get("stat_effects"), stat_ids, f"item {item.get('id')} stat effects", errors)
        validate_combat_effects(item.get("effects"), f"item {item.get('id')} effects", errors)
    for material in content.get("materials", []):
        check_rarity(material.get("rarity"), rarities, f"material {material.get('id')}", errors)
    for job in content.get("jobs", []):
        parent_id = str(job.get("parent_id", ""))
        if parent_id and parent_id not in jobs:
            errors.append(f"job {job.get('id')} parent not found: {parent_id}")
        validate_stat_effects(job.get("stat_effects"), stat_ids, f"job {job.get('id')} stat effects", errors)
        validate_combat_effects(job.get("effects"), f"job {job.get('id')} effects", errors)
    for effect in content.get("stack_effects", []):
        validate_stack_effect(effect, stat_ids, f"stack effect {effect.get('id')}", errors)
    for skill in content.get("skills", []):
        for job_id in skill.get("job_ids", []):
            if job_id not in jobs:
                errors.append(f"skill {skill.get('id')} job not found: {job_id}")
        validate_stat_effects(skill.get("player_stat_effects"), stat_ids, f"skill {skill.get('id')} player stat effects", errors)
        validate_stat_effects(skill.get("enemy_stat_effects"), stat_ids, f"skill {skill.get('id')} enemy stat effects", errors)
        validate_combat_effects(skill.get("player_effects", skill.get("effects")), f"skill {skill.get('id')} player effects", errors)
        validate_combat_effects(skill.get("enemy_effects"), f"skill {skill.get('id')} enemy effects", errors)
        validate_effect_actions(skill.get("effect_actions"), f"skill {skill.get('id')} effect actions", errors, stack_effects)
        validate_heal_cap(skill.get("heal_cap"), f"skill {skill.get('id')} heal cap", errors)
        if str(skill.get("heal_target", "self") or "self") not in STAT_EFFECT_TARGET_IDS:
            errors.append(f"skill {skill.get('id')} heal target is invalid")
    for recipe in content.get("crafting_recipes", []):
        if recipe.get("result_item_id") not in items:
            errors.append(f"recipe {recipe.get('id')} result item not found: {recipe.get('result_item_id')}")
        for material_id in recipe.get("materials", {}):
            if material_id not in materials:
                errors.append(f"recipe {recipe.get('id')} material not found: {material_id}")
    for dungeon in content.get("dungeons", []):
        enemy_ids = ensure_unique_ids(dungeon.get("enemies", []), f"dungeon {dungeon.get('id')} enemy", errors)
        if not enemy_ids:
            errors.append(f"dungeon {dungeon.get('id')} has no enemies")
        for enemy in dungeon.get("enemies", []):
            validate_reward(enemy.get("rewards", {}), items, materials, rarities, f"enemy {enemy.get('id')} rewards", errors)
    for boss in content.get("bosses", []):
        pattern_ids = ensure_unique_ids(boss.get("patterns", []), f"boss {boss.get('id')} pattern", errors)
        for pattern in boss.get("patterns", []):
            if isinstance(pattern, dict):
                validate_boss_pattern(pattern, f"boss {boss.get('id')} pattern", stat_ids, errors, stack_effects)
        warning_pattern_rows = [
            warning.get("pattern")
            for warning in boss.get("warnings", [])
            if isinstance(warning.get("pattern"), dict)
        ]
        warning_pattern_ids = ensure_unique_ids(
            warning_pattern_rows,
            f"boss {boss.get('id')} warning failure effect",
            errors,
        )
        success_pattern_rows = [
            warning.get("success_pattern")
            for warning in boss.get("warnings", [])
            if isinstance(warning.get("success_pattern"), dict)
        ]
        success_pattern_ids = ensure_unique_ids(
            success_pattern_rows,
            f"boss {boss.get('id')} warning success effect",
            errors,
        )
        variant_pattern_rows = [
            variant.get("pattern")
            for warning in boss.get("warnings", [])
            for variant in warning.get("failure_variants", [])
            if isinstance(variant, dict) and isinstance(variant.get("pattern"), dict)
        ]
        variant_pattern_ids = ensure_unique_ids(
            variant_pattern_rows,
            f"boss {boss.get('id')} warning failure variant",
            errors,
        )
        hp_effect_pattern_rows = [
            effect.get("pattern")
            for effect in boss.get("hp_effects", [])
            if isinstance(effect, dict) and isinstance(effect.get("pattern"), dict)
        ]
        hp_effect_pattern_ids = ensure_unique_ids(
            hp_effect_pattern_rows,
            f"boss {boss.get('id')} hp instant effect",
            errors,
        )
        for pattern_id in pattern_ids & warning_pattern_ids:
            errors.append(f"boss {boss.get('id')} duplicate pattern id: {pattern_id}")
        for pattern_id in (pattern_ids | warning_pattern_ids) & success_pattern_ids:
            errors.append(f"boss {boss.get('id')} duplicate pattern id: {pattern_id}")
        for pattern_id in (pattern_ids | warning_pattern_ids | success_pattern_ids) & variant_pattern_ids:
            errors.append(f"boss {boss.get('id')} duplicate pattern id: {pattern_id}")
        for pattern_id in (pattern_ids | warning_pattern_ids | success_pattern_ids | variant_pattern_ids) & hp_effect_pattern_ids:
            errors.append(f"boss {boss.get('id')} duplicate pattern id: {pattern_id}")
        warning_ids = ensure_unique_ids(boss.get("warnings", []), f"boss {boss.get('id')} warning", errors)
        for warning in boss.get("warnings", []):
            validate_boss_warning_template(
                warning,
                pattern_ids,
                warning_ids,
                stat_ids,
                f"boss {boss.get('id')} warning",
                errors,
                stack_effects,
            )
        for warning in boss.get("hp_warnings", []):
            validate_warning_trigger(warning, warning_ids, pattern_ids, stat_ids, f"boss {boss.get('id')} hp warning", errors, stack_effects)
        validate_boss_hp_locks(
            boss.get("hp_locks", []),
            f"boss {boss.get('id')} hp locks",
            errors,
        )
        validate_boss_hp_effects(
            boss.get("hp_effects", []),
            stat_ids,
            f"boss {boss.get('id')} hp instant effects",
            errors,
            stack_effects,
        )
        for warning in boss.get("ct", {}).get("warnings_by_hp", []):
            validate_warning_trigger(warning, warning_ids, pattern_ids, stat_ids, f"boss {boss.get('id')} ct warning", errors, stack_effects)
        skull_system = boss.get("skull_system")
        if isinstance(skull_system, dict) and skull_system.get("enabled", True):
            red_thread_warning_id = str(skull_system.get("red_thread_warning_id", "red_thread") or "")
            if red_thread_warning_id and red_thread_warning_id not in warning_ids:
                errors.append(
                    f"boss {boss.get('id')} skull system red thread warning not found: {red_thread_warning_id}"
                )
        validate_boss_stack_effects(
            boss.get("stack_effects", []),
            content.get("stack_effects", []),
            stack_effects,
            f"boss {boss.get('id')} stack effects",
            errors,
        )
        validate_reward(boss.get("rewards", {}), items, materials, rarities, f"boss {boss.get('id')} rewards", errors)
    validate_gacha(content.get("gacha", {}), items, materials, rarities, errors)

    for label, ids in (("skills", skills), ("recipes", recipes), ("dungeons", dungeons), ("bosses", bosses)):
        if not ids:
            errors.append(f"no {label} configured")
    return errors


def ensure_unique_ids(rows: Any, label: str, errors: list[str]) -> set[str]:
    if not isinstance(rows, list):
        errors.append(f"{label} list is not an array")
        return set()
    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("id", ""))
        if not row_id:
            errors.append(f"{label} missing id")
            continue
        if not ID_RE.match(row_id):
            errors.append(f"{label} has invalid id: {row_id}")
        if row_id in seen:
            errors.append(f"{label} duplicate id: {row_id}")
        seen.add(row_id)
    return seen


def check_rarity(rarity: Any, rarities: set[str], label: str, errors: list[str]) -> None:
    if str(rarity) not in rarities:
        errors.append(f"{label} rarity not found: {rarity}")


def validate_stack_effect(effect: dict[str, Any], stat_ids: set[str], label: str, errors: list[str]) -> None:
    max_stacks = safe_int(effect.get("max_stacks", effect.get("max")), 0)
    if max_stacks < 1:
        errors.append(f"{label} max stacks must be at least 1")
    tiers = effect.get("tiers", [])
    if not isinstance(tiers, list):
        errors.append(f"{label} tiers is not an array")
        return
    seen_stacks: set[int] = set()
    for index, tier in enumerate(tiers, start=1):
        if not isinstance(tier, dict):
            errors.append(f"{label} tier {index} is not an object")
            continue
        stack = safe_int(tier.get("stack"), 0)
        if stack < 1 or stack > max_stacks:
            errors.append(f"{label} tier {index} stack out of range: {stack}")
        if stack in seen_stacks:
            errors.append(f"{label} duplicate tier stack: {stack}")
        seen_stacks.add(stack)
        validate_stat_effects(tier.get("stat_effects"), stat_ids, f"{label} tier {stack} stat effects", errors)
        validate_combat_effects(tier.get("effects"), f"{label} tier {stack} effects", errors)
    conditions = effect.get("conditions", [])
    if conditions in (None, []):
        return
    if not isinstance(conditions, list):
        errors.append(f"{label} conditions is not an array")
        return
    for index, condition in enumerate(conditions, start=1):
        if not isinstance(condition, dict):
            errors.append(f"{label} condition {index} is not an object")
            continue
        objective = str(condition.get("objective", ""))
        if objective not in STACK_CONDITION_OBJECTIVE_IDS:
            errors.append(f"{label} condition {index} objective not found: {objective}")
        target = str(condition.get("target", "self") or "self")
        if objective in {"warning_success", "warning_failure"}:
            if target not in {"none", "self", "opponent"}:
                errors.append(f"{label} condition {index} target not found: {target}")
        elif target not in {"self", "opponent"}:
            errors.append(f"{label} condition {index} target not found: {target}")
        operation = str(condition.get("operation", "increase") or "increase")
        if operation not in {"increase", "decrease", "set", "remove", "max"}:
            errors.append(f"{label} condition {index} operation not found: {operation}")
        if safe_int(condition.get("value"), 1) < 1:
            errors.append(f"{label} condition {index} value must be at least 1")
        if safe_int(condition.get("required"), 1) < 1:
            errors.append(f"{label} condition {index} required must be at least 1")
        if objective == "hits" and safe_int(condition.get("min_damage"), 0) < 0:
            errors.append(f"{label} condition {index} min damage must be non-negative")


def validate_boss_stack_effects(
    rows: Any,
    stack_effect_rows: list[dict[str, Any]],
    stack_effect_ids: set[str],
    label: str,
    errors: list[str],
) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    max_stacks_by_id = {
        str(row.get("id", "")): max(1, safe_int(row.get("max_stacks", row.get("max")), 1))
        for row in stack_effect_rows
        if isinstance(row, dict)
    }
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        effect_id = str(row.get("stack_effect_id", row.get("id", row.get("effect_id", ""))) or "")
        if effect_id not in stack_effect_ids:
            errors.append(f"{label} {index} stack effect not found: {effect_id}")
            continue
        if effect_id in seen:
            errors.append(f"{label} {index} duplicate stack effect: {effect_id}")
        seen.add(effect_id)
        initial_stacks = safe_int(row.get("initial_stacks", row.get("stacks")), 0)
        if initial_stacks < 0 or initial_stacks > max_stacks_by_id.get(effect_id, 1):
            errors.append(f"{label} {index} initial stacks out of range: {initial_stacks}")


def validate_boss_hp_effects(
    rows: Any,
    stat_ids: set[str],
    label: str,
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        thresholds = row.get("thresholds")
        if isinstance(thresholds, list):
            if not thresholds:
                errors.append(f"{label} {index} has no thresholds")
            for threshold_index, threshold_raw in enumerate(thresholds, start=1):
                threshold = safe_float(threshold_raw, None)
                if threshold is None or threshold < 0 or threshold > 1:
                    errors.append(f"{label} {index} threshold {threshold_index} out of range")
        else:
            threshold = safe_float(row.get("threshold"), None)
            if threshold is None or threshold < 0 or threshold > 1:
                errors.append(f"{label} {index} threshold out of range")
        pattern = row.get("pattern")
        if not isinstance(pattern, dict):
            errors.append(f"{label} {index} missing pattern")
            continue
        validate_boss_pattern(pattern, f"{label} {index} pattern", stat_ids, errors, stack_effect_ids)


def validate_boss_hp_locks(rows: Any, label: str, errors: list[str]) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    seen: set[float] = set()
    for index, raw in enumerate(rows, start=1):
        value = raw.get("threshold", raw.get("hp", raw.get("value"))) if isinstance(raw, dict) else raw
        threshold = safe_float(value, None)
        if threshold is None or threshold <= 0 or threshold >= 1:
            errors.append(f"{label} {index} threshold out of range")
            continue
        normalized = round(threshold, 6)
        if normalized in seen:
            errors.append(f"{label} {index} duplicate threshold: {threshold}")
        seen.add(normalized)


def validate_boss_warning_template(
    warning: dict[str, Any],
    pattern_ids: set[str],
    warning_ids: set[str],
    stat_ids: set[str],
    label: str,
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    pattern = warning.get("pattern")
    if isinstance(pattern, dict):
        validate_boss_pattern(pattern, f"{label} {warning.get('id')} failure effect", stat_ids, errors, stack_effect_ids)
    else:
        # Legacy shape: warning template references a shared top-level pattern.
        pattern_id = str(warning.get("pattern_id", ""))
        if pattern_id not in pattern_ids:
            errors.append(f"{label} {warning.get('id')} pattern not found: {pattern_id}")
    if safe_int(warning.get("turns"), 1) < 1:
        errors.append(f"{label} {warning.get('id')} turns must be at least 1")
    for key, name in (
        ("success_warning_id", "success warning"),
        ("failure_warning_id", "failure warning"),
    ):
        linked_warning_id = str(warning.get(key, "") or "")
        if linked_warning_id and linked_warning_id not in warning_ids:
            errors.append(f"{label} {warning.get('id')} {name} not found: {linked_warning_id}")
    validate_warning_activation_conditions(
        warning.get("activation_conditions"),
        f"{label} {warning.get('id')} activation conditions",
        errors,
        stack_effect_ids,
    )
    validate_warning_objectives(warning, f"{label} {warning.get('id')}", errors)
    success_pattern = warning.get("success_pattern")
    if success_pattern is not None:
        if not isinstance(success_pattern, dict):
            errors.append(f"{label} {warning.get('id')} success effect is not an object")
        else:
            validate_boss_pattern(success_pattern, f"{label} {warning.get('id')} success effect", stat_ids, errors, stack_effect_ids)
    validate_warning_failure_variants(
        warning.get("failure_variants"),
        stat_ids,
        f"{label} {warning.get('id')} failure variants",
        errors,
        stack_effect_ids,
    )


def validate_boss_pattern(
    pattern: dict[str, Any],
    label: str,
    stat_ids: set[str],
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    pattern_id = str(pattern.get("id", ""))
    if not pattern_id:
        errors.append(f"{label} missing id")
    elif not ID_RE.match(pattern_id):
        errors.append(f"{label} has invalid id: {pattern_id}")
    if not str(pattern.get("name", "")):
        errors.append(f"{label} missing name")
    validate_stat_effects(pattern.get("player_stat_effects"), stat_ids, f"{label} player stat effects", errors)
    validate_stat_effects(pattern.get("boss_stat_effects"), stat_ids, f"{label} boss stat effects", errors)
    validate_combat_effects(pattern.get("player_effects"), f"{label} player effects", errors)
    validate_combat_effects(pattern.get("boss_effects", pattern.get("effects")), f"{label} boss effects", errors)
    validate_effect_actions(pattern.get("effect_actions"), f"{label} effect actions", errors, stack_effect_ids)
    validate_plain_damage(pattern.get("plain_damage"), f"{label} plain damage", errors)
    hp_loss_ratio = safe_float(pattern.get("self_hp_loss_ratio"), 0.0)
    if hp_loss_ratio < 0:
        errors.append(f"{label} self hp loss ratio must be non-negative")


def validate_plain_damage(raw: Any, label: str, errors: list[str]) -> None:
    if raw in (None, []):
        return
    if not isinstance(raw, dict):
        errors.append(f"{label} is not an object")
        return
    mode = str(raw.get("mode", "none") or "none")
    if mode not in PLAIN_DAMAGE_MODES:
        errors.append(f"{label} mode is invalid: {mode}")
    value = safe_float(raw.get("value"), None)
    if value is None or value < 0:
        errors.append(f"{label} value must be non-negative")


def validate_warning_failure_variants(
    rows: Any,
    stat_ids: set[str],
    label: str,
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    for index, variant in enumerate(rows, start=1):
        if not isinstance(variant, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        conditions = variant.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            errors.append(f"{label} {index} has no stack conditions")
        else:
            for condition_index, condition in enumerate(conditions, start=1):
                if not isinstance(condition, dict):
                    errors.append(f"{label} {index} condition {condition_index} is not an object")
                    continue
                effect_id = str(condition.get("stack_effect_id", ""))
                if effect_id not in stack_effect_ids:
                    errors.append(f"{label} {index} condition {condition_index} stack effect not found: {effect_id}")
                target = str(condition.get("target", "boss") or "boss")
                if target not in {"boss", "player"}:
                    errors.append(f"{label} {index} condition {condition_index} target is invalid: {target}")
                min_stacks = safe_int(condition.get("min_stacks"), 0)
                max_stacks = safe_int(condition.get("max_stacks"), -1)
                if min_stacks < 0:
                    errors.append(f"{label} {index} condition {condition_index} min stacks must be non-negative")
                if max_stacks >= 0 and max_stacks < min_stacks:
                    errors.append(f"{label} {index} condition {condition_index} max stacks must be at least min stacks")
        pattern = variant.get("pattern")
        if not isinstance(pattern, dict):
            errors.append(f"{label} {index} missing pattern")
            continue
        validate_boss_pattern(pattern, f"{label} {index} pattern", stat_ids, errors, stack_effect_ids)


def validate_warning_activation_conditions(
    rows: Any,
    label: str,
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    for index, condition in enumerate(rows, start=1):
        if not isinstance(condition, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        kind = str(condition.get("kind", "") or "")
        if kind not in WARNING_ACTIVATION_CONDITION_IDS:
            errors.append(f"{label} {index} kind is invalid: {kind}")
            continue
        if kind == "stack":
            effect_id = str(condition.get("stack_effect_id", "") or "")
            if effect_id not in stack_effect_ids:
                errors.append(f"{label} {index} stack effect not found: {effect_id}")
            target = str(condition.get("target", "boss") or "boss")
            if target not in WARNING_ACTIVATION_STACK_TARGET_IDS:
                errors.append(f"{label} {index} target is invalid: {target}")
            min_stacks = safe_int(condition.get("min_stacks"), 0)
            max_stacks = safe_int(condition.get("max_stacks"), -1)
            if min_stacks < 0:
                errors.append(f"{label} {index} min stacks must be non-negative")
            if max_stacks >= 0 and max_stacks < min_stacks:
                errors.append(f"{label} {index} max stacks must be at least min stacks")
        elif kind == "turn_multiple":
            if safe_int(condition.get("multiple"), 0) < 1:
                errors.append(f"{label} {index} multiple must be at least 1")
        elif kind == "turn_range":
            min_turn = safe_int(condition.get("min_turn"), 1)
            max_turn = safe_int(condition.get("max_turn"), -1)
            if min_turn < 1:
                errors.append(f"{label} {index} min turn must be at least 1")
            if max_turn >= 0 and max_turn < min_turn:
                errors.append(f"{label} {index} max turn must be at least min turn")
        elif kind == "boss_hp_ratio":
            min_ratio = safe_float(condition.get("min_ratio"), 0.0)
            max_ratio = safe_float(condition.get("max_ratio"), 1.0)
            if min_ratio < 0 or max_ratio > 1 or max_ratio < min_ratio:
                errors.append(f"{label} {index} hp ratio range is invalid")


def validate_warning_trigger(
    warning: dict[str, Any],
    warning_ids: set[str],
    pattern_ids: set[str],
    stat_ids: set[str],
    label: str,
    errors: list[str],
    stack_effect_ids: set[str],
) -> None:
    raw_warning_ids = warning.get("warning_ids")
    if raw_warning_ids is None:
        raw_warning_ids = [warning.get("warning_id", "")]
    elif not isinstance(raw_warning_ids, list):
        errors.append(f"{label} warning ids is not an array")
        raw_warning_ids = []
    trigger_warning_ids = [
        str(warning_id or "")
        for warning_id in raw_warning_ids
        if str(warning_id or "")
    ]
    if trigger_warning_ids:
        for warning_id in trigger_warning_ids:
            if warning_id not in warning_ids:
                errors.append(f"{label} warning not found: {warning_id}")
        return

    # Legacy shape: HP/CT trigger owns its condition and failure pattern directly.
    validate_warning_objectives(warning, label, errors)
    pattern = warning.get("pattern")
    if isinstance(pattern, dict):
        validate_boss_pattern(pattern, f"{label} pattern", stat_ids, errors, stack_effect_ids)
        return
    pattern_id = str(warning.get("pattern_id", ""))
    if pattern_id not in pattern_ids:
        errors.append(f"{label} pattern not found: {pattern_id}")


def validate_warning_objectives(warning: dict[str, Any], label: str, errors: list[str]) -> None:
    objectives = warning.get("objectives")
    if isinstance(objectives, list):
        if not objectives:
            errors.append(f"{label} has no objectives")
        for objective in objectives:
            if not isinstance(objective, dict):
                errors.append(f"{label} objective is not an object")
                continue
            kind = str(objective.get("objective", ""))
            if kind not in OBJECTIVE_IDS:
                errors.append(f"{label} objective not found: {kind}")
            if safe_int(objective.get("required"), 0) < 1:
                errors.append(f"{label} objective required must be at least 1")
            if kind == "hits" and safe_int(objective.get("min_damage"), 0) < 0:
                errors.append(f"{label} objective min damage must be non-negative")
        return

    kind = str(warning.get("objective", ""))
    if kind and kind not in OBJECTIVE_IDS:
        errors.append(f"{label} objective not found: {kind}")
    if safe_int(warning.get("required"), 1) < 1:
        errors.append(f"{label} required must be at least 1")
    if kind == "hits" and safe_int(warning.get("min_damage"), 0) < 0:
        errors.append(f"{label} min damage must be non-negative")


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def validate_stat_effects(rows: Any, stat_ids: set[str], label: str, errors: list[str]) -> None:
    if rows in (None, []):
        return
    if not isinstance(rows, list):
        errors.append(f"{label} is not an array")
        return
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        stat = str(row.get("stat", row.get("key", "")))
        if stat not in stat_ids:
            errors.append(f"{label} {index} stat not found: {stat}")
        target = str(row.get("target", "self") or "self")
        if target not in STAT_EFFECT_TARGET_IDS:
            errors.append(f"{label} {index} target not found: {target}")
        if safe_float(row.get("value"), None) is None:
            errors.append(f"{label} {index} value is not a number")
        if safe_int(row.get("duration"), None) is None:
            errors.append(f"{label} {index} duration is not a number")

def validate_fixed_stats(raw: Any, stats: Any, label: str, errors: list[str]) -> None:
    if raw in (None, []):
        return
    if not isinstance(raw, list):
        errors.append(f"{label} is not an array")
        return
    if not isinstance(stats, dict):
        errors.append(f"{label} cannot be used without stats")
        return
    stat_keys = {str(key) for key in stats}
    for stat in raw:
        stat_id = str(stat)
        if stat_id not in stat_keys:
            errors.append(f"{label} stat not found on item: {stat_id}")


def validate_heal_cap(cap: Any, label: str, errors: list[str]) -> None:
    if cap in (None, {}):
        return
    if not isinstance(cap, dict):
        errors.append(f"{label} is not an object")
        return
    mode = str(cap.get("mode", "none"))
    if mode not in HEAL_CAP_MODES:
        errors.append(f"{label} mode not found: {mode}")
    if mode == "none":
        return
    value = safe_float(cap.get("value"), None)
    if value is None:
        errors.append(f"{label} value is not a number")
    elif value <= 0:
        errors.append(f"{label} value must be positive")


def validate_settings(settings: Any, errors: list[str]) -> None:
    if not isinstance(settings, dict):
        errors.append("settings is not an object")
        return
    for key in ("daily_explores", "max_equipped_items", "max_equipped_skills", "max_enhancement_stars"):
        value = safe_int(settings.get(key), None)
        if value is None:
            errors.append(f"settings {key} is not a number")
        elif value < 1:
            errors.append(f"settings {key} must be at least 1")
    level_multipliers = settings.get("level_damage_multipliers", [])
    if not isinstance(level_multipliers, list):
        errors.append("settings level_damage_multipliers is not an array")
    else:
        for index, raw_value in enumerate(level_multipliers):
            value = safe_float(raw_value, None)
            if value is None:
                errors.append(f"settings level_damage_multipliers {index} is not a number")
            elif value < 0:
                errors.append(f"settings level_damage_multipliers {index} must be non-negative")
    explore_combat = settings.get("explore_combat", {})
    if explore_combat is not None and not isinstance(explore_combat, dict):
        errors.append("settings explore_combat is not an object")
    elif isinstance(explore_combat, dict):
        for key in ("basic_attack_multiplier", "skill_damage_multiplier"):
            value = safe_float(explore_combat.get(key), None)
            if value is None:
                errors.append(f"settings explore_combat {key} is not a number")
            elif value < 0:
                errors.append(f"settings explore_combat {key} must be non-negative")
        defense_bonus = safe_float(explore_combat.get("player_defense_bonus"), None)
        if defense_bonus is None:
            errors.append("settings explore_combat player_defense_bonus is not a number")
    multipliers = settings.get("reward_multipliers", {})
    if not isinstance(multipliers, dict):
        errors.append("settings reward_multipliers is not an object")
        return
    for key in ("win_min", "win_max", "loss"):
        value = safe_float(multipliers.get(key), None)
        if value is None:
            errors.append(f"settings reward_multipliers {key} is not a number")
        elif value < 0:
            errors.append(f"settings reward_multipliers {key} must be non-negative")


def validate_enhancement(enhancement: Any, material_ids: set[str], errors: list[str]) -> None:
    if not isinstance(enhancement, dict):
        errors.append("enhancement is not an object")
        return
    methods = enhancement.get("methods", [])
    if not isinstance(methods, list):
        errors.append("enhancement methods is not an array")
        return
    seen: set[str] = set()
    for index, method in enumerate(methods, start=1):
        if not isinstance(method, dict):
            errors.append(f"enhancement method {index} is not an object")
            continue
        method_id = str(method.get("id", ""))
        if not method_id:
            errors.append(f"enhancement method {index} id is required")
        elif method_id in seen:
            errors.append(f"enhancement method duplicate id: {method_id}")
        seen.add(method_id)
        gold = method.get("gold", {})
        if isinstance(gold, dict) and str(gold.get("mode", "formula")) not in {"formula", "fixed", "none"}:
            errors.append(f"enhancement method {method_id} gold mode is invalid")
        odds = method.get("odds", {})
        if isinstance(odds, dict) and str(odds.get("mode", "formula")) not in {"formula", "fixed"}:
            errors.append(f"enhancement method {method_id} odds mode is invalid")
        min_stars = safe_int(method.get("min_stars"), 0)
        max_stars = safe_int(method.get("max_stars"), 10)
        if min_stars < 0:
            errors.append(f"enhancement method {method_id} min stars must be non-negative")
        if max_stars <= min_stars:
            errors.append(f"enhancement method {method_id} max stars must be greater than min stars")
        materials = method.get("materials", {})
        if not isinstance(materials, dict):
            errors.append(f"enhancement method {method_id} materials is not an object")
            continue
        for material_id, amount in materials.items():
            if material_id not in material_ids:
                errors.append(f"enhancement method {method_id} material not found: {material_id}")
            if safe_int(amount, 0) < 1:
                errors.append(f"enhancement method {method_id} material amount must be at least 1: {material_id}")


def validate_combat_effects(effects: Any, label: str, errors: list[str]) -> None:
    if effects in (None, {}):
        return
    if not isinstance(effects, dict):
        errors.append(f"{label} is not an object")
        return

    flurry = effects.get("flurry")
    if isinstance(flurry, dict):
        if safe_int(flurry.get("count"), 0) < 2:
            errors.append(f"{label} flurry count must be at least 2")
        validate_effect_duration(flurry, f"{label} flurry", errors)
        validate_effect_target(flurry, f"{label} flurry", errors)
    elif flurry not in (None, False):
        if isinstance(flurry, bool):
            pass
        elif safe_int(flurry, 0) < 2:
            errors.append(f"{label} flurry count must be at least 2")

    double_strike = effects.get("double_strike")
    if isinstance(double_strike, dict):
        if safe_int(double_strike.get("count", 2), 2) < 2:
            errors.append(f"{label} double strike count must be at least 2")
        validate_effect_duration(double_strike, f"{label} double strike", errors)
        validate_effect_target(double_strike, f"{label} double strike", errors)

    bonus_damage = effects.get("bonus_damage", [])
    bonus_rows = bonus_damage if isinstance(bonus_damage, list) else [bonus_damage]
    for index, bonus in enumerate(bonus_rows, start=1):
        validate_ratio_effect(bonus, f"{label} bonus damage {index}", errors)

    critical_reinforce = effects.get("critical_reinforce", [])
    reinforce_rows = critical_reinforce if isinstance(critical_reinforce, list) else [critical_reinforce]
    for index, reinforce in enumerate(reinforce_rows, start=1):
        validate_ratio_effect(reinforce, f"{label} critical reinforce {index}", errors)

    final_damage = effects.get("final_damage", [])
    final_damage_rows = final_damage if isinstance(final_damage, list) else [final_damage]
    for index, effect in enumerate(final_damage_rows, start=1):
        validate_signed_ratio_effect(effect, f"{label} final damage {index}", errors)

    post_attack = effects.get("post_attack_ability_damage", [])
    post_attack_rows = post_attack if isinstance(post_attack, list) else [post_attack]
    for index, effect in enumerate(post_attack_rows, start=1):
        validate_ratio_effect(effect, f"{label} post attack ability damage {index}", errors)
        if isinstance(effect, dict) and safe_int(effect.get("count", effect.get("hits", 1)), 0) < 1:
            errors.append(f"{label} post attack ability damage {index} count must be at least 1")

    ability_recast = effects.get("ability_recast", [])
    recast_rows = ability_recast if isinstance(ability_recast, list) else [ability_recast]
    for index, effect in enumerate(recast_rows, start=1):
        validate_count_effect(effect, f"{label} ability recast {index}", errors)

    for key, text in (("dispel_guard", "dispel guard"), ("veil", "veil"), ("mount", "veil")):
        rows = effects.get(key, [])
        guard_rows = rows if isinstance(rows, list) else [rows]
        for index, effect in enumerate(guard_rows, start=1):
            validate_guard_effect(effect, f"{label} {text} {index}", errors)


def validate_ratio_effect(effect: Any, label: str, errors: list[str]) -> None:
    if effect in (None, [], {}):
        return
    if isinstance(effect, dict):
        validate_effect_duration(effect, label, errors)
        validate_effect_target(effect, label, errors)
        if "percent" in effect:
            ratio = safe_float(effect.get("percent"), None)
        else:
            ratio = safe_float(effect.get("ratio", effect.get("value")), None)
    else:
        ratio = safe_float(effect, None)
    if ratio is None:
        errors.append(f"{label} ratio is not a number")
    elif ratio <= 0:
        errors.append(f"{label} ratio must be positive")


def validate_count_effect(effect: Any, label: str, errors: list[str]) -> None:
    if effect in (None, [], {}):
        return
    if isinstance(effect, dict):
        validate_effect_duration(effect, label, errors)
        validate_effect_target(effect, label, errors)
        count = safe_int(effect.get("count", effect.get("recasts", effect.get("times"))), None)
    else:
        count = safe_int(effect, None)
    if count is None:
        errors.append(f"{label} count is not a number")
    elif count < 1:
        errors.append(f"{label} count must be at least 1")


def validate_signed_ratio_effect(effect: Any, label: str, errors: list[str]) -> None:
    if effect in (None, [], {}):
        return
    if isinstance(effect, dict):
        validate_effect_duration(effect, label, errors)
        validate_effect_target(effect, label, errors)
        if "percent" in effect:
            ratio = safe_float(effect.get("percent"), None)
            if ratio is not None:
                ratio /= 100.0
        else:
            ratio = safe_float(effect.get("ratio", effect.get("value")), None)
    else:
        ratio = safe_float(effect, None)
        if ratio is not None and abs(ratio) > 1:
            ratio /= 100.0
    if ratio is None:
        errors.append(f"{label} ratio is not a number")
    elif ratio <= -1:
        errors.append(f"{label} ratio must be greater than -1")


def validate_guard_effect(effect: Any, label: str, errors: list[str]) -> None:
    if effect in (None, [], {}):
        return
    if not isinstance(effect, dict):
        errors.append(f"{label} is not an object")
        return
    validate_effect_target(effect, label, errors)
    mode = str(effect.get("mode", effect.get("type", "")) or "")
    count = safe_int(effect.get("count", effect.get("uses", effect.get("charges", 0))), 0)
    if mode == "count" or count > 0:
        if count < 1:
            errors.append(f"{label} count must be at least 1")
        return
    validate_effect_duration(effect, label, errors)


def validate_effect_target(effect: dict[str, Any], label: str, errors: list[str]) -> None:
    target = str(effect.get("target", "self") or "self")
    if target not in STAT_EFFECT_TARGET_IDS:
        errors.append(f"{label} target is invalid")


def validate_effect_duration(effect: dict[str, Any], label: str, errors: list[str]) -> None:
    if "duration" not in effect:
        return
    if safe_int(effect.get("duration"), None) is None:
        errors.append(f"{label} duration is not a number")


def validate_effect_actions(
    actions: Any,
    label: str,
    errors: list[str],
    stack_effect_ids: set[str] | None = None,
) -> None:
    if actions in (None, []):
        return
    if not isinstance(actions, list):
        errors.append(f"{label} is not an array")
        return
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            errors.append(f"{label} {index} is not an object")
            continue
        action_id = str(action.get("action", action.get("type", "")))
        if action_id not in EFFECT_ACTION_IDS:
            errors.append(f"{label} {index} action not found: {action_id}")
        target = str(action.get("target", "enemy"))
        if target not in EFFECT_TARGET_IDS:
            errors.append(f"{label} {index} target not found: {target}")
        if safe_int(action.get("count"), 1) < 1:
            errors.append(f"{label} {index} count must be at least 1")
        if action_id in STACK_EFFECT_ACTION_IDS:
            effect_id = str(action.get("stack_effect_id", action.get("effect_id", "")) or "")
            if not effect_id:
                errors.append(f"{label} {index} stack effect is required")
            elif stack_effect_ids is not None and effect_id not in stack_effect_ids:
                errors.append(f"{label} {index} stack effect not found: {effect_id}")
            if safe_int(action.get("value", action.get("stacks", 1)), 1) < 1:
                errors.append(f"{label} {index} value must be at least 1")
        conditions = action.get("conditions")
        if conditions in (None, []):
            continue
        if not isinstance(conditions, list):
            errors.append(f"{label} {index} conditions is not an array")
            continue
        for condition_index, condition in enumerate(conditions, start=1):
            if not isinstance(condition, dict):
                errors.append(f"{label} {index} condition {condition_index} is not an object")
                continue
            effect_id = str(condition.get("stack_effect_id", condition.get("effect_id", "")) or "")
            if not effect_id:
                errors.append(f"{label} {index} condition {condition_index} stack effect is required")
            elif stack_effect_ids is not None and effect_id not in stack_effect_ids:
                errors.append(f"{label} {index} condition {condition_index} stack effect not found: {effect_id}")
            target = str(condition.get("target", "self") or "self")
            if target not in EFFECT_ACTION_CONDITION_TARGET_IDS:
                errors.append(f"{label} {index} condition {condition_index} target is invalid: {target}")
            min_stacks = safe_int(condition.get("min_stacks"), 0)
            max_stacks = safe_int(condition.get("max_stacks"), -1)
            if min_stacks < 0:
                errors.append(f"{label} {index} condition {condition_index} min stacks must be non-negative")
            if max_stacks >= 0 and max_stacks < min_stacks:
                errors.append(f"{label} {index} condition {condition_index} max stacks must be at least min stacks")


def validate_reward(
    reward: dict[str, Any],
    items: set[str],
    materials: set[str],
    rarities: set[str],
    label: str,
    errors: list[str],
) -> None:
    for drop in reward.get("items", []):
        template_id = str(drop.get("template_id", drop.get("item_id", "")))
        if template_id and template_id not in items:
            errors.append(f"{label} item not found: {template_id}")
        rarity = str(drop.get("rarity", ""))
        if rarity and rarity not in rarities:
            errors.append(f"{label} rarity not found: {rarity}")
    for drop in reward.get("materials", []):
        material_id = str(drop.get("id", ""))
        if material_id not in materials:
            errors.append(f"{label} material not found: {material_id}")


def validate_gacha(
    gacha: Any,
    items: set[str],
    materials: set[str],
    rarities: set[str],
    errors: list[str],
) -> None:
    if not isinstance(gacha, dict):
        errors.append("gacha is not an object")
        return
    pools = gacha.get("pools", [])
    if not isinstance(pools, list):
        errors.append("gacha pools is not an array")
        return
    pool_ids = ensure_unique_ids(pools, "gacha pool", errors)
    default_pool_id = str(gacha.get("default_pool_id", ""))
    if pools and default_pool_id and default_pool_id not in pool_ids:
        errors.append(f"gacha default pool not found: {default_pool_id}")
    if safe_int(gacha.get("cost"), None) is None:
        errors.append("gacha cost is not a number")
    if safe_int(gacha.get("draws"), None) is None:
        errors.append("gacha draws is not a number")
    for pool in pools:
        if not isinstance(pool, dict):
            continue
        entries = pool.get("entries", [])
        if not isinstance(entries, list):
            errors.append(f"gacha pool {pool.get('id')} entries is not an array")
            continue
        if not entries:
            errors.append(f"gacha pool {pool.get('id')} has no entries")
        for index, entry in enumerate(entries, start=1):
            validate_gacha_entry(entry, items, materials, rarities, f"gacha pool {pool.get('id')} entry {index}", errors)


def validate_gacha_entry(
    entry: Any,
    items: set[str],
    materials: set[str],
    rarities: set[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(entry, dict):
        errors.append(f"{label} is not an object")
        return
    entry_type = str(entry.get("type", ""))
    if entry_type not in {"item", "item_rarity", "material", "material_rarity"}:
        errors.append(f"{label} type not found: {entry_type}")
    if safe_float(entry.get("chance"), None) is None:
        errors.append(f"{label} chance is not a number")
    if entry_type == "item":
        item_ids = entry.get("item_ids", entry.get("items", []))
        validate_gacha_targets(item_ids, items, "item", f"{label} item_ids", errors)
    if entry_type == "item_rarity" and str(entry.get("rarity", "")) not in rarities:
        errors.append(f"{label} rarity not found: {entry.get('rarity')}")
    if entry_type == "material":
        material_ids = entry.get("material_ids", entry.get("materials", []))
        validate_gacha_targets(material_ids, materials, "material", f"{label} material_ids", errors)
    if entry_type == "material_rarity" and str(entry.get("rarity", "")) not in rarities:
        errors.append(f"{label} rarity not found: {entry.get('rarity')}")


def validate_gacha_targets(
    raw_targets: Any,
    valid_ids: set[str],
    kind: str,
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(raw_targets, list) or not raw_targets:
        errors.append(f"{label} is empty")
        return
    for raw_target in raw_targets:
        if isinstance(raw_target, dict):
            target_id = str(raw_target.get("id", raw_target.get(f"{kind}_id", "")))
            amount = safe_int(raw_target.get("amount"), None)
            if amount is None or amount < 1:
                errors.append(f"{label} amount must be at least 1: {target_id}")
        else:
            target_id = str(raw_target)
        if target_id not in valid_ids:
            errors.append(f"{label} {kind} not found: {target_id}")


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "RPGAdmin/1.0"
    backup_retention = DEFAULT_BACKUP_RETENTION

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_static("index.html")
        elif path in {"/favicon.ico", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"}:
            self.send_no_content()
        elif path == "/api/content":
            self.send_json({"ok": True, "content": read_content()})
        elif path.startswith("/static/"):
            self.send_static(path.removeprefix("/static/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self.read_json_body()
        if path == "/api/validate":
            errors = validate_content(payload.get("content", {}))
            self.send_json({"ok": not errors, "errors": errors})
            return
        if path == "/api/save":
            content = payload.get("content", {})
            try:
                backup_path = save_content(content, self.backup_retention)
            except ValueError as exc:
                self.send_json({"ok": False, "errors": str(exc).splitlines()}, status=HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "backup": str(backup_path.relative_to(ROOT))})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_no_content(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_static(self, relative_path: str) -> None:
        path = (STATIC_DIR / relative_path).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())) or not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[rpg-admin] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local RPG content admin UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--backup-retention", type=int, default=DEFAULT_BACKUP_RETENTION, help="Number of recent content backups to keep.")
    args = parser.parse_args()

    AdminHandler.backup_retention = max(1, args.backup_retention)
    server = ThreadingHTTPServer((args.host, args.port), AdminHandler)
    print(f"RPG admin UI: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
