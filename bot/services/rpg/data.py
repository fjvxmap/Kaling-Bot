from __future__ import annotations

from dataclasses import dataclass, field


DAILY_EXPLORES = 5
MAX_EQUIPPED_ITEMS = 4
MAX_ENHANCEMENT_STARS = 10

STAT_ORDER = [
    "base_atk",
    "max_hp",
    "hp_bonus",
    "atk",
    "defense",
    "garrison",
    "strength",
    "enmity",
    "damage_cut",
    "dmg_mitigation",
    "dmg_amplification",
]

STAT_LABELS = {
    "base_atk": "공격력",
    "max_hp": "최대 HP",
    "hp_bonus": "HP 보너스",
    "atk": "공격 증폭",
    "defense": "방어",
    "garrison": "수비 태세",
    "strength": "우세",
    "enmity": "역전",
    "damage_cut": "피해 감소",
    "dmg_mitigation": "고정 감소",
    "dmg_amplification": "최종 피해",
}

PERCENT_STATS = {
    "hp_bonus",
    "atk",
    "defense",
    "garrison",
    "strength",
    "enmity",
    "damage_cut",
    "dmg_amplification",
}
INTEGER_STATS = {"base_atk", "max_hp"}

RARITIES = ["normal", "rare", "epic", "unique", "legendary"]
RARITY_LABELS = {
    "normal": "노멀",
    "rare": "레어",
    "epic": "에픽",
    "unique": "유니크",
    "legendary": "레전더리",
}
RARITY_COLORS = {
    "normal": 0xA0A7B4,
    "rare": 0x4BA3FF,
    "epic": 0xB56BFF,
    "unique": 0xFFB84D,
    "legendary": 0xFF5C7A,
}
ENHANCE_BASE_COST = {
    "normal": 30,
    "rare": 60,
    "epic": 110,
    "unique": 200,
    "legendary": 380,
}
RESTORE_COST = {
    "normal": 25,
    "rare": 55,
    "epic": 95,
    "unique": 160,
    "legendary": 280,
}
RARITY_PRICE_MULTIPLIERS = {
    "normal": 1.0,
    "rare": 2.15,
    "epic": 4.4,
    "unique": 8.8,
    "legendary": 17.5,
}


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
    uses: int
    damage_multiplier: float = 0.0
    hits: int = 0
    player_mods: dict[str, float] = field(default_factory=dict)
    enemy_mods: dict[str, float] = field(default_factory=dict)
    duration: int = 0
    heal_power: float = 0.0
    damage_cut: float = 0.0


@dataclass(frozen=True)
class BossPattern:
    threshold: float
    name: str
    damage_multiplier: float = 0.0
    hits: int = 0
    player_mods: dict[str, float] = field(default_factory=dict)
    boss_mods: dict[str, float] = field(default_factory=dict)
    duration: int = 0


@dataclass(frozen=True)
class EncounterTemplate:
    id: str
    name: str
    level_req: int
    rank: int
    stats: dict[str, float]
    gold: int
    exp: int
    drop_chance: float
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


def _item(item_id: str, name: str, rarity: str, stats: dict[str, float]) -> ItemTemplate:
    return ItemTemplate(item_id, name, rarity, stats, _base_price(rarity, stats))


ITEM_CATALOG = [
    _item("normal_01", "Iron Knife", "normal", {"base_atk": 2, "atk": 0.006}),
    _item("normal_08", "Leather Guard", "normal", {"max_hp": 14, "garrison": 0.018}),
    _item("normal_20", "Simple Glaive", "normal", {"base_atk": 1, "max_hp": 6, "atk": 0.006, "defense": 0.006}),
    _item("rare_01", "Silver Knife", "rare", {"base_atk": 3, "atk": 0.022, "dmg_amplification": 0.01}),
    _item("rare_14", "Kite Shield", "rare", {"max_hp": 24, "defense": 0.026, "garrison": 0.05}),
    _item("rare_20", "Polished Glaive", "rare", {"base_atk": 2, "max_hp": 16, "atk": 0.016, "defense": 0.014, "strength": 0.012}),
    _item("epic_01", "Crimson Knife", "epic", {"base_atk": 5, "atk": 0.05, "enmity": 0.035}),
    _item("epic_08", "Ironwall Guard", "epic", {"max_hp": 42, "defense": 0.065, "garrison": 0.055, "dmg_mitigation": 1.4}),
    _item("epic_20", "Royal Glaive", "epic", {"base_atk": 4, "max_hp": 32, "hp_bonus": 0.026, "atk": 0.03, "defense": 0.028, "strength": 0.025, "enmity": 0.02}),
    _item("unique_01", "Void Knife", "unique", {"base_atk": 7, "atk": 0.07, "enmity": 0.075, "dmg_amplification": 0.045}),
    _item("unique_08", "Citadel Guard", "unique", {"max_hp": 76, "hp_bonus": 0.06, "defense": 0.095, "garrison": 0.12, "dmg_mitigation": 2.4}),
    _item("unique_20", "Dominion Glaive", "unique", {"base_atk": 6, "max_hp": 52, "hp_bonus": 0.045, "atk": 0.045, "defense": 0.045, "garrison": 0.04, "strength": 0.04, "enmity": 0.035, "dmg_mitigation": 1.2, "dmg_amplification": 0.035}),
    _item("legendary_01", "Excalibur", "legendary", {"base_atk": 18, "atk": 0.18, "strength": 0.22, "dmg_amplification": 0.08}),
    _item("legendary_08", "Aegis", "legendary", {"max_hp": 150, "hp_bonus": 0.18, "defense": 0.22, "garrison": 0.24, "dmg_mitigation": 6.0}),
    _item("legendary_20", "Paragon Glaive", "legendary", {"base_atk": 10, "max_hp": 100, "hp_bonus": 0.1, "atk": 0.1, "defense": 0.1, "garrison": 0.1, "strength": 0.1, "enmity": 0.1, "dmg_mitigation": 3.0, "dmg_amplification": 0.1}),
]
ITEM_BY_ID = {item.id: item for item in ITEM_CATALOG}
ITEMS_BY_RARITY = {
    rarity: [item for item in ITEM_CATALOG if item.rarity == rarity]
    for rarity in RARITIES
}

SKILLS = [
    SkillTemplate("power_strike", "Power Strike", 1, 2, 1.45, 1),
    SkillTemplate("slash_blast", "Slash Blast", 3, 1, 0.82, 3),
    SkillTemplate(
        "iron_body",
        "Iron Body",
        4,
        1,
        player_mods={"defense": 0.08, "dmg_mitigation": 1.5},
        duration=3,
        damage_cut=0.12,
    ),
    SkillTemplate("rage", "Rage", 6, 1, player_mods={"atk": 0.08, "strength": 0.05}, duration=3),
    SkillTemplate("heal", "Heal", 8, 1, player_mods={"defense": 0.03, "dmg_mitigation": 0.8}, duration=2, heal_power=1.2),
    SkillTemplate("raging_blow", "Raging Blow", 12, 1, 1.0, 4),
    SkillTemplate("enrage", "Enrage", 16, 1, player_mods={"atk": 0.18, "dmg_amplification": 0.10}, duration=4),
]

DUNGEONS = [
    EncounterTemplate(
        "moss_ruins",
        "이끼 낀 폐허",
        1,
        1,
        {"base_atk": 8, "max_hp": 80, "defense": 0.02, "dmg_mitigation": 0.5},
        95,
        70,
        0.45,
        "입문용 던전. 노멀/레어 장비를 모으기 좋습니다.",
    ),
    EncounterTemplate(
        "crystal_cave",
        "수정 동굴",
        3,
        2,
        {"base_atk": 14, "max_hp": 170, "atk": 0.03, "defense": 0.05, "dmg_mitigation": 1.2},
        170,
        135,
        0.52,
        "초반 성장 구간. 레어 이상 확률이 조금 오릅니다.",
    ),
    EncounterTemplate(
        "sunken_forge",
        "가라앉은 대장간",
        6,
        3,
        {"base_atk": 24, "max_hp": 360, "atk": 0.06, "defense": 0.08, "garrison": 0.03, "dmg_mitigation": 2.6},
        315,
        235,
        0.60,
        "강화 재료와 에픽 장비를 노리는 중반 던전입니다.",
    ),
    EncounterTemplate(
        "ashen_tower",
        "잿빛 탑",
        10,
        4,
        {"base_atk": 38, "max_hp": 700, "atk": 0.10, "defense": 0.12, "strength": 0.05, "dmg_mitigation": 4.8},
        540,
        390,
        0.68,
        "유니크 장비가 보이기 시작하는 고난도 던전입니다.",
    ),
    EncounterTemplate(
        "starfall_gate",
        "별추락 관문",
        15,
        5,
        {"base_atk": 58, "max_hp": 1180, "atk": 0.16, "defense": 0.16, "strength": 0.08, "dmg_amplification": 0.05, "dmg_mitigation": 7.5},
        880,
        620,
        0.78,
        "레전더리 드랍을 기대할 수 있는 최상위 탐색지입니다.",
    ),
]
DUNGEON_BY_ID = {dungeon.id: dungeon for dungeon in DUNGEONS}

BOSSES = [
    BossTemplate(
        "slime_emperor",
        "Slime Emperor",
        4,
        2,
        {"base_atk": 11, "max_hp": 230, "defense": 0.06, "garrison": 0.04, "dmg_mitigation": 2.0},
        1200,
        280,
        1,
        1.0,
        [
            BossPattern(0.70, "Sticky Crown", player_mods={"atk": -0.20}, duration=3),
            BossPattern(0.45, "Imperial Bulk", boss_mods={"damage_cut": 0.16, "dmg_mitigation": 2.0}, duration=2),
            BossPattern(0.20, "Crown Drop", 0.65, 3),
        ],
        "튼튼한 첫 보스. 방어형 장비의 가치를 알려줍니다.",
    ),
    BossTemplate(
        "crimson_wyvern",
        "Crimson Wyvern",
        7,
        3,
        {"base_atk": 25, "max_hp": 620, "atk": 0.10, "strength": 0.08, "dmg_amplification": 0.04},
        1900,
        430,
        1,
        1.0,
        [
            BossPattern(0.75, "Ignited Scales", boss_mods={"atk": 0.28, "dmg_amplification": 0.16}, duration=3),
            BossPattern(0.50, "Wing Buffet", 0.85, 4),
            BossPattern(0.22, "Crimson Breath", 1.10, 5),
        ],
        "공격이 강한 보스. 낮은 HP에서 폭발력이 큽니다.",
    ),
    BossTemplate(
        "clockwork_knight",
        "Clockwork Knight",
        10,
        4,
        {"base_atk": 32, "max_hp": 880, "defense": 0.15, "garrison": 0.10, "dmg_mitigation": 6.0},
        2800,
        620,
        2,
        1.0,
        [
            BossPattern(0.72, "Gear Lock", player_mods={"atk": -0.18, "strength": -0.14}, duration=3),
            BossPattern(0.48, "Iron Rewind", boss_mods={"defense": 0.24, "damage_cut": 0.24, "dmg_mitigation": 4.0}, duration=3),
            BossPattern(0.18, "Final Gear", 0.95, 5),
        ],
        "단단하고 오래 버팁니다. 강화된 무기가 체감됩니다.",
    ),
    BossTemplate(
        "mirror_witch",
        "Mirror Witch",
        13,
        5,
        {"base_atk": 39, "max_hp": 1120, "atk": 0.13, "defense": 0.13, "dmg_amplification": 0.09},
        3900,
        850,
        2,
        1.0,
        [
            BossPattern(0.78, "Mirror Curse", player_mods={"atk": -0.22, "dmg_amplification": -0.18}, duration=3),
            BossPattern(0.52, "Shattered Glass", 0.72, 6),
            BossPattern(0.22, "Mirror Collapse", 1.15, 5),
        ],
        "디버프가 많은 보스. 높은 기본 공격력이 안정적입니다.",
    ),
    BossTemplate(
        "black_star",
        "Black Star",
        18,
        6,
        {"base_atk": 54, "max_hp": 1750, "atk": 0.20, "defense": 0.19, "garrison": 0.13, "dmg_amplification": 0.14},
        6400,
        1250,
        3,
        1.0,
        [
            BossPattern(0.82, "Gravity Well", player_mods={"strength": -0.24, "enmity": -0.24}, duration=3),
            BossPattern(0.60, "Black Armor", boss_mods={"defense": 0.28, "damage_cut": 0.28}, duration=3),
            BossPattern(0.38, "Singularity", boss_mods={"atk": 0.34, "dmg_amplification": 0.24}, duration=3),
            BossPattern(0.16, "Last Light", 1.35, 4, player_mods={"damage_cut": -0.18}, duration=2),
        ],
        "주간 최종 보스. 공격과 방어를 모두 요구합니다.",
    ),
]
BOSS_BY_ID = {boss.id: boss for boss in BOSSES}


def next_level_exp(level: int) -> int:
    level = max(1, level)
    step = level - 1
    return 300 + 180 * step + 45 * step * step


def previous_level_exp(level: int) -> int:
    if level <= 1:
        return 0
    return next_level_exp(level - 1)


def star_multiplier(stars: int) -> float:
    stars = max(0, min(MAX_ENHANCEMENT_STARS, stars))
    return 1.0 + 0.24 * stars + 0.03 * stars * stars + 0.03 * min(stars, 3)


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


def enhancement_cost(rarity: str, stars: int) -> int:
    return ENHANCE_BASE_COST[rarity] * (stars + 1) * (stars + 1)


def restore_cost(rarity: str) -> int:
    return RESTORE_COST[rarity]


def enhancement_odds(rarity: str, stars: int) -> tuple[float, float, float]:
    tier = RARITIES.index(rarity)
    success = max(0.15, 0.86 - 0.055 * stars - 0.045 * tier)
    destroy = 0.0 if stars < 2 else min(0.38, 0.008 * (stars - 1) * (tier + 1))
    fail = max(0.0, 1.0 - success - destroy)
    return success, fail, destroy
