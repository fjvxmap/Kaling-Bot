from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONTENT_DIR = Path(__file__).with_name("content")
LEGACY_CONTENT_PATH = Path(__file__).with_name("content.json")
WARNING_OBJECTIVES = {
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
STACK_CONDITION_OBJECTIVES = WARNING_OBJECTIVES | {"received_damage"}
WARNING_ACTIVATION_CONDITIONS = {
    "stack",
    "turn_multiple",
    "turn_range",
    "boss_hp_ratio",
    "ct_ready",
}
INFINITE_EFFECT_TURNS = -1
STACK_EFFECT_ACTIONS = {
    "stack_increase",
    "stack_decrease",
    "stack_set",
    "stack_remove",
    "stack_max",
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


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
            "gacha": _read_json(CONTENT_DIR / "gacha.json"),
            "items": _read_json(CONTENT_DIR / "items.json"),
            "jobs": _read_json(CONTENT_DIR / "jobs.json"),
            "skills": _read_json(CONTENT_DIR / "skills.json"),
            "stack_effects": _read_json(CONTENT_DIR / "stack_effects.json")
            if (CONTENT_DIR / "stack_effects.json").exists()
            else [],
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
class FlurryEffect:
    count: int
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class DoubleStrikeEffect:
    count: int
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class BonusDamageEffect:
    ratio: float
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class CriticalReinforceEffect:
    ratio: float
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class FinalDamageEffect:
    ratio: float
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class PostAttackAbilityDamageEffect:
    ratio: float
    count: int
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class AbilityRecastEffect:
    count: int
    duration: int
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class DispelGuardEffect:
    duration: int
    count: int = 0
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class VeilEffect:
    duration: int
    count: int = 0
    undispellable: bool = False
    target: str = "self"


@dataclass(frozen=True)
class HealCap:
    mode: str = "none"
    value: float = 0.0

    @property
    def has_cap(self) -> bool:
        return self.mode in {"flat", "max_hp_ratio"} and self.value > 0


@dataclass(frozen=True)
class PlainDamage:
    mode: str = "none"
    value: float = 0.0

    @property
    def has_damage(self) -> bool:
        return self.mode in {"flat", "target_max_hp_ratio"} and self.value > 0


@dataclass(frozen=True)
class StatEffect:
    stat: str
    value: float
    duration: int
    undispellable: bool = False
    heal_cap: HealCap = field(default_factory=HealCap)
    target: str = "self"


@dataclass(frozen=True)
class CombatSpecialEffects:
    flurry: FlurryEffect | None = None
    double_strike: DoubleStrikeEffect | None = None
    bonus_damage: list[BonusDamageEffect] = field(default_factory=list)
    critical_reinforce: list[CriticalReinforceEffect] = field(default_factory=list)
    final_damage: list[FinalDamageEffect] = field(default_factory=list)
    post_attack_ability_damage: list[PostAttackAbilityDamageEffect] = field(default_factory=list)
    ability_recast: list[AbilityRecastEffect] = field(default_factory=list)
    dispel_guard: list[DispelGuardEffect] = field(default_factory=list)
    veil: list[VeilEffect] = field(default_factory=list)

    @property
    def has_any(self) -> bool:
        return (
            self.flurry is not None
            or self.double_strike is not None
            or bool(self.bonus_damage)
            or bool(self.critical_reinforce)
            or bool(self.final_damage)
            or bool(self.post_attack_ability_damage)
            or bool(self.ability_recast)
            or bool(self.dispel_guard)
            or bool(self.veil)
        )


@dataclass(frozen=True)
class EffectActionStackCondition:
    stack_effect_id: str = ""
    target: str = "self"
    min_stacks: int = 0
    max_stacks: int = -1


@dataclass(frozen=True)
class EffectAction:
    action: str
    target: str = "enemy"
    count: int = 1
    stack_effect_id: str = ""
    value: int = 1
    conditions: list[EffectActionStackCondition] = field(default_factory=list)


@dataclass(frozen=True)
class StackEffectCondition:
    objective: str
    target: str = "self"
    operation: str = "increase"
    value: int = 1
    required: int = 1
    min_damage: int = 0


@dataclass(frozen=True)
class StackEffectTier:
    stack: int
    stat_effects: list[StatEffect] = field(default_factory=list)
    effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)


@dataclass(frozen=True)
class StackEffectTemplate:
    id: str
    name: str
    max_stacks: int
    description: str = ""
    tiers: list[StackEffectTier] = field(default_factory=list)
    conditions: list[StackEffectCondition] = field(default_factory=list)


@dataclass(frozen=True)
class ItemTemplate:
    id: str
    name: str
    rarity: str
    stats: dict[str, float]
    base_price: int
    fixed_stats: frozenset[str] = field(default_factory=frozenset)
    stat_effects: list[StatEffect] = field(default_factory=list)
    effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    undispellable: bool = True
    excluded_from_gacha: bool = False


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
    player_stat_effects: list[StatEffect] = field(default_factory=list)
    enemy_stat_effects: list[StatEffect] = field(default_factory=list)
    player_effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    enemy_effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    effect_actions: list[EffectAction] = field(default_factory=list)
    player_undispellable: bool = False
    enemy_undispellable: bool = False
    duration: int = 0
    heal_power: float = 0.0
    heal_cap: HealCap = field(default_factory=HealCap)
    heal_target: str = "self"
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
    description: str = ""
    stat_effects: list[StatEffect] = field(default_factory=list)
    effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    undispellable: bool = True


@dataclass(frozen=True)
class BossPattern:
    threshold: float
    name: str
    damage_multiplier: float = 0.0
    hits: int = 0
    plain_damage: PlainDamage = field(default_factory=PlainDamage)
    self_hp_loss_ratio: float = 0.0
    player_mods: dict[str, float] = field(default_factory=dict)
    boss_mods: dict[str, float] = field(default_factory=dict)
    player_stat_effects: list[StatEffect] = field(default_factory=list)
    boss_stat_effects: list[StatEffect] = field(default_factory=list)
    player_effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    boss_effects: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    effect_actions: list[EffectAction] = field(default_factory=list)
    player_undispellable: bool = False
    boss_undispellable: bool = False
    duration: int = 0
    id: str = ""


@dataclass(frozen=True)
class BossWarningObjective:
    objective: str
    required: int
    min_damage: int = 0


@dataclass(frozen=True)
class BossWarningFailureStackCondition:
    stack_effect_id: str
    target: str = "boss"
    min_stacks: int = 0
    max_stacks: int = -1


@dataclass(frozen=True)
class BossWarningActivationCondition:
    kind: str
    stack_effect_id: str = ""
    target: str = "boss"
    min_stacks: int = 0
    max_stacks: int = -1
    multiple: int = 1
    min_turn: int = 1
    max_turn: int = -1
    min_ratio: float = 0.0
    max_ratio: float = 1.0
    ct_ready: bool = True


@dataclass(frozen=True)
class BossWarningFailureVariant:
    conditions: list[BossWarningFailureStackCondition]
    pattern: BossPattern
    name: str = ""


@dataclass(frozen=True)
class BossWarningTemplate:
    id: str
    name: str
    pattern_id: str
    objectives: list[BossWarningObjective]
    turns: int = 1
    pattern: BossPattern | None = None
    success_pattern: BossPattern | None = None
    success_warning_id: str = ""
    failure_warning_id: str = ""
    failure_variants: list[BossWarningFailureVariant] = field(default_factory=list)
    activation_conditions: list[BossWarningActivationCondition] = field(default_factory=list)


@dataclass(frozen=True)
class BossHPWarningTemplate:
    threshold: float
    warning_id: str
    warning: BossWarningTemplate | None = None


@dataclass(frozen=True)
class BossHPInstantEffectTemplate:
    threshold: float
    pattern: BossPattern


@dataclass(frozen=True)
class BossCTGaugeTemplate:
    above: float
    max: int


@dataclass(frozen=True)
class BossCTWarningTemplate:
    above: float
    warning_id: str
    warning: BossWarningTemplate | None = None
    warning_ids: tuple[str, ...] = ()
    warnings: tuple[BossWarningTemplate, ...] = ()


@dataclass(frozen=True)
class BossStackEffectTemplate:
    stack_effect_id: str
    initial_stacks: int = 0


@dataclass(frozen=True)
class MaterialTemplate:
    id: str
    name: str
    rarity: str
    description: str = ""
    emoji: str = ""


@dataclass(frozen=True)
class RewardItemDrop:
    chance: float
    template_id: str = ""
    rarity: str = ""
    stars: int = 0
    min: int = 1
    max: int = 1
    owner_chance: float | None = None
    owner_min: int | None = None
    owner_max: int | None = None
    participant_chance: float | None = None
    participant_min: int | None = None
    participant_max: int | None = None


@dataclass(frozen=True)
class RewardMaterialDrop:
    id: str
    chance: float
    min: int = 1
    max: int = 1
    owner_chance: float | None = None
    owner_min: int | None = None
    owner_max: int | None = None
    participant_chance: float | None = None
    participant_min: int | None = None
    participant_max: int | None = None


@dataclass(frozen=True)
class RewardTemplate:
    item_drops: list[RewardItemDrop] = field(default_factory=list)
    material_drops: list[RewardMaterialDrop] = field(default_factory=list)


@dataclass(frozen=True)
class GachaEntry:
    type: str
    chance: float
    item_ids: tuple[str, ...] = ()
    material_ids: tuple[str, ...] = ()
    item_amounts: dict[str, int] = field(default_factory=dict)
    material_amounts: dict[str, int] = field(default_factory=dict)
    rarity: str = ""
    stars: int = 0
    min: int = 1
    max: int = 1


@dataclass(frozen=True)
class GachaPool:
    id: str
    name: str
    description: str
    cost_material_id: str
    cost_material_amount: int
    draws: int
    entries: list[GachaEntry] = field(default_factory=list)


@dataclass(frozen=True)
class EnhancementMethod:
    id: str
    name: str
    description: str = ""
    gold_cost_mode: str = "formula"
    gold_cost: int = 0
    material_costs: dict[str, int] = field(default_factory=dict)
    odds_mode: str = "formula"
    success: float | None = None
    fail: float | None = None
    destroy: float | None = None
    min_stars: int = 0
    max_stars: int = 999


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
    stats: dict[str, float]
    gold: int
    exp: int
    description: str
    rare: bool = False
    rewards: RewardTemplate = field(default_factory=RewardTemplate)


@dataclass(frozen=True)
class DungeonTemplate:
    id: str
    name: str
    level_req: int
    enemies: list[EnemyTemplate]
    description: str


@dataclass(frozen=True)
class BossTemplate:
    id: str
    name: str
    level_req: int
    stats: dict[str, float]
    gold: int
    exp: int
    patterns: list[BossPattern]
    warnings: list[BossWarningTemplate]
    description: str
    hp_warnings: list[BossHPWarningTemplate] = field(default_factory=list)
    hp_effects: list[BossHPInstantEffectTemplate] = field(default_factory=list)
    hp_locks: list[float] = field(default_factory=list)
    ct_gauge: list[BossCTGaugeTemplate] = field(default_factory=list)
    ct_warnings: list[BossCTWarningTemplate] = field(default_factory=list)
    stack_effects: list[BossStackEffectTemplate] = field(default_factory=list)
    pattern_by_id: dict[str, BossPattern] = field(default_factory=dict)
    warning_by_id: dict[str, BossWarningTemplate] = field(default_factory=dict)
    rewards: RewardTemplate = field(default_factory=RewardTemplate)


def _stats(raw: dict[str, Any] | None) -> dict[str, float]:
    return {str(key): float(value) for key, value in (raw or {}).items()}


def _fixed_stats(raw: Any, stats: dict[str, float]) -> frozenset[str]:
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(stat) for stat in raw if str(stat) in stats)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
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


def _clamped_chance(value: Any, default: float = 0.0) -> float:
    return max(0.0, min(1.0, _safe_float(value, default)))


def _optional_chance(raw: dict[str, Any], key: str) -> float | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    return _clamped_chance(value, 0.0)


def _optional_positive_int(raw: dict[str, Any], key: str) -> int | None:
    value = raw.get(key)
    if value is None or value == "":
        return None
    return max(1, _safe_int(value, 1))


def _effect_duration(raw: dict[str, Any] | None, default_duration: int) -> int:
    value = default_duration if raw is None else raw.get("duration", default_duration)
    duration = _safe_int(value, default_duration)
    if duration < 0:
        return INFINITE_EFFECT_TURNS
    return max(1, duration)


def _effect_undispellable(raw: Any, fallback: bool = False) -> bool:
    if isinstance(raw, dict):
        return bool(raw.get("undispellable", fallback))
    return fallback


def _effect_target(raw: Any) -> str:
    if not isinstance(raw, dict):
        return "self"
    target = str(raw.get("target", "self") or "self")
    if target in {"ally", "allies", "party"}:
        return "allies"
    return "self"


def _target_value(raw: Any) -> str:
    target = str(raw or "self")
    if target in {"ally", "allies", "party"}:
        return "allies"
    return "self"


def _guard_count(raw: Any) -> int:
    if not isinstance(raw, dict):
        return 0
    mode = str(raw.get("mode", raw.get("type", "")) or "")
    count = raw.get("count", raw.get("uses", raw.get("charges", 0)))
    if mode == "count" or count:
        return max(1, _safe_int(count, 1))
    return 0


def _guard_duration(raw: Any, default_duration: int) -> int:
    if isinstance(raw, dict) and _guard_count(raw) > 0 and "duration" not in raw:
        return INFINITE_EFFECT_TURNS
    return _effect_duration(raw, default_duration)


def _guard_rows(raw: Any) -> list[Any]:
    if raw in (None, False, {}, []):
        return []
    return raw if isinstance(raw, list) else [raw]


def _bonus_ratio(raw: Any) -> float:
    if isinstance(raw, dict):
        if "percent" in raw:
            return max(0.0, _safe_float(raw.get("percent")) / 100.0)
        return max(0.0, _safe_float(raw.get("ratio", raw.get("value", 0.0))))
    value = _safe_float(raw)
    return max(0.0, value / 100.0 if value > 1 else value)


def _signed_ratio(raw: Any) -> float:
    if isinstance(raw, dict):
        if "percent" in raw:
            return _safe_float(raw.get("percent")) / 100.0
        return _safe_float(raw.get("ratio", raw.get("value", 0.0)))
    value = _safe_float(raw)
    return value / 100.0 if abs(value) > 1 else value


def _heal_cap(raw: Any) -> HealCap:
    if not isinstance(raw, dict):
        return HealCap()
    cap = raw.get("heal_cap")
    if isinstance(cap, dict):
        raw_mode = str(cap.get("mode", cap.get("type", cap.get("kind", "none"))) or "none")
        value = _safe_float(cap.get("value", cap.get("amount", 0.0)), 0.0)
    else:
        raw_mode = str(raw.get("heal_cap_mode", raw.get("heal_cap_type", "none")) or "none")
        value = _safe_float(raw.get("heal_cap_value", cap if cap is not None else 0.0), 0.0)
        if cap is not None and raw_mode == "none":
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
    if mode not in {"flat", "max_hp_ratio"} or value <= 0:
        return HealCap()
    if raw_mode in {"max_hp_percent", "hp_percent", "percent"} or (mode == "max_hp_ratio" and value > 1):
        value /= 100.0
    return HealCap(mode=mode, value=max(0.0, value))


def _combat_effects(
    raw: Any,
    default_duration: int = 1,
    fallback_undispellable: bool = False,
) -> CombatSpecialEffects:
    if not isinstance(raw, dict):
        return CombatSpecialEffects()

    flurry: FlurryEffect | None = None
    flurry_raw = raw.get("flurry")
    if isinstance(flurry_raw, dict):
        count = max(1, _safe_int(flurry_raw.get("count", flurry_raw.get("branches", 1)), 1))
        if count > 1:
            flurry = FlurryEffect(
                count=count,
                duration=_effect_duration(flurry_raw, default_duration),
                undispellable=_effect_undispellable(flurry_raw, fallback_undispellable),
                target=_effect_target(flurry_raw),
            )
    elif flurry_raw:
        count = 2 if isinstance(flurry_raw, bool) else max(1, _safe_int(flurry_raw, 1))
        if count > 1:
            flurry = FlurryEffect(
                count=count,
                duration=_effect_duration(None, default_duration),
                undispellable=fallback_undispellable,
                target="self",
            )

    double_strike: DoubleStrikeEffect | None = None
    double_raw = raw.get("double_strike")
    if isinstance(double_raw, dict):
        if bool(double_raw.get("enabled", True)):
            count = max(2, _safe_int(double_raw.get("count", double_raw.get("actions", 2)), 2))
            double_strike = DoubleStrikeEffect(
                count=count,
                duration=_effect_duration(double_raw, default_duration),
                undispellable=_effect_undispellable(double_raw, fallback_undispellable),
                target=_effect_target(double_raw),
            )
    elif double_raw:
        double_strike = DoubleStrikeEffect(
            count=2,
            duration=_effect_duration(None, default_duration),
            undispellable=fallback_undispellable,
            target="self",
        )

    bonus_damage: list[BonusDamageEffect] = []
    bonus_raw = raw.get("bonus_damage", [])
    bonus_rows = bonus_raw if isinstance(bonus_raw, list) else [bonus_raw]
    for bonus in bonus_rows:
        ratio = _bonus_ratio(bonus)
        if ratio <= 0:
            continue
        duration = _effect_duration(bonus if isinstance(bonus, dict) else None, default_duration)
        bonus_damage.append(
            BonusDamageEffect(
                ratio=ratio,
                duration=duration,
                undispellable=_effect_undispellable(bonus, fallback_undispellable),
                target=_effect_target(bonus),
            )
        )

    critical_reinforce: list[CriticalReinforceEffect] = []
    reinforce_raw = raw.get("critical_reinforce", [])
    reinforce_rows = reinforce_raw if isinstance(reinforce_raw, list) else [reinforce_raw]
    for reinforce in reinforce_rows:
        ratio = _bonus_ratio(reinforce)
        if ratio <= 0:
            continue
        duration = _effect_duration(reinforce if isinstance(reinforce, dict) else None, default_duration)
        critical_reinforce.append(
            CriticalReinforceEffect(
                ratio=ratio,
                duration=duration,
                undispellable=_effect_undispellable(reinforce, fallback_undispellable),
                target=_effect_target(reinforce),
            )
        )

    final_damage: list[FinalDamageEffect] = []
    final_damage_raw = raw.get("final_damage", [])
    final_damage_rows = final_damage_raw if isinstance(final_damage_raw, list) else [final_damage_raw]
    for final_effect in final_damage_rows:
        ratio = _signed_ratio(final_effect)
        if ratio == 0 or ratio <= -1:
            continue
        duration = _effect_duration(final_effect if isinstance(final_effect, dict) else None, default_duration)
        final_damage.append(
            FinalDamageEffect(
                ratio=ratio,
                duration=duration,
                undispellable=_effect_undispellable(final_effect, fallback_undispellable),
                target=_effect_target(final_effect),
            )
        )

    post_attack_ability_damage: list[PostAttackAbilityDamageEffect] = []
    post_attack_raw = raw.get("post_attack_ability_damage", [])
    post_attack_rows = post_attack_raw if isinstance(post_attack_raw, list) else [post_attack_raw]
    for post_attack in post_attack_rows:
        ratio = _bonus_ratio(post_attack)
        if ratio <= 0:
            continue
        count = 1
        if isinstance(post_attack, dict):
            count = max(1, _safe_int(post_attack.get("count", post_attack.get("hits", 1)), 1))
        post_attack_ability_damage.append(
            PostAttackAbilityDamageEffect(
                ratio=ratio,
                count=count,
                duration=_effect_duration(post_attack if isinstance(post_attack, dict) else None, default_duration),
                undispellable=_effect_undispellable(post_attack, fallback_undispellable),
                target=_effect_target(post_attack),
            )
        )

    ability_recast: list[AbilityRecastEffect] = []
    recast_raw = raw.get("ability_recast", raw.get("ability_reactivation", raw.get("ability_repeat", [])))
    recast_rows = recast_raw if isinstance(recast_raw, list) else [recast_raw]
    for recast in recast_rows:
        if isinstance(recast, dict):
            count = max(1, _safe_int(recast.get("count", recast.get("recasts", recast.get("times", 1))), 1))
            duration = _effect_duration(recast, default_duration)
            undispellable = _effect_undispellable(recast, fallback_undispellable)
            target = _effect_target(recast)
        elif recast:
            count = max(1, _safe_int(recast, 1))
            duration = _effect_duration(None, default_duration)
            undispellable = fallback_undispellable
            target = "self"
        else:
            continue
        ability_recast.append(
            AbilityRecastEffect(
                count=count,
                duration=duration,
                undispellable=undispellable,
                target=target,
            )
        )

    dispel_guard: list[DispelGuardEffect] = []
    for guard in _guard_rows(raw.get("dispel_guard")):
        dispel_guard.append(
            DispelGuardEffect(
                duration=_guard_duration(guard, default_duration),
                count=_guard_count(guard),
                undispellable=_effect_undispellable(guard, fallback_undispellable),
                target=_effect_target(guard),
            )
        )

    veil: list[VeilEffect] = []
    for guard in [*_guard_rows(raw.get("veil")), *_guard_rows(raw.get("mount"))]:
        veil.append(
            VeilEffect(
                duration=_guard_duration(guard, default_duration),
                count=_guard_count(guard),
                undispellable=_effect_undispellable(guard, fallback_undispellable),
                target=_effect_target(guard),
            )
        )

    return CombatSpecialEffects(
        flurry=flurry,
        double_strike=double_strike,
        bonus_damage=bonus_damage,
        critical_reinforce=critical_reinforce,
        final_damage=final_damage,
        post_attack_ability_damage=post_attack_ability_damage,
        ability_recast=ability_recast,
        dispel_guard=dispel_guard,
        veil=veil,
    )


def _stat_effects(
    raw: Any,
    legacy_mods: Any,
    default_duration: int,
    fallback_undispellable: bool = False,
) -> list[StatEffect]:
    effects: list[StatEffect] = []
    rows = raw if isinstance(raw, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stat = str(row.get("stat", row.get("key", "")))
        value = _safe_float(row.get("value"), 0.0)
        if not stat or value == 0:
            continue
        effects.append(
            StatEffect(
                stat=stat,
                value=value,
                duration=_effect_duration(row, default_duration),
                target=_stat_effect_target(row),
                undispellable=_effect_undispellable(row, fallback_undispellable),
                heal_cap=_heal_cap(row),
            )
        )
    if effects:
        return effects
    return [
        StatEffect(
            stat=stat,
            value=value,
            duration=_effect_duration(None, default_duration),
            target="self",
            undispellable=fallback_undispellable,
        )
        for stat, value in _stats(legacy_mods).items()
        if value
    ]


def _stat_effect_target(row: dict[str, Any]) -> str:
    target = str(row.get("target", "self") or "self")
    if target in {"ally", "allies", "party"}:
        return "allies"
    return "self"


def _stat_effect_totals(effects: list[StatEffect]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for effect in effects:
        totals[effect.stat] = totals.get(effect.stat, 0.0) + effect.value
    return totals


def _effect_actions(raw: Any) -> list[EffectAction]:
    rows = raw if isinstance(raw, list) else []
    actions: list[EffectAction] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_action = str(row.get("action", row.get("type", "")) or "")
        operation = str(row.get("operation", row.get("op", "")) or "")
        action = _stack_action(raw_action, operation)
        if action not in {"dispel", "clear_all", *STACK_EFFECT_ACTIONS}:
            continue
        value = max(1, _safe_int(row.get("value", row.get("stacks", row.get("count", 1))), 1))
        raw_conditions = row.get("conditions", row.get("stack_conditions", []))
        if not isinstance(raw_conditions, list):
            raw_conditions = []
        actions.append(
            EffectAction(
                action=action,
                target=str(row.get("target", _effect_action_default_target(action)) or _effect_action_default_target(action)),
                count=max(1, _safe_int(row.get("count"), 1)),
                stack_effect_id=str(row.get("stack_effect_id", row.get("effect_id", "")) or ""),
                value=value,
                conditions=[
                    condition
                    for condition in (
                        _effect_action_stack_condition(condition_raw)
                        for condition_raw in raw_conditions
                        if isinstance(condition_raw, dict)
                    )
                    if condition.stack_effect_id
                ],
            )
        )
    return actions


def _effect_action_default_target(action: str) -> str:
    return "self" if action in STACK_EFFECT_ACTIONS else "enemy"


def _effect_action_stack_condition(raw: dict[str, Any]) -> EffectActionStackCondition:
    min_stacks = _safe_int(raw.get("min_stacks", raw.get("min", raw.get("stacks", 1))), 1)
    max_stacks = _safe_int(raw.get("max_stacks", raw.get("max", -1)), -1)
    return EffectActionStackCondition(
        stack_effect_id=str(raw.get("stack_effect_id", raw.get("effect_id", raw.get("id", ""))) or ""),
        target=_effect_action_stack_condition_target(raw.get("target", "self")),
        min_stacks=max(0, min_stacks),
        max_stacks=max_stacks,
    )


def _effect_action_stack_condition_target(value: Any) -> str:
    target = str(value or "self")
    if target in {"boss"}:
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


def _stack_action(action: str, operation: str = "") -> str:
    if action in STACK_EFFECT_ACTIONS:
        return action
    if action in {"stack", "stack_effect"}:
        op = operation or "increase"
        return f"stack_{op}"
    return action


def _stack_condition_target(value: Any) -> str:
    target = str(value or "self")
    if target in {"none", "event", "warning"}:
        return "none"
    if target in {"me", "holder"}:
        return "self"
    if target in {"enemy", "opponent"}:
        return "opponent"
    return "self"


def _stack_effect_condition(raw: dict[str, Any]) -> StackEffectCondition:
    operation = str(raw.get("operation", raw.get("op", "increase")) or "increase")
    action = _stack_action("stack", operation)
    return StackEffectCondition(
        objective=str(raw.get("objective", raw.get("kind", "damage")) or "damage"),
        target=_stack_condition_target(raw.get("target")),
        operation=action.removeprefix("stack_"),
        value=max(1, _safe_int(raw.get("value", raw.get("stacks", 1)), 1)),
        required=max(1, _safe_int(raw.get("required"), 1)),
        min_damage=max(0, _safe_int(raw.get("min_damage"), 0)),
    )


def _stack_effect_tier(raw: dict[str, Any]) -> StackEffectTier:
    return StackEffectTier(
        stack=max(1, _safe_int(raw.get("stack", raw.get("stacks", 1)), 1)),
        stat_effects=_stat_effects(
            raw.get("stat_effects"),
            raw.get("mods"),
            INFINITE_EFFECT_TURNS,
            True,
        ),
        effects=_combat_effects(raw.get("effects"), INFINITE_EFFECT_TURNS, True),
    )


def _stack_effect_template(raw: dict[str, Any]) -> StackEffectTemplate:
    max_stacks = max(1, _safe_int(raw.get("max_stacks", raw.get("max", 1)), 1))
    tiers = [
        _stack_effect_tier(tier)
        for tier in raw.get("tiers", raw.get("stacks", []))
        if isinstance(tier, dict)
    ]
    return StackEffectTemplate(
        id=str(raw["id"]),
        name=str(raw.get("name", raw["id"])),
        max_stacks=max_stacks,
        description=str(raw.get("description", "")),
        tiers=sorted(tiers, key=lambda tier: tier.stack),
        conditions=[
            _stack_effect_condition(condition)
            for condition in raw.get("conditions", [])
            if isinstance(condition, dict)
        ],
    )


def _base_price(rarity: str, stats: dict[str, float]) -> int:
    power = 0.0
    for key, value in stats.items():
        if key == "base_atk":
            power += value * 19
        elif key == "max_hp":
            power += value * 2.2
        elif key == "defense_ignore":
            power += value * 850
        elif key == "dmg_supplement":
            power += value * 24
        elif key == "skill_dmg_supplement":
            power += value * 18
        elif key == "dmg_mitigation":
            power += value * 30
        else:
            power += value * 900
    richness = 1 + 0.16 * max(0, len(stats) - 2)
    return round((80 + power) * RARITY_PRICE_MULTIPLIERS[rarity] * richness)


def _item(raw: dict[str, Any]) -> ItemTemplate:
    stats = _stats(raw.get("stats"))
    rarity = str(raw["rarity"])
    undispellable = bool(raw.get("undispellable", True))
    return ItemTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        rarity=rarity,
        stats=stats,
        base_price=int(raw.get("base_price") or _base_price(rarity, stats)),
        fixed_stats=_fixed_stats(raw.get("fixed_stats"), stats),
        stat_effects=_stat_effects(raw.get("stat_effects"), None, INFINITE_EFFECT_TURNS, undispellable),
        effects=_combat_effects(raw.get("effects"), INFINITE_EFFECT_TURNS, undispellable),
        undispellable=undispellable,
        excluded_from_gacha=bool(raw.get("excluded_from_gacha", False)),
    )


def _job(raw: dict[str, Any]) -> JobTemplate:
    undispellable = bool(raw.get("undispellable", True))
    return JobTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        tier=int(raw["tier"]),
        level_req=int(raw["level_req"]),
        parent_id=str(raw.get("parent_id", "")),
        stats=_stats(raw.get("stats")),
        stat_effects=_stat_effects(raw.get("stat_effects"), None, INFINITE_EFFECT_TURNS, undispellable),
        effects=_combat_effects(raw.get("effects"), INFINITE_EFFECT_TURNS, undispellable),
        undispellable=undispellable,
        description=str(raw.get("description", "")),
    )


def _skill(raw: dict[str, Any]) -> SkillTemplate:
    duration = int(raw.get("duration", 0))
    damage_cut = float(raw.get("damage_cut", 0.0))
    player_undispellable = bool(raw.get("player_undispellable", raw.get("undispellable", False)))
    enemy_undispellable = bool(raw.get("enemy_undispellable", False))
    player_stat_effects = _stat_effects(
        raw.get("player_stat_effects"),
        raw.get("player_mods"),
        duration,
        player_undispellable,
    )
    enemy_stat_effects = _stat_effects(
        raw.get("enemy_stat_effects"),
        raw.get("enemy_mods"),
        duration,
        enemy_undispellable,
    )
    if damage_cut > 0 and not any(effect.stat == "damage_cut" for effect in player_stat_effects):
        player_stat_effects.append(
            StatEffect(
                stat="damage_cut",
                value=damage_cut,
                duration=_effect_duration(None, duration),
                undispellable=player_undispellable,
            )
        )
    return SkillTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        unlock_level=int(raw["unlock_level"]),
        uses=int(raw.get("uses", 0)),
        cooldown=int(raw.get("cooldown", 0)),
        role=str(raw.get("role", "attack")),
        damage_multiplier=float(raw.get("damage_multiplier", 0.0)),
        hits=int(raw.get("hits", 0)),
        player_mods=_stat_effect_totals(player_stat_effects),
        enemy_mods=_stat_effect_totals(enemy_stat_effects),
        player_stat_effects=player_stat_effects,
        enemy_stat_effects=enemy_stat_effects,
        player_effects=_combat_effects(raw.get("player_effects", raw.get("effects")), duration, player_undispellable),
        enemy_effects=_combat_effects(raw.get("enemy_effects"), duration, enemy_undispellable),
        effect_actions=_effect_actions(raw.get("effect_actions")),
        player_undispellable=player_undispellable,
        enemy_undispellable=enemy_undispellable,
        duration=duration,
        heal_power=float(raw.get("heal_power", 0.0)),
        heal_cap=_heal_cap(raw),
        heal_target=_target_value(raw.get("heal_target", raw.get("healTarget", "self"))),
        damage_cut=damage_cut,
        job_ids=tuple(str(job_id) for job_id in raw.get("job_ids", ())),
        note=str(raw.get("note", "")),
    )


def _material(raw: dict[str, Any]) -> MaterialTemplate:
    return MaterialTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        rarity=str(raw.get("rarity", "normal")),
        description=str(raw.get("description", "")),
        emoji=str(raw.get("emoji", "")),
    )


def _reward_item_drop(raw: dict[str, Any]) -> RewardItemDrop:
    minimum = max(1, _safe_int(raw.get("min", raw.get("amount", 1)), 1))
    maximum = max(minimum, _safe_int(raw.get("max", minimum), minimum))
    return RewardItemDrop(
        chance=_clamped_chance(raw.get("chance", 0.0), 0.0),
        template_id=str(raw.get("template_id", raw.get("item_id", ""))),
        rarity=str(raw.get("rarity", "")),
        stars=max(0, _safe_int(raw.get("stars", 0), 0)),
        min=minimum,
        max=maximum,
        owner_chance=_optional_chance(raw, "owner_chance"),
        owner_min=_optional_positive_int(raw, "owner_min"),
        owner_max=_optional_positive_int(raw, "owner_max"),
        participant_chance=_optional_chance(raw, "participant_chance"),
        participant_min=_optional_positive_int(raw, "participant_min"),
        participant_max=_optional_positive_int(raw, "participant_max"),
    )


def _reward_material_drop(raw: dict[str, Any]) -> RewardMaterialDrop:
    minimum = max(1, _safe_int(raw.get("min", raw.get("amount", 1)), 1))
    maximum = max(minimum, _safe_int(raw.get("max", minimum), minimum))
    return RewardMaterialDrop(
        id=str(raw["id"]),
        chance=_clamped_chance(raw.get("chance", 1.0), 1.0),
        min=minimum,
        max=maximum,
        owner_chance=_optional_chance(raw, "owner_chance"),
        owner_min=_optional_positive_int(raw, "owner_min"),
        owner_max=_optional_positive_int(raw, "owner_max"),
        participant_chance=_optional_chance(raw, "participant_chance"),
        participant_min=_optional_positive_int(raw, "participant_min"),
        participant_max=_optional_positive_int(raw, "participant_max"),
    )


def _reward(raw: dict[str, Any] | None) -> RewardTemplate:
    raw = raw or {}
    item_drops = [
        _reward_item_drop(item)
        for item in raw.get("items", [])
        if isinstance(item, dict)
    ]
    material_drops = [
        _reward_material_drop(material)
        for material in raw.get("materials", [])
        if isinstance(material, dict) and material.get("id")
    ]
    return RewardTemplate(
        item_drops=item_drops,
        material_drops=material_drops,
    )


def _gacha_entry(raw: dict[str, Any]) -> GachaEntry:
    minimum = max(1, _safe_int(raw.get("min", raw.get("amount", 1)), 1))
    maximum = max(minimum, _safe_int(raw.get("max", minimum), minimum))
    raw_item_ids = raw.get("item_ids", raw.get("items", []))
    raw_material_ids = raw.get("material_ids", raw.get("materials", []))
    item_amounts = _gacha_target_amounts(raw_item_ids)
    material_amounts = _gacha_target_amounts(raw_material_ids, minimum)
    return GachaEntry(
        type=str(raw.get("type", "item_rarity")),
        chance=max(0.0, float(raw.get("chance", raw.get("weight", 0.0)))),
        item_ids=tuple(item_amounts.keys()),
        material_ids=tuple(material_amounts.keys()),
        item_amounts=item_amounts,
        material_amounts=material_amounts,
        rarity=str(raw.get("rarity", "")),
        stars=max(0, int(raw.get("stars", 0))),
        min=minimum,
        max=maximum,
    )


def _gacha_target_amounts(raw_targets: Any, default_amount: int = 1) -> dict[str, int]:
    if not isinstance(raw_targets, list):
        return {}
    targets: dict[str, int] = {}
    for raw_target in raw_targets:
        if isinstance(raw_target, dict):
            target_id = str(raw_target.get("id", raw_target.get("item_id", raw_target.get("material_id", ""))))
            amount = max(1, _safe_int(raw_target.get("amount"), default_amount))
        else:
            target_id = str(raw_target)
            amount = max(1, default_amount)
        if not target_id:
            continue
        targets[target_id] = amount
    return targets


def _gacha_pool(raw: dict[str, Any], defaults: dict[str, Any]) -> GachaPool:
    return GachaPool(
        id=str(raw.get("id", "default")),
        name=str(raw.get("name", raw.get("id", "기본 가챠"))),
        description=str(raw.get("description", "")),
        cost_material_id=str(raw.get("material_id", defaults.get("material_id", "crystal"))),
        cost_material_amount=max(1, int(raw.get("cost", defaults.get("cost", 3000)))),
        draws=max(1, int(raw.get("draws", defaults.get("draws", 10)))),
        entries=[
            _gacha_entry(entry)
            for entry in raw.get("entries", [])
            if isinstance(entry, dict)
        ],
    )


def _cost_materials(raw: Any) -> dict[str, int]:
    if isinstance(raw, dict):
        return {
            str(material_id): max(1, _safe_int(amount, 1))
            for material_id, amount in raw.items()
            if str(material_id)
        }
    if isinstance(raw, list):
        costs: dict[str, int] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            material_id = str(entry.get("id", entry.get("material_id", "")))
            if not material_id:
                continue
            costs[material_id] = costs.get(material_id, 0) + max(1, _safe_int(entry.get("amount", 1), 1))
        return costs
    return {}


def _enhancement_method(raw: dict[str, Any], index: int) -> EnhancementMethod:
    gold_raw = raw.get("gold", raw.get("gold_cost", {}))
    if isinstance(gold_raw, dict):
        gold_mode = str(gold_raw.get("mode", "formula") or "formula")
        gold_amount = max(0, _safe_int(gold_raw.get("amount", gold_raw.get("value", 0)), 0))
    else:
        gold_mode = "fixed"
        gold_amount = max(0, _safe_int(gold_raw, 0))
    if gold_mode not in {"formula", "fixed", "none"}:
        gold_mode = "formula"

    odds_raw = raw.get("odds", {})
    odds_raw = odds_raw if isinstance(odds_raw, dict) else {}
    odds_mode = str(odds_raw.get("mode", "formula") or "formula")
    if odds_mode not in {"formula", "fixed"}:
        odds_mode = "formula"

    def optional_chance(key: str) -> float | None:
        if key not in odds_raw or odds_raw.get(key) in (None, ""):
            return None
        return _clamped_chance(odds_raw.get(key), 0.0)

    return EnhancementMethod(
        id=str(raw.get("id", f"method_{index}")),
        name=str(raw.get("name", raw.get("id", f"강화 방식 {index}"))),
        description=str(raw.get("description", "")),
        gold_cost_mode=gold_mode,
        gold_cost=gold_amount,
        material_costs=_cost_materials(raw.get("materials", raw.get("material_costs", {}))),
        odds_mode=odds_mode,
        success=optional_chance("success"),
        fail=optional_chance("fail"),
        destroy=optional_chance("destroy"),
        min_stars=max(0, _safe_int(raw.get("min_stars", 0), 0)),
        max_stars=max(1, _safe_int(raw.get("max_stars", MAX_ENHANCEMENT_STARS), MAX_ENHANCEMENT_STARS)),
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
    return EnemyTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        weight=int(raw["weight"]),
        stats=_stats(raw.get("stats")),
        gold=gold,
        exp=exp,
        description=str(raw.get("description", "")),
        rare=bool(raw.get("rare", False)),
        rewards=_reward(raw.get("rewards")),
    )


def _dungeon(raw: dict[str, Any]) -> DungeonTemplate:
    return DungeonTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        level_req=int(raw["level_req"]),
        enemies=[_enemy(enemy) for enemy in raw.get("enemies", [])],
        description=str(raw.get("description", "")),
    )


def _plain_damage(raw: Any) -> PlainDamage:
    if raw in (None, "", 0, 0.0):
        return PlainDamage()
    if not isinstance(raw, dict):
        return PlainDamage(mode="flat", value=max(0.0, _safe_float(raw, 0.0)))
    mode = str(raw.get("mode", raw.get("type", "flat")) or "flat")
    if mode in {"fixed", "amount", "value"}:
        mode = "flat"
    elif mode in {"target_max_hp", "target_max_hp_percent", "max_hp", "max_hp_ratio", "max_hp_percent", "hp_percent", "percent", "ratio"}:
        mode = "target_max_hp_ratio"
    elif mode not in {"none", "flat", "target_max_hp_ratio"}:
        mode = "none"
    value = max(0.0, _safe_float(raw.get("value", raw.get("amount", raw.get("ratio", raw.get("percent", 0.0)))), 0.0))
    if mode == "target_max_hp_ratio" and ("percent" in raw or value > 1):
        value /= 100.0
    return PlainDamage(mode=mode, value=value)


def _hp_loss_ratio(raw: dict[str, Any]) -> float:
    value = raw.get(
        "self_hp_loss_ratio",
        raw.get("self_hp_loss", raw.get("hp_loss_ratio", raw.get("hp_loss", 0.0))),
    )
    if isinstance(value, dict):
        ratio = _safe_float(value.get("value", value.get("ratio", value.get("amount", value.get("percent", 0.0)))), 0.0)
        if "percent" in value:
            ratio /= 100.0
        return max(0.0, ratio)
    return max(0.0, _safe_float(value, 0.0))


def _boss_pattern(raw: dict[str, Any]) -> BossPattern:
    duration = int(raw.get("duration", 0))
    player_undispellable = bool(raw.get("player_undispellable", False))
    boss_undispellable = bool(raw.get("boss_undispellable", raw.get("undispellable", False)))
    player_stat_effects = _stat_effects(
        raw.get("player_stat_effects"),
        raw.get("player_mods"),
        duration,
        player_undispellable,
    )
    boss_stat_effects = _stat_effects(
        raw.get("boss_stat_effects"),
        raw.get("boss_mods"),
        duration,
        boss_undispellable,
    )
    return BossPattern(
        id=str(raw.get("id", "")),
        threshold=_hp_threshold(raw.get("threshold", 0.0)),
        name=str(raw["name"]),
        damage_multiplier=float(raw.get("damage_multiplier", 0.0)),
        hits=int(raw.get("hits", 0)),
        plain_damage=_plain_damage(raw.get("plain_damage", raw.get("neutral_damage", raw.get("true_damage")))),
        self_hp_loss_ratio=_hp_loss_ratio(raw),
        player_mods=_stat_effect_totals(player_stat_effects),
        boss_mods=_stat_effect_totals(boss_stat_effects),
        player_stat_effects=player_stat_effects,
        boss_stat_effects=boss_stat_effects,
        player_effects=_combat_effects(raw.get("player_effects"), duration, player_undispellable),
        boss_effects=_combat_effects(raw.get("boss_effects", raw.get("effects")), duration, boss_undispellable),
        effect_actions=_effect_actions(raw.get("effect_actions")),
        player_undispellable=player_undispellable,
        boss_undispellable=boss_undispellable,
        duration=duration,
    )


def _warning_pattern(raw: dict[str, Any], fallback_id: str, fallback_name: str) -> BossPattern | None:
    pattern = raw.get("pattern")
    if not isinstance(pattern, dict):
        return None
    normalized = dict(pattern)
    normalized["id"] = str(raw.get("warning_id", raw.get("id", fallback_id)) or fallback_id)
    normalized["name"] = str(raw.get("name", fallback_name) or fallback_name)
    return _boss_pattern(normalized)


def _warning_success_pattern(raw: dict[str, Any], warning_id: str, warning_name: str) -> BossPattern | None:
    pattern = raw.get("success_pattern", raw.get("success_effect", raw.get("on_success")))
    if not isinstance(pattern, dict):
        return None
    normalized = dict(pattern)
    normalized["id"] = str(normalized.get("id", f"{warning_id}_success") or f"{warning_id}_success")
    normalized["name"] = str(normalized.get("name", f"{warning_name} 성공 효과") or f"{warning_name} 성공 효과")
    return _boss_pattern(normalized)


def _warning_failure_stack_condition(raw: dict[str, Any]) -> BossWarningFailureStackCondition:
    target = str(raw.get("target", "boss") or "boss")
    if target in {"player", "self", "participant", "user"}:
        target = "player"
    else:
        target = "boss"
    return BossWarningFailureStackCondition(
        stack_effect_id=str(raw.get("stack_effect_id", raw.get("effect_id", raw.get("id", ""))) or ""),
        target=target,
        min_stacks=max(0, _safe_int(raw.get("min_stacks", raw.get("min", raw.get("stacks", 1))), 1)),
        max_stacks=_safe_int(raw.get("max_stacks", raw.get("max", -1)), -1),
    )


def _warning_activation_condition_kind(raw: Any) -> str:
    kind = str(raw or "stack")
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


def _warning_activation_condition_target(raw: Any) -> str:
    target = str(raw or "boss")
    if target in {"player", "self", "participant", "user"}:
        return "player"
    return "boss"


def _warning_activation_condition(raw: dict[str, Any]) -> BossWarningActivationCondition:
    kind = _warning_activation_condition_kind(raw.get("kind", raw.get("type", raw.get("condition", "stack"))))
    if kind not in WARNING_ACTIVATION_CONDITIONS:
        kind = "stack"
    min_turn = max(1, _safe_int(raw.get("min_turn", raw.get("min", raw.get("turn", 1))), 1))
    max_turn = _safe_int(raw.get("max_turn", raw.get("max", -1)), -1)
    min_ratio_raw = raw.get("min_ratio", raw.get("min_hp", raw.get("min_hp_ratio", raw.get("min", 0.0))))
    max_ratio_raw = raw.get("max_ratio", raw.get("max_hp", raw.get("max_hp_ratio", raw.get("max", 1.0))))
    return BossWarningActivationCondition(
        kind=kind,
        stack_effect_id=str(raw.get("stack_effect_id", raw.get("effect_id", raw.get("id", ""))) or ""),
        target=_warning_activation_condition_target(raw.get("target", "boss")),
        min_stacks=max(0, _safe_int(raw.get("min_stacks", raw.get("min", raw.get("stacks", 1))), 1)),
        max_stacks=_safe_int(raw.get("max_stacks", raw.get("max", -1)), -1),
        multiple=max(1, _safe_int(raw.get("multiple", raw.get("mod", raw.get("divisor", raw.get("value", 1)))), 1)),
        min_turn=min_turn,
        max_turn=max_turn,
        min_ratio=_hp_threshold(min_ratio_raw),
        max_ratio=_hp_threshold(max_ratio_raw),
        ct_ready=_safe_bool(raw.get("ct_ready", raw.get("ready")), True),
    )


def _warning_activation_conditions(raw: dict[str, Any]) -> list[BossWarningActivationCondition]:
    conditions = raw.get(
        "activation_conditions",
        raw.get("trigger_conditions", raw.get("spawn_conditions", raw.get("conditions", []))),
    )
    if not isinstance(conditions, list):
        return []
    return [
        _warning_activation_condition(condition)
        for condition in conditions
        if isinstance(condition, dict)
    ]


def _warning_failure_variant(
    raw: dict[str, Any],
    index: int,
    warning_id: str,
    warning_name: str,
) -> BossWarningFailureVariant | None:
    conditions = [
        _warning_failure_stack_condition(condition)
        for condition in raw.get("conditions", [])
        if isinstance(condition, dict)
    ]
    pattern_raw = raw.get("pattern") if isinstance(raw.get("pattern"), dict) else raw
    normalized = dict(pattern_raw)
    normalized["id"] = str(normalized.get("id", f"{warning_id}_failure_variant_{index + 1}") or f"{warning_id}_failure_variant_{index + 1}")
    normalized["name"] = str(raw.get("name", normalized.get("name", f"{warning_name} 변형 {index + 1}")) or f"{warning_name} 변형 {index + 1}")
    return BossWarningFailureVariant(
        conditions=conditions,
        pattern=_boss_pattern(normalized),
        name=str(raw.get("name", normalized["name"]) or normalized["name"]),
    )


def _warning_objectives(
    raw: dict[str, Any],
    default_objective: str = "damage",
) -> list[BossWarningObjective]:
    objectives = raw.get("objectives")
    parsed: list[BossWarningObjective] = []
    if isinstance(objectives, list):
        for objective in objectives:
            if not isinstance(objective, dict):
                continue
            kind = str(objective.get("objective", objective.get("kind", default_objective)) or default_objective)
            parsed.append(
                BossWarningObjective(
                    objective=kind,
                    required=max(1, _safe_int(objective.get("required"), 1)),
                    min_damage=max(0, _safe_int(objective.get("min_damage"), 0)),
                )
            )
    if parsed:
        return parsed
    return [
        BossWarningObjective(
            objective=str(raw.get("objective", default_objective) or default_objective),
            required=max(1, _safe_int(raw.get("required"), 1)),
            min_damage=max(0, _safe_int(raw.get("min_damage"), 0)),
        )
    ]


def _warning_template(
    raw: dict[str, Any],
    index: int,
    prefix: str,
    default_objective: str,
) -> BossWarningTemplate:
    warning_id = str(raw.get("warning_id", raw.get("id", "")) or "")
    if not warning_id:
        warning_id = f"{prefix}_{index + 1}"
    warning_name = str(raw.get("name", "") or "")
    pattern = _warning_pattern(raw, warning_id, warning_name or warning_id)
    if not warning_name:
        warning_name = pattern.name if pattern is not None else warning_id
    pattern_id = warning_id if pattern is not None else str(raw.get("pattern_id", ""))
    success_pattern = _warning_success_pattern(raw, warning_id, warning_name or warning_id)
    success_warning_id = str(
        raw.get(
            "success_warning_id",
            raw.get("on_success_warning_id", raw.get("next_success_warning_id", "")),
        )
        or ""
    )
    failure_warning_id = str(
        raw.get(
            "failure_warning_id",
            raw.get("on_failure_warning_id", raw.get("next_failure_warning_id", "")),
        )
        or ""
    )
    failure_variants = [
        variant
        for index, variant_raw in enumerate(raw.get("failure_variants", []))
        if isinstance(variant_raw, dict)
        for variant in [_warning_failure_variant(variant_raw, index, warning_id, warning_name or warning_id)]
        if variant is not None
    ]
    return BossWarningTemplate(
        id=warning_id,
        name=warning_name,
        pattern_id=pattern_id,
        objectives=_warning_objectives(raw, default_objective),
        turns=max(1, _safe_int(raw.get("turns", raw.get("limit_turns", 1)), 1)),
        pattern=pattern,
        success_pattern=success_pattern,
        success_warning_id=success_warning_id,
        failure_warning_id=failure_warning_id,
        failure_variants=failure_variants,
        activation_conditions=_warning_activation_conditions(raw),
    )


def _hp_warning(
    raw: dict[str, Any],
    index: int,
    warning_by_id: dict[str, BossWarningTemplate],
) -> BossHPWarningTemplate:
    warning_id = str(raw.get("warning_id", "") or "")
    warning = warning_by_id.get(warning_id) if warning_id else None
    if warning is None:
        warning = _warning_template(raw, index, "hp_warning", "damage")
        warning_id = warning.id
    return BossHPWarningTemplate(
        threshold=_hp_threshold(raw["threshold"]),
        warning_id=warning_id,
        warning=warning,
    )


def _hp_thresholds(value: Any) -> list[float]:
    source = value if isinstance(value, list) else [value]
    thresholds = [_hp_threshold(threshold) for threshold in source]
    unique = sorted({round(threshold, 6) for threshold in thresholds}, reverse=True)
    return unique or [0.0]


def _hp_effect_pattern_id(base_id: str, threshold: float, threshold_count: int) -> str:
    if threshold_count <= 1:
        return base_id
    threshold_key = int(round(max(0.0, min(1.0, threshold)) * 10000))
    return f"{base_id}_hp_{threshold_key:04d}"


def _hp_instant_effects(raw: dict[str, Any], index: int) -> list[BossHPInstantEffectTemplate]:
    pattern_raw = raw.get("pattern") if isinstance(raw.get("pattern"), dict) else raw
    normalized = dict(pattern_raw)
    fallback_id = str(raw.get("id", f"hp_effect_{index + 1}") or f"hp_effect_{index + 1}")
    fallback_name = str(raw.get("name", f"HP 즉시 효과 {index + 1}") or f"HP 즉시 효과 {index + 1}")
    normalized["id"] = str(normalized.get("id", fallback_id) or fallback_id)
    normalized["name"] = str(normalized.get("name", fallback_name) or fallback_name)
    thresholds = _hp_thresholds(raw.get("thresholds", raw.get("threshold", normalized.get("threshold", 0.0))))
    effects: list[BossHPInstantEffectTemplate] = []
    for threshold in thresholds:
        threshold_pattern = dict(normalized)
        threshold_pattern["threshold"] = threshold
        threshold_pattern["id"] = _hp_effect_pattern_id(normalized["id"], threshold, len(thresholds))
        effects.append(
            BossHPInstantEffectTemplate(
                threshold=threshold,
                pattern=_boss_pattern(threshold_pattern),
            )
        )
    return effects


def _ct_gauge(raw: dict[str, Any]) -> BossCTGaugeTemplate:
    return BossCTGaugeTemplate(
        above=_hp_threshold(raw.get("above", 0.0)),
        max=max(1, int(raw.get("max", 1))),
    )


def _warning_trigger_ids(raw: dict[str, Any]) -> list[str]:
    source = raw.get("warning_ids")
    if source is None:
        source = raw.get("warning_id", "")
    if not isinstance(source, list):
        source = [source]
    ids: list[str] = []
    for value in source:
        warning_id = str(value or "")
        if warning_id and warning_id not in ids:
            ids.append(warning_id)
    return ids


def _ct_warning(
    raw: dict[str, Any],
    index: int,
    warning_by_id: dict[str, BossWarningTemplate],
) -> BossCTWarningTemplate:
    warning_ids = _warning_trigger_ids(raw)
    warnings = [
        warning_by_id[warning_id]
        for warning_id in warning_ids
        if warning_id in warning_by_id
    ]
    if not warning_ids:
        warning = _warning_template(raw, index, "ct_warning", "hits")
        warning_id = warning.id
        warning_ids = [warning_id]
        warnings = [warning]
    else:
        warning_id = warning_ids[0]
    return BossCTWarningTemplate(
        above=_hp_threshold(raw.get("above", 0.0)),
        warning_id=warning_id,
        warning=warnings[0] if warnings else None,
        warning_ids=tuple(warning_ids),
        warnings=tuple(warnings),
    )


def _boss_stack_effect(raw: dict[str, Any]) -> BossStackEffectTemplate:
    stack_effect_id = str(raw.get("stack_effect_id", raw.get("id", raw.get("effect_id", ""))) or "")
    return BossStackEffectTemplate(
        stack_effect_id=stack_effect_id,
        initial_stacks=max(0, _safe_int(raw.get("initial_stacks", raw.get("stacks", 0)), 0)),
    )


def _hp_threshold(value: Any) -> float:
    threshold = _safe_float(value, 0.0)
    if threshold > 1:
        threshold /= 100.0
    return max(0.0, min(1.0, threshold))


def _boss(raw: dict[str, Any]) -> BossTemplate:
    patterns = [_boss_pattern(pattern) for pattern in raw.get("patterns", [])]
    warnings = [
        _warning_template(warning, index, "warning", "damage")
        for index, warning in enumerate(raw.get("warnings", []))
    ]
    warning_by_id = {
        warning.id: warning
        for warning in warnings
        if warning.id
    }
    ct = raw.get("ct", {})
    gold = int(raw["gold"])
    exp = int(raw["exp"])
    hp_warnings = sorted(
        [_hp_warning(warning, index, warning_by_id) for index, warning in enumerate(raw.get("hp_warnings", []))],
        key=lambda warning: warning.threshold,
        reverse=True,
    )
    hp_effect_rows = raw.get("hp_effects", raw.get("hp_instant_effects", raw.get("instant_hp_effects", [])))
    hp_effects = sorted(
        [
            hp_effect
            for index, effect in enumerate(hp_effect_rows)
            if isinstance(effect, dict)
            for hp_effect in _hp_instant_effects(effect, index)
        ],
        key=lambda effect: effect.threshold,
        reverse=True,
    )
    hp_lock_rows = raw.get("hp_locks", raw.get("hp_lock_thresholds", []))
    hp_lock_rows = hp_lock_rows if isinstance(hp_lock_rows, list) else []
    hp_locks = sorted(
        {
            round(_hp_threshold(row.get("threshold", row.get("hp", row.get("value", 0.0))) if isinstance(row, dict) else row), 6)
            for row in hp_lock_rows
        },
        reverse=True,
    )
    hp_locks = [threshold for threshold in hp_locks if 0.0 < threshold < 1.0]
    ct_warnings = sorted(
        [_ct_warning(warning, index, warning_by_id) for index, warning in enumerate(ct.get("warnings_by_hp", []))],
        key=lambda warning: warning.above,
        reverse=True,
    )
    direct_warnings = [
        template
        for warning in [*hp_warnings, *ct_warnings]
        for template in (
            list(getattr(warning, "warnings", ()))
            or ([warning.warning] if warning.warning is not None else [])
        )
        if template is not None and template.id not in warning_by_id
    ]
    all_warnings = [*warnings, *direct_warnings]
    warning_by_id = {
        warning.id: warning
        for warning in all_warnings
        if warning.id
    }
    direct_patterns = [
        warning.pattern
        for warning in all_warnings
        if warning.pattern is not None
    ]
    success_patterns = [
        warning.success_pattern
        for warning in all_warnings
        if warning.success_pattern is not None
    ]
    variant_patterns = [
        variant.pattern
        for warning in all_warnings
        for variant in warning.failure_variants
    ]
    hp_effect_patterns = [effect.pattern for effect in hp_effects]
    all_patterns = [*patterns, *direct_patterns, *success_patterns, *variant_patterns, *hp_effect_patterns]
    pattern_by_id = {
        pattern.id or pattern.name: pattern
        for pattern in all_patterns
    }
    return BossTemplate(
        id=str(raw["id"]),
        name=str(raw["name"]),
        level_req=int(raw["level_req"]),
        stats=_stats(raw.get("stats")),
        gold=gold,
        exp=exp,
        patterns=all_patterns,
        warnings=all_warnings,
        description=str(raw.get("description", "")),
        hp_warnings=hp_warnings,
        hp_effects=hp_effects,
        hp_locks=hp_locks,
        ct_gauge=sorted(
            [_ct_gauge(rule) for rule in ct.get("gauge_by_hp", [])],
            key=lambda rule: rule.above,
            reverse=True,
        ),
        ct_warnings=ct_warnings,
        stack_effects=[
            _boss_stack_effect(effect)
            for effect in raw.get("stack_effects", [])
            if isinstance(effect, dict)
        ],
        pattern_by_id=pattern_by_id,
        warning_by_id=warning_by_id,
        rewards=_reward(raw.get("rewards")),
    )


_SETTINGS = CONTENT.get("settings", {})
DAILY_EXPLORES = _env_int("KALING_DAILY_EXPLORES", int(_SETTINGS.get("daily_explores", 7)))
EXPLORE_LIMIT_ENABLED = _env_bool("KALING_EXPLORE_LIMIT_ENABLED", bool(_SETTINGS.get("explore_limit_enabled", False)))
BOSS_WEEKLY_REWARD_LIMIT_ENABLED = _env_bool(
    "KALING_BOSS_WEEKLY_REWARD_LIMIT_ENABLED",
    bool(_SETTINGS.get("boss_weekly_reward_limit_enabled", False)),
)
MAX_EQUIPPED_ITEMS = _env_int("KALING_MAX_EQUIPPED_ITEMS", int(_SETTINGS.get("max_equipped_items", 4)))
MAX_EQUIPPED_SKILLS = _env_int("KALING_MAX_EQUIPPED_SKILLS", int(_SETTINGS.get("max_equipped_skills", 4)))
MAX_ENHANCEMENT_STARS = _env_int("KALING_MAX_ENHANCEMENT_STARS", int(_SETTINGS.get("max_enhancement_stars", 10)))
_LEVEL_UP_GROWTH = _SETTINGS.get("level_up_growth", {})
if not isinstance(_LEVEL_UP_GROWTH, dict):
    _LEVEL_UP_GROWTH = {}
LEVEL_UP_BASE_ATK = _env_float("KALING_LEVEL_UP_BASE_ATK", _safe_float(_LEVEL_UP_GROWTH.get("base_atk"), 1.0))
LEVEL_UP_MAX_HP = _env_float("KALING_LEVEL_UP_MAX_HP", _safe_float(_LEVEL_UP_GROWTH.get("max_hp"), 5.0))
LEVEL_UP_DEFENSE = _env_float("KALING_LEVEL_UP_DEFENSE", _safe_float(_LEVEL_UP_GROWTH.get("defense"), 0.025))
_DEFAULT_LEVEL_DAMAGE_MULTIPLIERS = (1.0, 1.05, 1.1, 1.15, 1.2, 1.25)
_LEVEL_DAMAGE_MULTIPLIERS_RAW = _SETTINGS.get("level_damage_multipliers", _DEFAULT_LEVEL_DAMAGE_MULTIPLIERS)
if not isinstance(_LEVEL_DAMAGE_MULTIPLIERS_RAW, list) or not _LEVEL_DAMAGE_MULTIPLIERS_RAW:
    _LEVEL_DAMAGE_MULTIPLIERS_RAW = list(_DEFAULT_LEVEL_DAMAGE_MULTIPLIERS)
LEVEL_DAMAGE_MULTIPLIERS = tuple(
    max(0.0, _safe_float(value, _DEFAULT_LEVEL_DAMAGE_MULTIPLIERS[min(index, len(_DEFAULT_LEVEL_DAMAGE_MULTIPLIERS) - 1)]))
    for index, value in enumerate(_LEVEL_DAMAGE_MULTIPLIERS_RAW)
)
_REWARD_MULTIPLIERS = _SETTINGS.get("reward_multipliers", {})
if not isinstance(_REWARD_MULTIPLIERS, dict):
    _REWARD_MULTIPLIERS = {}
REWARD_WIN_MULTIPLIER_MIN = _env_float("KALING_REWARD_WIN_MIN", _safe_float(_REWARD_MULTIPLIERS.get("win_min"), 1.0))
REWARD_WIN_MULTIPLIER_MAX = _env_float("KALING_REWARD_WIN_MAX", _safe_float(_REWARD_MULTIPLIERS.get("win_max"), 1.2))
REWARD_LOSS_MULTIPLIER = _env_float("KALING_REWARD_LOSS", _safe_float(_REWARD_MULTIPLIERS.get("loss"), 0.2))

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
_ENHANCEMENT = CONTENT.get("enhancement", {})

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
MATERIALS_BY_RARITY = {
    rarity: [material for material in MATERIALS if material.rarity == rarity]
    for rarity in RARITIES
}

_ENHANCEMENT_METHOD_ROWS = _ENHANCEMENT.get("methods", [])
if not isinstance(_ENHANCEMENT_METHOD_ROWS, list) or not _ENHANCEMENT_METHOD_ROWS:
    _ENHANCEMENT_METHOD_ROWS = [
        {
            "id": "gold",
            "name": "일반 강화",
            "gold": {"mode": "formula", "amount": 0},
            "materials": {},
            "odds": {"mode": "formula"},
        }
    ]
ENHANCEMENT_METHODS = [
    _enhancement_method(method, index)
    for index, method in enumerate(_ENHANCEMENT_METHOD_ROWS, start=1)
    if isinstance(method, dict)
]
ENHANCEMENT_METHOD_BY_ID = {method.id: method for method in ENHANCEMENT_METHODS}
DEFAULT_ENHANCEMENT_METHOD_ID = ENHANCEMENT_METHODS[0].id if ENHANCEMENT_METHODS else "gold"

_GACHA_DATA = CONTENT.get("gacha", {})
GACHA_POOLS = [
    _gacha_pool(pool, _GACHA_DATA)
    for pool in _GACHA_DATA.get("pools", [])
    if isinstance(pool, dict)
]
GACHA_POOL_BY_ID = {pool.id: pool for pool in GACHA_POOLS}
GACHA_DEFAULT_POOL_ID = str(_GACHA_DATA.get("default_pool_id", GACHA_POOLS[0].id if GACHA_POOLS else ""))

CRAFTING_RECIPES = sorted(
    [_crafting_recipe(recipe) for recipe in CONTENT.get("crafting_recipes", [])],
    key=lambda recipe: (recipe.sort_order, recipe.level_req, recipe.name),
)
CRAFTING_RECIPE_BY_ID = {recipe.id: recipe for recipe in CRAFTING_RECIPES}

STACK_EFFECTS = [
    _stack_effect_template(effect)
    for effect in CONTENT.get("stack_effects", [])
    if isinstance(effect, dict)
]
STACK_EFFECT_BY_ID = {effect.id: effect for effect in STACK_EFFECTS}

DUNGEONS = [_dungeon(dungeon) for dungeon in CONTENT.get("dungeons", [])]
DUNGEON_BY_ID = {dungeon.id: dungeon for dungeon in DUNGEONS}

BOSSES = [_boss(boss) for boss in CONTENT.get("bosses", [])]
BOSS_BY_ID = {boss.id: boss for boss in BOSSES}


def _validate_content() -> None:
    errors: list[str] = []
    stack_effect_ids = [effect.id for effect in STACK_EFFECTS if effect.id]
    if len(stack_effect_ids) != len(set(stack_effect_ids)):
        errors.append("stack effects have duplicate ids")
    for effect in STACK_EFFECTS:
        if effect.max_stacks < 1:
            errors.append(f"stack effect {effect.id} max stacks must be at least 1")
        tier_stacks = [tier.stack for tier in effect.tiers]
        if len(tier_stacks) != len(set(tier_stacks)):
            errors.append(f"stack effect {effect.id} has duplicate tier stacks")
        for tier in effect.tiers:
            if tier.stack < 1 or tier.stack > effect.max_stacks:
                errors.append(f"stack effect {effect.id} tier out of range: {tier.stack}")
        for condition in effect.conditions:
            if condition.objective not in STACK_CONDITION_OBJECTIVES:
                errors.append(f"stack effect {effect.id} condition objective not found: {condition.objective}")
            if condition.operation not in {"increase", "decrease", "set", "remove", "max"}:
                errors.append(f"stack effect {effect.id} condition operation is invalid: {condition.operation}")
    for skill in SKILLS:
        errors.extend(_validate_effect_actions(skill.effect_actions, f"skill {skill.id} effect actions"))
    for recipe in CRAFTING_RECIPES:
        if recipe.result_item_id not in ITEM_BY_ID:
            errors.append(f"crafting recipe {recipe.id} result item not found: {recipe.result_item_id}")
        for material_id in recipe.materials:
            if material_id not in MATERIAL_BY_ID:
                errors.append(f"crafting recipe {recipe.id} material not found: {material_id}")
    method_ids = [method.id for method in ENHANCEMENT_METHODS if method.id]
    if len(method_ids) != len(set(method_ids)):
        errors.append("enhancement methods have duplicate ids")
    for method in ENHANCEMENT_METHODS:
        if not method.id:
            errors.append("enhancement method id is required")
        if method.min_stars < 0:
            errors.append(f"enhancement method {method.id} min stars must be non-negative")
        if method.max_stars <= method.min_stars:
            errors.append(f"enhancement method {method.id} max stars must be greater than min stars")
        for material_id in method.material_costs:
            if material_id not in MATERIAL_BY_ID:
                errors.append(f"enhancement method {method.id} material not found: {material_id}")
    for dungeon in DUNGEONS:
        for enemy in dungeon.enemies:
            errors.extend(_validate_reward(enemy.rewards, f"enemy {enemy.id} rewards"))
    for boss in BOSSES:
        pattern_ids = [pattern.id for pattern in boss.patterns if pattern.id]
        if len(pattern_ids) != len(set(pattern_ids)):
            errors.append(f"boss {boss.id} has duplicate pattern ids")
        for pattern in boss.patterns:
            errors.extend(_validate_effect_actions(pattern.effect_actions, f"boss {boss.id} pattern {pattern.id} effect actions"))
        warning_ids = [warning.id for warning in boss.warnings if warning.id]
        if len(warning_ids) != len(set(warning_ids)):
            errors.append(f"boss {boss.id} has duplicate warning ids")
        for warning in boss.warnings:
            if warning.pattern is not None:
                errors.extend(_validate_effect_actions(warning.pattern.effect_actions, f"boss {boss.id} warning {warning.id} effect actions"))
            for index, variant in enumerate(warning.failure_variants, start=1):
                for condition in variant.conditions:
                    if condition.stack_effect_id not in STACK_EFFECT_BY_ID:
                        errors.append(
                            f"boss {boss.id} warning {warning.id} failure variant {index} "
                            f"stack effect not found: {condition.stack_effect_id}"
                        )
                    if condition.min_stacks < 0:
                        errors.append(
                            f"boss {boss.id} warning {warning.id} failure variant {index} "
                            f"min stacks must be non-negative"
                        )
                    if condition.max_stacks >= 0 and condition.max_stacks < condition.min_stacks:
                        errors.append(
                            f"boss {boss.id} warning {warning.id} failure variant {index} "
                            f"max stacks must be at least min stacks"
                        )
                errors.extend(
                    _validate_effect_actions(
                        variant.pattern.effect_actions,
                        f"boss {boss.id} warning {warning.id} failure variant {index} effect actions",
                    )
                )
            for index, condition in enumerate(warning.activation_conditions, start=1):
                if condition.kind not in WARNING_ACTIVATION_CONDITIONS:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        f"kind not found: {condition.kind}"
                    )
                if condition.kind == "stack" and condition.stack_effect_id not in STACK_EFFECT_BY_ID:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        f"stack effect not found: {condition.stack_effect_id}"
                    )
                if condition.min_stacks < 0:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        f"min stacks must be non-negative"
                    )
                if condition.max_stacks >= 0 and condition.max_stacks < condition.min_stacks:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        f"max stacks must be at least min stacks"
                    )
                if condition.multiple < 1:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        "turn multiple must be at least 1"
                    )
                if condition.min_turn < 1:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        "min turn must be at least 1"
                    )
                if condition.max_turn >= 0 and condition.max_turn < condition.min_turn:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        "max turn must be at least min turn"
                    )
                if condition.min_ratio < 0 or condition.max_ratio > 1 or condition.max_ratio < condition.min_ratio:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} activation condition {index} "
                        "hp ratio range is invalid"
                    )
            if warning.pattern_id not in boss.pattern_by_id:
                errors.append(f"boss {boss.id} warning pattern not found: {warning.pattern_id}")
            if warning.success_warning_id and warning.success_warning_id not in boss.warning_by_id:
                errors.append(
                    f"boss {boss.id} warning {warning.id} success warning not found: "
                    f"{warning.success_warning_id}"
                )
            if warning.failure_warning_id and warning.failure_warning_id not in boss.warning_by_id:
                errors.append(
                    f"boss {boss.id} warning {warning.id} failure warning not found: "
                    f"{warning.failure_warning_id}"
                )
            if not warning.objectives:
                errors.append(f"boss {boss.id} warning has no objectives: {warning.id}")
            for objective in warning.objectives:
                if objective.objective not in WARNING_OBJECTIVES:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} objective not found: {objective.objective}"
                    )
                if objective.required < 1:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} objective required must be at least 1"
                    )
                if objective.min_damage < 0:
                    errors.append(
                        f"boss {boss.id} warning {warning.id} objective min damage must be non-negative"
                    )
        for warning in boss.hp_warnings:
            if warning.warning_id not in boss.warning_by_id:
                errors.append(f"boss {boss.id} hp warning not found: {warning.warning_id}")
        for index, effect in enumerate(boss.hp_effects, start=1):
            if effect.threshold < 0 or effect.threshold > 1:
                errors.append(f"boss {boss.id} hp effect {index} threshold out of range: {effect.threshold}")
            errors.extend(_validate_effect_actions(effect.pattern.effect_actions, f"boss {boss.id} hp effect {index} effect actions"))
        seen_hp_locks: set[float] = set()
        for index, threshold in enumerate(boss.hp_locks, start=1):
            if threshold <= 0 or threshold >= 1:
                errors.append(f"boss {boss.id} hp lock {index} threshold out of range: {threshold}")
            if threshold in seen_hp_locks:
                errors.append(f"boss {boss.id} duplicate hp lock threshold: {threshold}")
            seen_hp_locks.add(threshold)
        for warning in boss.ct_warnings:
            warning_ids = warning.warning_ids or ((warning.warning_id,) if warning.warning_id else ())
            for warning_id in warning_ids:
                if warning_id not in boss.warning_by_id:
                    errors.append(f"boss {boss.id} ct warning not found: {warning_id}")
        for stack_effect in boss.stack_effects:
            if stack_effect.stack_effect_id not in STACK_EFFECT_BY_ID:
                errors.append(f"boss {boss.id} stack effect not found: {stack_effect.stack_effect_id}")
                continue
            max_stacks = STACK_EFFECT_BY_ID[stack_effect.stack_effect_id].max_stacks
            if stack_effect.initial_stacks < 0 or stack_effect.initial_stacks > max_stacks:
                errors.append(
                    f"boss {boss.id} stack effect initial stacks out of range: "
                    f"{stack_effect.stack_effect_id} {stack_effect.initial_stacks}"
                )
        errors.extend(_validate_reward(boss.rewards, f"boss {boss.id} rewards"))
    pool_ids = [pool.id for pool in GACHA_POOLS]
    if len(pool_ids) != len(set(pool_ids)):
        errors.append("gacha has duplicate pool ids")
    if GACHA_POOLS and GACHA_DEFAULT_POOL_ID not in GACHA_POOL_BY_ID:
        errors.append(f"gacha default pool not found: {GACHA_DEFAULT_POOL_ID}")
    for pool in GACHA_POOLS:
        if not pool.entries:
            errors.append(f"gacha pool {pool.id} has no entries")
        for index, entry in enumerate(pool.entries, start=1):
            errors.extend(_validate_gacha_entry(entry, f"gacha pool {pool.id} entry {index}"))
    if errors:
        raise ValueError("Invalid RPG content:\n" + "\n".join(f"- {error}" for error in errors))


def _validate_effect_actions(actions: list[EffectAction], label: str) -> list[str]:
    errors: list[str] = []
    for action in actions:
        if action.action in STACK_EFFECT_ACTIONS and action.stack_effect_id not in STACK_EFFECT_BY_ID:
            errors.append(f"{label} stack effect not found: {action.stack_effect_id}")
        for index, condition in enumerate(action.conditions, start=1):
            if condition.stack_effect_id not in STACK_EFFECT_BY_ID:
                errors.append(
                    f"{label} {action.action} condition {index} stack effect not found: "
                    f"{condition.stack_effect_id}"
                )
            if condition.target not in {"self", "enemy", "allies", "opponents", "boss", "player"}:
                errors.append(
                    f"{label} {action.action} condition {index} target is invalid: "
                    f"{condition.target}"
                )
            if condition.min_stacks < 0:
                errors.append(f"{label} {action.action} condition {index} min stacks must be non-negative")
            if condition.max_stacks >= 0 and condition.max_stacks < condition.min_stacks:
                errors.append(f"{label} {action.action} condition {index} max stacks must be at least min stacks")
    return errors


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


def _validate_gacha_entry(entry: GachaEntry, label: str) -> list[str]:
    errors: list[str] = []
    if entry.type not in {"item", "item_rarity", "material", "material_rarity"}:
        errors.append(f"{label} type not found: {entry.type}")
    if entry.chance <= 0:
        errors.append(f"{label} chance must be greater than 0")
    if entry.type == "item":
        for item_id in entry.item_ids:
            if item_id not in ITEM_BY_ID:
                errors.append(f"{label} item not found: {item_id}")
    if entry.type == "item_rarity" and entry.rarity not in RARITIES:
        errors.append(f"{label} rarity not found: {entry.rarity}")
    if entry.type == "material":
        for material_id in entry.material_ids:
            if material_id not in MATERIAL_BY_ID:
                errors.append(f"{label} material not found: {material_id}")
    if entry.type == "material_rarity" and entry.rarity not in RARITIES:
        errors.append(f"{label} rarity not found: {entry.rarity}")
    return errors


_validate_content()

_LEVEL_CURVE = CONTENT.get("level_curve", {})
PLAYER_START = dict(CONTENT.get("player", {}).get("start", {}))
STAT_ALLOCATIONS = {
    str(stat_id): dict(rule)
    for stat_id, rule in CONTENT.get("stat_allocation", {}).items()
    if isinstance(rule, dict)
}
def next_level_exp(level: int) -> int:
    level = max(1, level)
    step = level - 1
    base = int(_LEVEL_CURVE.get("base", 280))
    linear = int(_LEVEL_CURVE.get("linear", 170))
    quadratic = int(_LEVEL_CURVE.get("quadratic", 50))
    cubic = int(_LEVEL_CURVE.get("cubic", 0))
    return base + linear * step + quadratic * step * step + cubic * step * step * step


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
    template = ITEM_BY_ID[template_id]
    stats: dict[str, float] = {}
    for key, value in template.stats.items():
        if key in template.fixed_stats:
            scaled = value
        else:
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


def enhancement_method(method_id: str | None = None) -> EnhancementMethod:
    if method_id and method_id in ENHANCEMENT_METHOD_BY_ID:
        return ENHANCEMENT_METHOD_BY_ID[method_id]
    if DEFAULT_ENHANCEMENT_METHOD_ID in ENHANCEMENT_METHOD_BY_ID:
        return ENHANCEMENT_METHOD_BY_ID[DEFAULT_ENHANCEMENT_METHOD_ID]
    return EnhancementMethod(
        id="gold",
        name="일반 강화",
        gold_cost_mode="formula",
        odds_mode="formula",
        max_stars=MAX_ENHANCEMENT_STARS,
    )


def enhancement_method_available(method: EnhancementMethod, stars: int) -> bool:
    stars = max(0, int(stars))
    return method.min_stars <= stars < min(method.max_stars, MAX_ENHANCEMENT_STARS)


def enhancement_method_gold_cost(method: EnhancementMethod, rarity: str, stars: int) -> int:
    if method.gold_cost_mode == "none":
        return 0
    if method.gold_cost_mode == "fixed":
        return max(0, int(method.gold_cost))
    return enhancement_cost(rarity, stars)


def enhancement_method_odds(method: EnhancementMethod, rarity: str, stars: int) -> tuple[float, float, float]:
    base_success, base_fail, base_destroy = enhancement_odds(rarity, stars)
    if method.odds_mode == "fixed":
        success = 0.0 if method.success is None else method.success
        destroy = 0.0 if method.destroy is None else method.destroy
        fail = method.fail if method.fail is not None else max(0.0, 1.0 - success - destroy)
    else:
        success = base_success if method.success is None else method.success
        destroy = base_destroy if method.destroy is None else method.destroy
        fail = method.fail if method.fail is not None else max(0.0, 1.0 - success - destroy)
        if method.success is None and method.destroy is None and method.fail is None:
            fail = base_fail
    total = success + fail + destroy
    if total > 1.0:
        success /= total
        fail /= total
        destroy /= total
    return success, fail, destroy


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
