from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONTENT_DIR = Path(__file__).with_name("content")
LEGACY_CONTENT_PATH = Path(__file__).with_name("content.json")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_json_dir(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = [
        _read_json(file)
        for file in sorted(path.glob("*.json"))
    ]
    return sorted(
        entries,
        key=lambda entry: (int(entry.get("sort_order", 9999)), str(entry.get("id", ""))),
    )


def _load_content() -> dict[str, Any]:
    if CONTENT_DIR.exists():
        return {
            "settings": _read_json(CONTENT_DIR / "settings.json"),
            "stats": _read_json(CONTENT_DIR / "stats.json"),
            "rarities": _read_json(CONTENT_DIR / "rarities.json"),
            "level_curve": _read_json(CONTENT_DIR / "level_curve.json"),
            "player": _read_json(CONTENT_DIR / "player.json"),
            "stat_allocation": _read_json(CONTENT_DIR / "stat_allocation.json"),
            "enhancement": _read_json(CONTENT_DIR / "enhancement.json"),
            "drop_rarity_weights": _read_json(CONTENT_DIR / "drop_rarity_weights.json"),
            "items": _read_json(CONTENT_DIR / "items.json"),
            "jobs": _read_json(CONTENT_DIR / "jobs.json"),
            "skills": _read_json(CONTENT_DIR / "skills.json"),
            "materials": _read_json(CONTENT_DIR / "materials.json"),
            "crafting_recipes": _read_json(CONTENT_DIR / "crafting_recipes.json"),
            "dungeons": _read_json_dir(CONTENT_DIR / "dungeons"),
            "bosses": _read_json_dir(CONTENT_DIR / "bosses"),
        }
    if LEGACY_CONTENT_PATH.exists():
        return _read_json(LEGACY_CONTENT_PATH)
    raise FileNotFoundError(f"RPG content not found: {CONTENT_DIR}")


CONTENT = _load_content()


@dataclass(frozen=True)
class ItemTemplate:
    id: str
    name: str
    rarity: str
    stats: dict[str, float]
    base_price: int


@dataclass(frozen=True)
class SkillTemplate:
    id: str
    name: str
    unlock_level: int
    uses: int = 0
    cooldown: int = 0
    role: str = "attack"
    damage_multiplier: float = 0.0
    hits: int = 0
    player_mods: dict[str, float] = field(default_factory=dict)
    enemy_mods: dict[str, float] = field(default_factory=dict)
    duration: int = 0
    heal_power: float = 0.0
    damage_cut: float = 0.0
    job_ids: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class JobTemplate:
    id: str
    name: str
    tier: int
    level_req: int
    parent_id: str
    stats: dict[str, float]
    description: str


@dataclass(frozen=True)
class BossPattern:
    threshold: float
    name: str
    damage_multiplier: float = 0.0
    hits: int = 0
    player_mods: dict[str, float] = field(default_factory=dict)
    boss_mods: dict[str, float] = field(default_factory=dict)
    duration: int = 0
    id: str = ""


@dataclass(frozen=True)
class BossHPWarningTemplate:
    threshold: float
    pattern_id: str
    objective: str
    required: int


@dataclass(frozen=True)
class BossCTGaugeTemplate:
    above: float
    max: int


@dataclass(frozen=True)
class BossCTWarningTemplate:
    above: float
    pattern_id: str
    objective: str
    required: int


@dataclass(frozen=True)
class MaterialTemplate:
    id: str
    name: str
    rarity: str
    description: str = ""


@dataclass(frozen=True)
class RewardItemDrop:
    chance: float
    template_id: str = ""
    rank: int = 0
    rarity: str = ""
    stars: int = 0


@dataclass(frozen=True)
class RewardMaterialDrop:
    id: str
    chance: float
    min: int = 1
    max: int = 1


@dataclass(frozen=True)
class RewardTemplate:
    gold_min: int = 0
    gold_max: int = 0
    exp: int = 0
    stat_points: int = 0
    item_drops: list[RewardItemDrop] = field(default_factory=list)
    material_drops: list[RewardMaterialDrop] = field(default_factory=list)


@dataclass(frozen=True)
class CraftingRecipe:
    id: str
    name: str
    result_item_id: str
    level_req: int
    gold: int
    materials: dict[str, int]
    description: str = ""
    sort_order: int = 0
    result_stars: int = 0


@dataclass(frozen=True)
class EnemyTemplate:
    id: str
    name: str
    weight: int
    rank: int
    stats: dict[str, float]
    gold: int
    exp: int
    drop_chance: float
    description: str
    rare: bool = False
    rewards: RewardTemplate = field(default_factory=RewardTemplate)
    consolation_rewards: RewardTemplate = field(default_factory=RewardTemplate)


@dataclass(frozen=True)
class DungeonTemplate:
    id: str
    name: str
    level_req: int
    rank: int
    enemies: list[EnemyTemplate]
    description: str


@dataclass(frozen=True)
class BossTemplate:
    id: str
    name: str
    level_req: int
    rank: int
    stats: dict[str, float]
    gold: int
    exp: int
    stat_points: int
    drop_chance: float
    patterns: list[BossPattern]
    description: str
    hp_warnings: list[BossHPWarningTemplate] = field(default_factory=list)
    ct_gauge: list[BossCTGaugeTemplate] = field(default_factory=list)
    ct_warnings: list[BossCTWarningTemplate] = field(default_factory=list)
    pattern_by_id: dict[str, BossPattern] = field(default_factory=dict)
    rewards: RewardTemplate = field(default_factory=RewardTemplate)


def _stats(raw: dict[str, Any] | None) -> dict[str, float]:
    return {str(key): float(value) for key, value in (raw or {}).items()}


def _base_price(rarity: str, stats: dict[str, float]) -> int:
    power = 0.0
    for key, value in stats.items():
        if key == "base_atk":
            power += value * 19
        elif key == "max_hp":
            power += value * 2.2
        elif key == "dmg_mitigation":
            power += value * 30
        else:
            power += value * 900
    richness = 1 + 0.16 * max(0, len(stats) - 2)
    return round((80 + power) * RARITY_PRICE_MULTIPLIERS[rarity] * richness)


def _item(raw: dict[str, Any]) -> ItemTemplate:
    stats = _stats(raw.get("stats"))
    rarity = str(raw["rarity"])
    return ItemTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        rarity=rarity,
        stats=stats,
        base_price=int(raw.get("base_price") or _base_price(rarity, stats)),
    )


def _job(raw: dict[str, Any]) -> JobTemplate:
    return JobTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        tier=int(raw["tier"]),
        level_req=int(raw["level_req"]),
        parent_id=str(raw.get("parent_id", "")),
        stats=_stats(raw.get("stats")),
        description=str(raw.get("description", "")),
    )


def _skill(raw: dict[str, Any]) -> SkillTemplate:
    return SkillTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        unlock_level=int(raw["unlock_level"]),
        uses=int(raw.get("uses", 0)),
        cooldown=int(raw.get("cooldown", 0)),
        role=str(raw.get("role", "attack")),
        damage_multiplier=float(raw.get("damage_multiplier", 0.0)),
        hits=int(raw.get("hits", 0)),
        player_mods=_stats(raw.get("player_mods")),
        enemy_mods=_stats(raw.get("enemy_mods")),
        duration=int(raw.get("duration", 0)),
        heal_power=float(raw.get("heal_power", 0.0)),
        damage_cut=float(raw.get("damage_cut", 0.0)),
        job_ids=tuple(str(job_id) for job_id in raw.get("job_ids", ())),
        note=str(raw.get("note", "")),
    )


def _material(raw: dict[str, Any]) -> MaterialTemplate:
    return MaterialTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        rarity=str(raw.get("rarity", "normal")),
        description=str(raw.get("description", "")),
    )


def _gold_range(raw: Any, default_gold: int) -> tuple[int, int]:
    if isinstance(raw, dict):
        minimum = int(raw.get("min", default_gold))
        maximum = int(raw.get("max", minimum))
    elif raw is None:
        minimum = maximum = default_gold
    else:
        minimum = maximum = int(raw)
    return max(0, minimum), max(0, max(minimum, maximum))


def _reward_item_drop(raw: dict[str, Any]) -> RewardItemDrop:
    return RewardItemDrop(
        chance=max(0.0, min(1.0, float(raw.get("chance", 0.0)))),
        template_id=str(raw.get("template_id", raw.get("item_id", ""))),
        rank=max(0, int(raw.get("rank", 0))),
        rarity=str(raw.get("rarity", "")),
        stars=max(0, int(raw.get("stars", 0))),
    )


def _reward_material_drop(raw: dict[str, Any]) -> RewardMaterialDrop:
    minimum = max(1, int(raw.get("min", raw.get("amount", 1))))
    maximum = max(minimum, int(raw.get("max", minimum)))
    return RewardMaterialDrop(
        id=str(raw["id"]),
        chance=max(0.0, min(1.0, float(raw.get("chance", 1.0)))),
        min=minimum,
        max=maximum,
    )


def _reward(
    raw: dict[str, Any] | None,
    *,
    default_gold: int = 0,
    default_exp: int = 0,
    default_stat_points: int = 0,
    default_item_rank: int = 0,
    default_item_chance: float = 0.0,
) -> RewardTemplate:
    raw = raw or {}
    gold_min, gold_max = _gold_range(raw.get("gold"), default_gold)
    item_drops = [
        _reward_item_drop(item)
        for item in raw.get("items", [])
        if isinstance(item, dict)
    ]
    if not item_drops and default_item_chance > 0:
        item_drops = [RewardItemDrop(default_item_chance, rank=default_item_rank)]
    material_drops = [
        _reward_material_drop(material)
        for material in raw.get("materials", [])
        if isinstance(material, dict) and material.get("id")
    ]
    return RewardTemplate(
        gold_min=gold_min,
        gold_max=gold_max,
        exp=max(0, int(raw.get("exp", default_exp))),
        stat_points=max(0, int(raw.get("stat_points", default_stat_points))),
        item_drops=item_drops,
        material_drops=material_drops,
    )


def _crafting_recipe(raw: dict[str, Any]) -> CraftingRecipe:
    return CraftingRecipe(
        id=str(raw["id"]),
        name=str(raw["name"]),
        result_item_id=str(raw["result_item_id"]),
        level_req=max(1, int(raw.get("level_req", 1))),
        gold=max(0, int(raw.get("gold", 0))),
        materials={str(key): max(1, int(value)) for key, value in raw.get("materials", {}).items()},
        description=str(raw.get("description", "")),
        sort_order=int(raw.get("sort_order", 0)),
        result_stars=max(0, int(raw.get("result_stars", 0))),
    )


def _enemy(raw: dict[str, Any]) -> EnemyTemplate:
    gold = int(raw["gold"])
    exp = int(raw["exp"])
    rank = int(raw["rank"])
    drop_chance = float(raw["drop_chance"])
    return EnemyTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        weight=int(raw["weight"]),
        rank=rank,
        stats=_stats(raw.get("stats")),
        gold=gold,
        exp=exp,
        drop_chance=drop_chance,
        description=str(raw.get("description", "")),
        rare=bool(raw.get("rare", False)),
        rewards=_reward(
            raw.get("rewards"),
            default_gold=gold,
            default_exp=exp,
            default_item_rank=rank,
            default_item_chance=drop_chance,
        ),
        consolation_rewards=_reward(
            raw.get("consolation_rewards"),
            default_gold=max(1, gold // 5),
            default_exp=max(1, exp // 5),
        ),
    )


def _dungeon(raw: dict[str, Any]) -> DungeonTemplate:
    return DungeonTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        level_req=int(raw["level_req"]),
        rank=int(raw["rank"]),
        enemies=[_enemy(enemy) for enemy in raw.get("enemies", [])],
        description=str(raw.get("description", "")),
    )


def _boss_pattern(raw: dict[str, Any]) -> BossPattern:
    return BossPattern(
        id=str(raw.get("id", "")),
        threshold=float(raw.get("threshold", 0.0)),
        name=str(raw["name"]),
        damage_multiplier=float(raw.get("damage_multiplier", 0.0)),
        hits=int(raw.get("hits", 0)),
        player_mods=_stats(raw.get("player_mods")),
        boss_mods=_stats(raw.get("boss_mods")),
        duration=int(raw.get("duration", 0)),
    )


def _hp_warning(raw: dict[str, Any]) -> BossHPWarningTemplate:
    return BossHPWarningTemplate(
        threshold=float(raw["threshold"]),
        pattern_id=str(raw["pattern_id"]),
        objective=str(raw.get("objective", "damage")),
        required=max(1, int(raw.get("required", 1))),
    )


def _ct_gauge(raw: dict[str, Any]) -> BossCTGaugeTemplate:
    return BossCTGaugeTemplate(
        above=float(raw.get("above", 0.0)),
        max=max(1, int(raw.get("max", 1))),
    )


def _ct_warning(raw: dict[str, Any]) -> BossCTWarningTemplate:
    return BossCTWarningTemplate(
        above=float(raw.get("above", 0.0)),
        pattern_id=str(raw["pattern_id"]),
        objective=str(raw.get("objective", "hits")),
        required=max(1, int(raw.get("required", 1))),
    )


def _boss(raw: dict[str, Any]) -> BossTemplate:
    patterns = [_boss_pattern(pattern) for pattern in raw.get("patterns", [])]
    pattern_by_id = {
        pattern.id or pattern.name: pattern
        for pattern in patterns
    }
    ct = raw.get("ct", {})
    rank = int(raw["rank"])
    gold = int(raw["gold"])
    exp = int(raw["exp"])
    stat_points = int(raw.get("stat_points", 0))
    drop_chance = float(raw.get("drop_chance", 0.0))
    return BossTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        level_req=int(raw["level_req"]),
        rank=rank,
        stats=_stats(raw.get("stats")),
        gold=gold,
        exp=exp,
        stat_points=stat_points,
        drop_chance=drop_chance,
        patterns=patterns,
        description=str(raw.get("description", "")),
        hp_warnings=sorted(
            [_hp_warning(warning) for warning in raw.get("hp_warnings", [])],
            key=lambda warning: warning.threshold,
            reverse=True,
        ),
        ct_gauge=sorted(
            [_ct_gauge(rule) for rule in ct.get("gauge_by_hp", [])],
            key=lambda rule: rule.above,
            reverse=True,
        ),
        ct_warnings=sorted(
            [_ct_warning(warning) for warning in ct.get("warnings_by_hp", [])],
            key=lambda warning: warning.above,
            reverse=True,
        ),
        pattern_by_id=pattern_by_id,
        rewards=_reward(
            raw.get("rewards"),
            default_gold=gold,
            default_exp=exp,
            default_stat_points=stat_points,
            default_item_rank=rank + 1,
            default_item_chance=drop_chance,
        ),
    )


_SETTINGS = CONTENT.get("settings", {})
DAILY_EXPLORES = int(_SETTINGS.get("daily_explores", 7))
EXPLORE_LIMIT_ENABLED = bool(_SETTINGS.get("explore_limit_enabled", False))
BOSS_WEEKLY_REWARD_LIMIT_ENABLED = bool(_SETTINGS.get("boss_weekly_reward_limit_enabled", False))
MAX_EQUIPPED_ITEMS = int(_SETTINGS.get("max_equipped_items", 4))
MAX_ENHANCEMENT_STARS = int(_SETTINGS.get("max_enhancement_stars", 10))

_STAT_DATA = CONTENT.get("stats", {})
STAT_ORDER = [str(stat) for stat in _STAT_DATA.get("order", [])]
STAT_LABELS = {str(key): str(value) for key, value in _STAT_DATA.get("labels", {}).items()}
PERCENT_STATS = {str(stat) for stat in _STAT_DATA.get("percent_stats", [])}
INTEGER_STATS = {str(stat) for stat in _STAT_DATA.get("integer_stats", [])}

_RARITY_DATA = CONTENT.get("rarities", {})
RARITIES = [str(rarity) for rarity in _RARITY_DATA.get("order", [])]
RARITY_LABELS = {str(key): str(value) for key, value in _RARITY_DATA.get("labels", {}).items()}
RARITY_COLORS = {str(key): int(value) for key, value in _RARITY_DATA.get("colors", {}).items()}
ENHANCE_BASE_COST = {str(key): int(value) for key, value in _RARITY_DATA.get("enhance_base_cost", {}).items()}
RESTORE_COST = {str(key): int(value) for key, value in _RARITY_DATA.get("restore_cost", {}).items()}
RARITY_PRICE_MULTIPLIERS = {
    str(key): float(value)
    for key, value in _RARITY_DATA.get("price_multipliers", {}).items()
}

ITEM_CATALOG = [_item(item) for item in CONTENT.get("items", [])]
ITEM_BY_ID = {item.id: item for item in ITEM_CATALOG}
ITEMS_BY_RARITY = {
    rarity: [item for item in ITEM_CATALOG if item.rarity == rarity]
    for rarity in RARITIES
}

JOBS = [_job(job) for job in CONTENT.get("jobs", [])]
JOB_BY_ID = {job.id: job for job in JOBS}

SKILLS = [_skill(skill) for skill in CONTENT.get("skills", [])]
SKILL_BY_ID = {skill.id: skill for skill in SKILLS}

MATERIALS = [_material(material) for material in CONTENT.get("materials", [])]
MATERIAL_BY_ID = {material.id: material for material in MATERIALS}

CRAFTING_RECIPES = sorted(
    [_crafting_recipe(recipe) for recipe in CONTENT.get("crafting_recipes", [])],
    key=lambda recipe: (recipe.sort_order, recipe.level_req, recipe.name),
)
CRAFTING_RECIPE_BY_ID = {recipe.id: recipe for recipe in CRAFTING_RECIPES}

DUNGEONS = [_dungeon(dungeon) for dungeon in CONTENT.get("dungeons", [])]
DUNGEON_BY_ID = {dungeon.id: dungeon for dungeon in DUNGEONS}

BOSSES = [_boss(boss) for boss in CONTENT.get("bosses", [])]
BOSS_BY_ID = {boss.id: boss for boss in BOSSES}


def _validate_content() -> None:
    errors: list[str] = []
    for recipe in CRAFTING_RECIPES:
        if recipe.result_item_id not in ITEM_BY_ID:
            errors.append(f"crafting recipe {recipe.id} result item not found: {recipe.result_item_id}")
        for material_id in recipe.materials:
            if material_id not in MATERIAL_BY_ID:
                errors.append(f"crafting recipe {recipe.id} material not found: {material_id}")
    for dungeon in DUNGEONS:
        for enemy in dungeon.enemies:
            errors.extend(_validate_reward(enemy.rewards, f"enemy {enemy.id} rewards"))
            errors.extend(_validate_reward(enemy.consolation_rewards, f"enemy {enemy.id} consolation_rewards"))
    for boss in BOSSES:
        for warning in boss.hp_warnings:
            if warning.pattern_id not in boss.pattern_by_id:
                errors.append(f"boss {boss.id} hp warning pattern not found: {warning.pattern_id}")
        for warning in boss.ct_warnings:
            if warning.pattern_id not in boss.pattern_by_id:
                errors.append(f"boss {boss.id} ct warning pattern not found: {warning.pattern_id}")
        errors.extend(_validate_reward(boss.rewards, f"boss {boss.id} rewards"))
    if errors:
        raise ValueError("Invalid RPG content:\n" + "\n".join(f"- {error}" for error in errors))


def _validate_reward(reward: RewardTemplate, label: str) -> list[str]:
    errors: list[str] = []
    for drop in reward.item_drops:
        if drop.template_id and drop.template_id not in ITEM_BY_ID:
            errors.append(f"{label} item not found: {drop.template_id}")
        if drop.rarity and drop.rarity not in RARITIES:
            errors.append(f"{label} rarity not found: {drop.rarity}")
    for drop in reward.material_drops:
        if drop.id not in MATERIAL_BY_ID:
            errors.append(f"{label} material not found: {drop.id}")
    return errors


_validate_content()

_LEVEL_CURVE = CONTENT.get("level_curve", {})
_ENHANCEMENT = CONTENT.get("enhancement", {})
PLAYER_START = dict(CONTENT.get("player", {}).get("start", {}))
STAT_ALLOCATIONS = {
    str(stat_id): dict(rule)
    for stat_id, rule in CONTENT.get("stat_allocation", {}).items()
    if isinstance(rule, dict)
}
DROP_RARITY_WEIGHTS = {
    str(rarity): dict(rule)
    for rarity, rule in CONTENT.get("drop_rarity_weights", {}).items()
    if isinstance(rule, dict)
}


def next_level_exp(level: int) -> int:
    level = max(1, level)
    step = level - 1
    base = int(_LEVEL_CURVE.get("base", 280))
    linear = int(_LEVEL_CURVE.get("linear", 170))
    quadratic = int(_LEVEL_CURVE.get("quadratic", 50))
    return base + linear * step + quadratic * step * step


def previous_level_exp(level: int) -> int:
    if level <= 1:
        return 0
    return next_level_exp(level - 1)


def star_multiplier(stars: int) -> float:
    stars = max(0, min(MAX_ENHANCEMENT_STARS, stars))
    config = _ENHANCEMENT.get("star_multiplier", {})
    linear = float(config.get("linear", 0.24))
    quadratic = float(config.get("quadratic", 0.03))
    early_bonus = float(config.get("early_bonus", 0.03))
    early_bonus_cap = int(config.get("early_bonus_cap", 3))
    return 1.0 + linear * stars + quadratic * stars * stars + early_bonus * min(stars, early_bonus_cap)


def scaled_item_stats(template_id: str, stars: int) -> dict[str, float]:
    multiplier = star_multiplier(stars)
    stats: dict[str, float] = {}
    for key, value in ITEM_BY_ID[template_id].stats.items():
        scaled = value / multiplier if value < 0 else value * multiplier
        if key in INTEGER_STATS:
            stats[key] = float(max(1, round(scaled)))
        elif key == "dmg_mitigation":
            stats[key] = round(scaled, 1)
        else:
            stats[key] = round(scaled, 4)
    return stats


def stat_delta(base_stats: dict[str, float], upgraded_stats: dict[str, float]) -> dict[str, float]:
    keys = set(base_stats) | set(upgraded_stats)
    return {
        key: upgraded_stats.get(key, 0.0) - base_stats.get(key, 0.0)
        for key in keys
    }


def enhancement_cost(rarity: str, stars: int) -> int:
    return ENHANCE_BASE_COST[rarity] * (stars + 1) * (stars + 1)


def restore_cost(rarity: str) -> int:
    return RESTORE_COST[rarity]


def sell_price(template_id: str, stars: int, *, destroyed: bool = False) -> int:
    template = ITEM_BY_ID[template_id]
    multiplier = star_multiplier(stars)
    sell_rates = _ENHANCEMENT.get("sell_rates", {})
    rate = float(sell_rates.get("destroyed" if destroyed else "normal", 0.16 if destroyed else 0.38))
    return max(1, round(template.base_price * multiplier * rate))


def enhancement_odds(rarity: str, stars: int) -> tuple[float, float, float]:
    tier = RARITIES.index(rarity)
    config = _ENHANCEMENT.get("odds", {})
    success = max(
        float(config.get("success_floor", 0.15)),
        float(config.get("success_base", 0.86))
        - float(config.get("success_star_penalty", 0.055)) * stars
        - float(config.get("success_tier_penalty", 0.045)) * tier,
    )
    destroy_min_stars = int(config.get("destroy_min_stars", 2))
    if stars < destroy_min_stars:
        destroy = 0.0
    else:
        destroy = min(
            float(config.get("destroy_cap", 0.38)),
            float(config.get("destroy_scale", 0.008)) * (stars - 1) * (tier + 1),
        )
    fail = max(0.0, 1.0 - success - destroy)
    return success, fail, destroy
