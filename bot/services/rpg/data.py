from __future__ import annotations

from dataclasses import dataclass, field


DAILY_EXPLORES = 7
EXPLORE_LIMIT_ENABLED = False
BOSS_WEEKLY_REWARD_LIMIT_ENABLED = False
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
    "garrison": "견수",
    "strength": "혼신",
    "enmity": "배수",
    "damage_cut": "피해 차단",
    "dmg_mitigation": "데미지 감소",
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

JOBS = [
    JobTemplate("novice", "초보자", 0, 1, "", {}, "기본 직업입니다. Lv.3부터 1차 전직을 선택할 수 있습니다."),
    JobTemplate("warrior_1", "검사", 1, 3, "novice", {"max_hp": 20, "atk": 0.015, "strength": 0.025}, "공격과 생존이 균형 잡힌 전사 계열입니다."),
    JobTemplate("magician_1", "마법사", 1, 3, "novice", {"atk": 0.035, "dmg_amplification": 0.02, "dmg_mitigation": 0.5}, "버프, 회복, 높은 최종 피해에 강점이 있습니다."),
    JobTemplate("thief_1", "도적", 1, 3, "novice", {"base_atk": 1, "atk": 0.025, "enmity": 0.035}, "빠른 타격과 낮은 체력 배수 피해에 강합니다."),
    JobTemplate("hero_2", "파이터", 2, 8, "warrior_1", {"base_atk": 3, "max_hp": 28, "atk": 0.035, "strength": 0.055}, "혼신 기반 공격형 전사입니다."),
    JobTemplate("paladin_2", "페이지", 2, 8, "warrior_1", {"max_hp": 42, "defense": 0.045, "garrison": 0.055, "dmg_mitigation": 1.0}, "견수와 방어를 활용하는 안정형 전사입니다."),
    JobTemplate("archmage_2", "위자드", 2, 8, "magician_1", {"atk": 0.055, "strength": 0.045, "dmg_amplification": 0.06}, "강한 마법 타격과 디버프를 사용합니다."),
    JobTemplate("bishop_2", "클레릭", 2, 8, "magician_1", {"hp_bonus": 0.045, "defense": 0.035, "dmg_mitigation": 1.4}, "회복과 방어 보조에 특화됩니다."),
    JobTemplate("night_lord_2", "어쌔신", 2, 8, "thief_1", {"base_atk": 3, "atk": 0.045, "enmity": 0.075}, "배수 피해와 연타에 집중합니다."),
    JobTemplate("shadower_2", "시프", 2, 8, "thief_1", {"base_atk": 2, "atk": 0.035, "garrison": 0.045, "enmity": 0.045}, "공격과 견수를 섞는 생존형 도적입니다."),
    JobTemplate("hero_3", "히어로", 3, 14, "hero_2", {"base_atk": 5, "max_hp": 45, "atk": 0.06, "strength": 0.10, "dmg_amplification": 0.035}, "짧고 강한 폭딜로 보스를 압박합니다."),
    JobTemplate("paladin_3", "팔라딘", 3, 14, "paladin_2", {"base_atk": 3, "max_hp": 68, "defense": 0.08, "garrison": 0.10, "dmg_mitigation": 2.4}, "버티면서 확실히 클리어하는 방어형 최종 전직입니다."),
    JobTemplate("archmage_3", "아크메이지", 3, 14, "archmage_2", {"atk": 0.085, "strength": 0.08, "dmg_amplification": 0.105}, "광역과 방어 약화로 전투 시간을 줄입니다."),
    JobTemplate("bishop_3", "비숍", 3, 14, "bishop_2", {"hp_bonus": 0.08, "defense": 0.07, "dmg_mitigation": 2.6, "dmg_amplification": 0.04}, "회복과 장기전 안정성이 가장 높습니다."),
    JobTemplate("night_lord_3", "나이트로드", 3, 14, "night_lord_2", {"base_atk": 5, "atk": 0.08, "enmity": 0.14, "dmg_amplification": 0.045}, "HP가 낮을수록 위력이 커지는 공격형 최종 전직입니다."),
    JobTemplate("shadower_3", "섀도어", 3, 14, "shadower_2", {"base_atk": 4, "atk": 0.06, "garrison": 0.08, "enmity": 0.09, "dmg_mitigation": 1.4}, "견수와 배수를 함께 쓰는 유연한 최종 전직입니다."),
]
JOB_BY_ID = {job.id: job for job in JOBS}

SKILLS = [
    SkillTemplate("quick_strike", "Quick Strike", 1, uses=0, cooldown=2, role="attack", damage_multiplier=1.12, hits=1),
    SkillTemplate("guard_focus", "Guard Focus", 3, uses=0, cooldown=5, role="defense", player_mods={"defense": 0.04, "garrison": 0.035}, duration=3, damage_cut=0.08),
    SkillTemplate("power_strike", "Power Strike", 3, uses=0, cooldown=3, role="attack", damage_multiplier=1.42, hits=1, job_ids=("warrior_1",)),
    SkillTemplate("iron_body", "Iron Body", 4, uses=0, cooldown=6, role="defense", player_mods={"defense": 0.08, "dmg_mitigation": 1.5}, duration=3, damage_cut=0.12, job_ids=("warrior_1",)),
    SkillTemplate("rage", "Rage", 8, uses=0, cooldown=6, role="buff", player_mods={"atk": 0.08, "strength": 0.05}, duration=3, job_ids=("hero_2",)),
    SkillTemplate("raging_blow", "Raging Blow", 14, uses=0, cooldown=4, role="attack", damage_multiplier=0.92, hits=4, job_ids=("hero_3",)),
    SkillTemplate("guardian_oath", "Guardian Oath", 8, uses=0, cooldown=6, role="defense", player_mods={"defense": 0.08, "garrison": 0.08, "dmg_mitigation": 1.8}, duration=3, damage_cut=0.14, job_ids=("paladin_2",)),
    SkillTemplate("blast", "Blast", 14, uses=0, cooldown=4, role="attack", damage_multiplier=1.55, hits=2, enemy_mods={"defense": -0.06}, duration=2, job_ids=("paladin_3",)),
    SkillTemplate("energy_bolt", "Energy Bolt", 3, uses=0, cooldown=3, role="attack", damage_multiplier=1.35, hits=1, job_ids=("magician_1",)),
    SkillTemplate("magic_barrier", "Magic Barrier", 4, uses=0, cooldown=6, role="defense", player_mods={"defense": 0.06, "dmg_mitigation": 1.2}, duration=3, damage_cut=0.10, job_ids=("magician_1",)),
    SkillTemplate("arcane_mark", "Arcane Mark", 8, uses=0, cooldown=5, role="debuff", enemy_mods={"defense": -0.08, "dmg_mitigation": -1.5}, duration=3, job_ids=("archmage_2",)),
    SkillTemplate("meteor", "Meteor", 14, uses=0, cooldown=5, role="attack", damage_multiplier=0.78, hits=6, job_ids=("archmage_3",)),
    SkillTemplate("heal", "Heal", 8, uses=0, cooldown=5, role="heal", player_mods={"defense": 0.03, "dmg_mitigation": 0.8}, duration=2, heal_power=1.45, job_ids=("bishop_2",)),
    SkillTemplate("holy_symbol", "Holy Symbol", 14, uses=0, cooldown=7, role="buff", player_mods={"atk": 0.10, "defense": 0.07}, duration=4, heal_power=0.55, job_ids=("bishop_3",)),
    SkillTemplate("lucky_seven", "Lucky Seven", 3, uses=0, cooldown=3, role="attack", damage_multiplier=0.82, hits=2, job_ids=("thief_1",)),
    SkillTemplate("smoke_screen", "Smoke Screen", 4, uses=0, cooldown=6, role="debuff", enemy_mods={"atk": -0.06, "dmg_amplification": -0.04}, duration=3, damage_cut=0.08, job_ids=("thief_1",)),
    SkillTemplate("drain", "Drain", 8, uses=0, cooldown=4, role="heal", damage_multiplier=0.92, hits=2, heal_power=0.65, job_ids=("night_lord_2",)),
    SkillTemplate("quad_throw", "Quad Throw", 14, uses=0, cooldown=4, role="attack", damage_multiplier=0.82, hits=4, player_mods={"enmity": 0.07}, duration=2, job_ids=("night_lord_3",)),
    SkillTemplate("savage_blow", "Savage Blow", 8, uses=0, cooldown=4, role="attack", damage_multiplier=0.52, hits=6, job_ids=("shadower_2",)),
    SkillTemplate("assassinate", "Assassinate", 14, uses=0, cooldown=5, role="attack", damage_multiplier=1.25, hits=3, player_mods={"enmity": 0.08}, duration=2, job_ids=("shadower_3",)),
]

DUNGEONS = [
    DungeonTemplate(
        "moss_ruins",
        "이끼 낀 폐허",
        1,
        1,
        [
            EnemyTemplate("moss_slime", "Moss Slime", 62, 1, {"base_atk": 8, "max_hp": 80, "defense": 0.02, "dmg_mitigation": 0.5}, 95, 70, 0.45, "표준 몬스터입니다."),
            EnemyTemplate("ruin_bat", "Ruin Bat", 30, 1, {"base_atk": 10, "max_hp": 72, "atk": 0.02, "defense": 0.015}, 110, 82, 0.48, "조금 더 아프지만 체력이 낮습니다."),
            EnemyTemplate("golden_sprout", "Golden Sprout", 8, 2, {"base_atk": 12, "max_hp": 115, "defense": 0.035, "dmg_mitigation": 1.0}, 190, 135, 0.72, "낮은 확률로 등장하는 보너스 몬스터입니다.", True),
        ],
        "입문용 던전. 하루 성장의 기본 루트입니다.",
    ),
    DungeonTemplate(
        "crystal_cave",
        "수정 동굴",
        3,
        2,
        [
            EnemyTemplate("crystal_lizard", "Crystal Lizard", 56, 2, {"base_atk": 14, "max_hp": 170, "atk": 0.03, "defense": 0.05, "dmg_mitigation": 1.2}, 170, 135, 0.52, "균형형 몬스터입니다."),
            EnemyTemplate("shard_golem", "Shard Golem", 34, 2, {"base_atk": 13, "max_hp": 215, "defense": 0.075, "garrison": 0.03, "dmg_mitigation": 1.8}, 195, 150, 0.55, "단단해서 공격력 투자가 필요합니다."),
            EnemyTemplate("prism_mimic", "Prism Mimic", 10, 3, {"base_atk": 19, "max_hp": 245, "atk": 0.06, "defense": 0.07, "dmg_mitigation": 2.0}, 340, 235, 0.82, "보상이 좋은 희귀 몬스터입니다.", True),
        ],
        "초반 전직 이후 장비와 경험치를 같이 챙기는 구간입니다.",
    ),
    DungeonTemplate(
        "sunken_forge",
        "가라앉은 대장간",
        6,
        3,
        [
            EnemyTemplate("forge_imp", "Forge Imp", 50, 3, {"base_atk": 24, "max_hp": 360, "atk": 0.06, "defense": 0.08, "garrison": 0.03, "dmg_mitigation": 2.6}, 315, 235, 0.60, "중반 표준 몬스터입니다."),
            EnemyTemplate("iron_sentinel", "Iron Sentinel", 38, 3, {"base_atk": 22, "max_hp": 460, "defense": 0.12, "garrison": 0.07, "dmg_mitigation": 4.0}, 360, 260, 0.64, "강화된 무기의 체감이 큽니다."),
            EnemyTemplate("ember_treasure", "Ember Treasure", 12, 4, {"base_atk": 31, "max_hp": 520, "atk": 0.08, "defense": 0.12, "dmg_amplification": 0.04, "dmg_mitigation": 4.2}, 620, 410, 0.90, "강하지만 에픽 이상 기대값이 높은 몬스터입니다.", True),
        ],
        "강화 비용과 에픽 장비를 마련하는 중반 던전입니다.",
    ),
    DungeonTemplate(
        "ashen_tower",
        "잿빛 탑",
        10,
        4,
        [
            EnemyTemplate("ash_knight", "Ash Knight", 48, 4, {"base_atk": 38, "max_hp": 700, "atk": 0.10, "defense": 0.12, "strength": 0.05, "dmg_mitigation": 4.8}, 540, 390, 0.68, "상위 장비가 필요한 몬스터입니다."),
            EnemyTemplate("tower_specter", "Tower Specter", 40, 4, {"base_atk": 43, "max_hp": 620, "atk": 0.13, "defense": 0.10, "enmity": 0.05, "dmg_amplification": 0.06, "dmg_mitigation": 4.2}, 590, 430, 0.70, "공격이 높아 방어 스킬 AI를 시험합니다."),
            EnemyTemplate("onyx_cache", "Onyx Cache", 12, 5, {"base_atk": 52, "max_hp": 880, "atk": 0.15, "defense": 0.14, "strength": 0.08, "dmg_mitigation": 6.4}, 980, 690, 0.94, "유니크 장비 기대값이 높은 희귀 몬스터입니다.", True),
        ],
        "2차 후반과 3차 초입을 잇는 고난도 던전입니다.",
    ),
    DungeonTemplate(
        "starfall_gate",
        "별추락 관문",
        15,
        5,
        [
            EnemyTemplate("starbound_guard", "Starbound Guard", 46, 5, {"base_atk": 58, "max_hp": 1180, "atk": 0.16, "defense": 0.16, "strength": 0.08, "dmg_amplification": 0.05, "dmg_mitigation": 7.5}, 880, 620, 0.78, "최상위 일반 몬스터입니다."),
            EnemyTemplate("void_lancer", "Void Lancer", 42, 5, {"base_atk": 66, "max_hp": 1040, "atk": 0.20, "defense": 0.14, "enmity": 0.09, "dmg_amplification": 0.08, "dmg_mitigation": 6.8}, 940, 675, 0.80, "빠르게 쓰러뜨리지 못하면 위험합니다."),
            EnemyTemplate("fallen_star", "Fallen Star", 12, 6, {"base_atk": 78, "max_hp": 1500, "atk": 0.22, "defense": 0.20, "strength": 0.10, "dmg_amplification": 0.10, "dmg_mitigation": 9.0}, 1600, 1050, 1.0, "레전더리 기대값이 있는 희귀 몬스터입니다.", True),
        ],
        "최종 보스 준비용 탐색지입니다.",
    ),
]
DUNGEON_BY_ID = {dungeon.id: dungeon for dungeon in DUNGEONS}

BOSSES = [
    BossTemplate(
        "slime_emperor",
        "Slime Emperor",
        5,
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
        "첫 보스. 1차 전직과 약간의 스탯 투자 후 안정적으로 잡히는 기준입니다.",
    ),
    BossTemplate(
        "crimson_wyvern",
        "Crimson Wyvern",
        8,
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
        "2차 전직 직후 도전하는 공격형 보스입니다.",
    ),
    BossTemplate(
        "clockwork_knight",
        "Clockwork Knight",
        11,
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
        "강화와 디버프 스킬 활용이 필요한 방어형 보스입니다.",
    ),
    BossTemplate(
        "mirror_witch",
        "Mirror Witch",
        14,
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
        "3차 전직 진입 체크포인트입니다.",
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
        "현재 최종 보스입니다. 3차 전직, 장비 강화, 스탯 투자가 모두 필요합니다.",
    ),
]
BOSS_BY_ID = {boss.id: boss for boss in BOSSES}


def next_level_exp(level: int) -> int:
    level = max(1, level)
    step = level - 1
    return 280 + 170 * step + 50 * step * step


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


def enhancement_odds(rarity: str, stars: int) -> tuple[float, float, float]:
    tier = RARITIES.index(rarity)
    success = max(0.15, 0.86 - 0.055 * stars - 0.045 * tier)
    destroy = 0.0 if stars < 2 else min(0.38, 0.008 * (stars - 1) * (tier + 1))
    fail = max(0.0, 1.0 - success - destroy)
    return success, fail, destroy
