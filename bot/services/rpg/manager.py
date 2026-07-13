from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from random import Random
from zoneinfo import ZoneInfo

from .data import (
    BOSS_BY_ID,
    BOSS_WEEKLY_REWARD_LIMIT_ENABLED,
    BOSSES,
    BonusDamageEffect,
    CRAFTING_RECIPE_BY_ID,
    CRAFTING_RECIPES,
    CombatSpecialEffects,
    DAILY_EXPLORES,
    DUNGEON_BY_ID,
    DUNGEONS,
    EffectAction,
    EXPLORE_LIMIT_ENABLED,
    GACHA_DEFAULT_POOL_ID,
    GACHA_POOL_BY_ID,
    GACHA_POOLS,
    INFINITE_EFFECT_TURNS,
    INTEGER_STATS,
    ITEM_BY_ID,
    ITEMS_BY_RARITY,
    JOB_BY_ID,
    JOBS,
    LEVEL_UP_BASE_ATK,
    LEVEL_UP_DEFENSE,
    LEVEL_UP_MAX_HP,
    MATERIAL_BY_ID,
    MATERIALS,
    MATERIALS_BY_RARITY,
    MAX_ENHANCEMENT_STARS,
    MAX_EQUIPPED_ITEMS,
    MAX_EQUIPPED_SKILLS,
    PERCENT_STATS,
    PLAYER_START,
    PostAttackAbilityDamageEffect,
    RARITIES,
    RARITY_LABELS,
    REWARD_LOSS_MULTIPLIER,
    REWARD_WIN_MULTIPLIER_MAX,
    REWARD_WIN_MULTIPLIER_MIN,
    SKILL_BY_ID,
    SKILLS,
    STAT_LABELS,
    STAT_ORDER,
    STACK_EFFECT_ACTIONS,
    STACK_EFFECT_BY_ID,
    BossPattern,
    BossTemplate,
    CraftingRecipe,
    DungeonTemplate,
    EnemyTemplate,
    GachaEntry,
    GachaPool,
    HealCap,
    JobTemplate,
    MaterialTemplate,
    RewardItemDrop,
    RewardTemplate,
    SkillTemplate,
    StatEffect,
    enhancement_cost,
    enhancement_odds,
    next_level_exp,
    previous_level_exp,
    restore_cost,
    scaled_item_stats,
    sell_price,
    stat_delta,
)
from .models import CombatStats, ItemInstance, PlayerProfile
from .store import RPGStore


STACKED_DEBUFF_FLOORS = {
    "atk": -0.5,
    "defense": -0.5,
}

RESTORE_STAR_LOSS = 3
DEFENSE_CAP = 4.0
WARNING_STACK_EVENTS = {"warning_success", "warning_failure"}
RPG_TIMEZONE = ZoneInfo("Asia/Seoul")
WEEKLY_BOSS_RESET_WEEKDAY = 3  # Thursday. datetime.date.weekday(): Monday=0.


def weekly_boss_key_for_date(day: date) -> str:
    days_since_reset = (day.weekday() - WEEKLY_BOSS_RESET_WEEKDAY) % 7
    reset_date = day - timedelta(days=days_since_reset)
    return reset_date.isoformat()


@dataclass
class ActiveEffect:
    turns: int
    mods: dict[str, float]
    source_id: str
    special: CombatSpecialEffects = field(default_factory=CombatSpecialEffects)
    undispellable: bool = False
    heal_cap: HealCap = field(default_factory=HealCap)


@dataclass
class ActiveStackEffect:
    template_id: str
    stacks: int
    persistent: bool = False
    condition_progress: dict[str, int] = field(default_factory=dict)


@dataclass
class AttackOutcome:
    damage: int = 0
    hits: int = 0
    hit_damages: list[int] = field(default_factory=list)
    ability_damage: int = 0
    ability_hits: int = 0
    actions: int = 1
    flurry_count: int = 1
    bonus_hits: int = 0
    double_attacks: int = 0
    triple_attacks: int = 0
    critical_hits: int = 0
    heal: int = 0
    life_steal_segments: list[int] = field(default_factory=list)
    detail_lines: list[str] = field(default_factory=list)


@dataclass
class SkillUseResult:
    damage: int = 0
    hit_damages: list[int] = field(default_factory=list)
    heal: int = 0
    raw_heal: int = 0
    dispels: int = 0
    clear_alls: int = 0
    detail_lines: list[str] = field(default_factory=list)


@dataclass
class BattleReport:
    won: bool
    turns: int
    player_hp: int
    player_max_hp: int
    enemy_hp: int
    enemy_max_hp: int
    log: list[str]
    skills_used: list[str] = field(default_factory=list)


@dataclass
class RewardReport:
    gold: int = 0
    exp: int = 0
    levels_gained: int = 0
    multiplier: float = 1.0
    dropped_item: ItemInstance | None = None
    dropped_items: list[ItemInstance] = field(default_factory=list)
    auto_sold_item: ItemInstance | None = None
    auto_sold_items: list[ItemInstance] = field(default_factory=list)
    auto_sold_gold: int = 0
    materials: dict[str, int] = field(default_factory=dict)
    weekly_reward_claimed: bool = False
    weekly_reward_locked: bool = False
    consolation: bool = False


@dataclass
class ExploreResult:
    ok: bool
    message: str
    profile: PlayerProfile
    dungeon: DungeonTemplate | None = None
    enemy: EnemyTemplate | None = None
    battle: BattleReport | None = None
    reward: RewardReport | None = None
    daily_remaining: int = 0


@dataclass
class ExploreBatchResult:
    ok: bool
    message: str
    profile: PlayerProfile
    dungeon: DungeonTemplate | None = None
    results: list[ExploreResult] = field(default_factory=list)
    requested_count: int = 0
    daily_remaining: int = 0


@dataclass
class BossResult:
    ok: bool
    message: str
    profile: PlayerProfile
    boss: BossTemplate | None = None
    battle: BattleReport | None = None
    reward: RewardReport | None = None
    weekly_key: str = ""


@dataclass
class EnhancementPreview:
    ok: bool
    message: str
    profile: PlayerProfile
    item: ItemInstance | None = None
    cost: int = 0
    odds: tuple[float, float, float] = (0.0, 0.0, 0.0)
    before_stats: dict[str, float] = field(default_factory=dict)
    after_stats: dict[str, float] = field(default_factory=dict)
    delta_stats: dict[str, float] = field(default_factory=dict)
    before_stars: int = 0
    after_stars: int = 0
    spare_item: ItemInstance | None = None


@dataclass
class EnhancementResult:
    ok: bool
    message: str
    profile: PlayerProfile
    item: ItemInstance | None = None
    cost: int = 0
    before_stars: int = 0
    after_stars: int = 0
    outcome: str = ""
    odds: tuple[float, float, float] = (0.0, 0.0, 0.0)
    spare_item: ItemInstance | None = None


@dataclass
class EquipmentResult:
    ok: bool
    message: str
    profile: PlayerProfile
    item: ItemInstance | None = None


@dataclass
class SellResult:
    ok: bool
    message: str
    profile: PlayerProfile
    gold: int = 0
    sold_count: int = 0
    sold_items: list[str] = field(default_factory=list)


@dataclass
class AbilityResult:
    ok: bool
    message: str
    profile: PlayerProfile
    skills: list[SkillTemplate] = field(default_factory=list)


@dataclass
class JobResult:
    ok: bool
    message: str
    profile: PlayerProfile
    job: JobTemplate | None = None


@dataclass
class CraftResult:
    ok: bool
    message: str
    profile: PlayerProfile
    recipe: CraftingRecipe | None = None
    item: ItemInstance | None = None
    missing_materials: dict[str, int] = field(default_factory=dict)
    missing_gold: int = 0


@dataclass
class GachaResult:
    ok: bool
    message: str
    profile: PlayerProfile
    pool: GachaPool | None = None
    spent_material_id: str = ""
    spent_material_amount: int = 0
    items: list[ItemInstance] = field(default_factory=list)
    materials: dict[str, int] = field(default_factory=dict)
    auto_sold_items: list[ItemInstance] = field(default_factory=list)
    auto_sold_gold: int = 0


@dataclass
class GachaGrant:
    items: list[ItemInstance] = field(default_factory=list)
    materials: dict[str, int] = field(default_factory=dict)


class RPGService:
    def __init__(self, store: RPGStore | None = None, rng: Random | None = None) -> None:
        self.store = store or RPGStore()
        self.rng = rng or Random()
        self._profiles = self.store.load_profiles()
        for profile in self._profiles.values():
            self._cleanup_profile(profile)

    def start_profile(self, user_id: int, display_name: str) -> tuple[PlayerProfile, bool]:
        if user_id in self._profiles:
            profile = self._profiles[user_id]
            profile.display_name = display_name or profile.display_name
            self._reset_daily_if_needed(profile)
            self._cleanup_profile(profile)
            self._save()
            return profile, False
        profile = PlayerProfile.create(user_id, display_name)
        self._profiles[user_id] = profile
        self._save()
        return profile, True

    def get_profile(self, user_id: int, display_name: str) -> PlayerProfile:
        profile, _created = self.start_profile(user_id, display_name)
        return profile

    def profile_stats(self, profile: PlayerProfile) -> CombatStats:
        return self._player_stats(profile)

    def explore_limit_enabled(self) -> bool:
        return EXPLORE_LIMIT_ENABLED

    def boss_reward_limit_enabled(self) -> bool:
        return BOSS_WEEKLY_REWARD_LIMIT_ENABLED

    def daily_remaining(self, profile: PlayerProfile) -> int:
        if not EXPLORE_LIMIT_ENABLED:
            return -1
        self._reset_daily_if_needed(profile)
        return max(0, DAILY_EXPLORES - profile.daily_explores_used)

    def current_week_key(self) -> str:
        return self._week_key()

    def dungeons(self) -> list[DungeonTemplate]:
        return list(DUNGEONS)

    def bosses(self) -> list[BossTemplate]:
        return list(BOSSES)

    def jobs(self) -> list[JobTemplate]:
        return list(JOBS)

    def materials(self) -> list[MaterialTemplate]:
        return list(MATERIALS)

    def crafting_recipes(self) -> list[CraftingRecipe]:
        return list(CRAFTING_RECIPES)

    def gacha_pools(self) -> list[GachaPool]:
        return list(GACHA_POOLS)

    def current_job(self, profile: PlayerProfile) -> JobTemplate:
        return JOB_BY_ID.get(profile.job_id, JOB_BY_ID["novice"])

    def job_chain(self, profile: PlayerProfile) -> list[JobTemplate]:
        chain: list[JobTemplate] = []
        job = self.current_job(profile)
        seen: set[str] = set()
        while job.id and job.id not in seen:
            chain.append(job)
            seen.add(job.id)
            if not job.parent_id:
                break
            job = JOB_BY_ID.get(job.parent_id, JOB_BY_ID["novice"])
        return list(reversed(chain))

    def available_jobs(self, profile: PlayerProfile) -> list[JobTemplate]:
        current_id = self.current_job(profile).id
        return [
            job for job in JOBS
            if job.parent_id == current_id and profile.level >= job.level_req
        ]

    def free_advance_jobs(self, profile: PlayerProfile) -> list[JobTemplate]:
        current = self.current_job(profile)
        if current.id == "novice":
            return []
        return [
            job for job in JOBS
            if job.id != current.id
            and job.id != "novice"
            and job.tier == current.tier
            and profile.level >= job.level_req
        ]

    def next_jobs(self, profile: PlayerProfile) -> list[JobTemplate]:
        current_id = self.current_job(profile).id
        return [job for job in JOBS if job.parent_id == current_id]

    def advance_job(self, user_id: int, display_name: str, job_id: str) -> JobResult:
        profile = self.get_profile(user_id, display_name)
        job = JOB_BY_ID.get(job_id)
        if job is None or job.id == "novice":
            return JobResult(False, "알 수 없는 전직입니다.", profile)
        if job.parent_id != self.current_job(profile).id:
            return JobResult(False, "현재 직업에서 선택할 수 없는 전직입니다.", profile, job)
        if profile.level < job.level_req:
            return JobResult(False, f"{job.name}은 Lv.{job.level_req}부터 전직할 수 있습니다.", profile, job)
        profile.job_id = job.id
        self._cleanup_equipped_skills(profile)
        self._save()
        return JobResult(True, f"{job.name}{self._direction_particle(job.name)} 전직했습니다.", profile, job)

    def free_advance_job(self, user_id: int, display_name: str, job_id: str) -> JobResult:
        profile = self.get_profile(user_id, display_name)
        current = self.current_job(profile)
        job = JOB_BY_ID.get(job_id)
        if job is None or job.id == "novice":
            return JobResult(False, "알 수 없는 전직입니다.", profile)
        if job.id == current.id:
            return JobResult(False, "이미 현재 직업입니다.", profile, job)
        if current.id == "novice" or job.tier != current.tier:
            return JobResult(False, "자유전직은 같은 티어의 직업으로만 가능합니다.", profile, job)
        if profile.level < job.level_req:
            return JobResult(False, f"{job.name}은 Lv.{job.level_req}부터 전직할 수 있습니다.", profile, job)
        profile.job_id = job.id
        self._cleanup_equipped_skills(profile)
        self._save()
        return JobResult(True, f"{job.name}{self._direction_particle(job.name)} 자유전직했습니다.", profile, job)

    def _direction_particle(self, text: str) -> str:
        if not text:
            return "으로"
        code = ord(text[-1]) - 0xAC00
        if 0 <= code <= 11171:
            return "으로" if code % 28 else "로"
        return "으로"

    def unlocked_skills(self, profile: PlayerProfile) -> list[SkillTemplate]:
        chain_ids = {job.id for job in self.job_chain(profile)}
        skills: list[SkillTemplate] = []
        for skill in SKILLS:
            if profile.level < skill.unlock_level:
                continue
            if skill.job_ids and not chain_ids.intersection(skill.job_ids):
                continue
            skills.append(skill)
        return skills

    def equipped_skills(self, profile: PlayerProfile) -> list[SkillTemplate]:
        available = {skill.id: skill for skill in self.unlocked_skills(profile)}
        skills = [
            available[skill_id]
            for skill_id in profile.equipped_skill_ids
            if skill_id in available
        ][:MAX_EQUIPPED_SKILLS]
        return skills

    def set_equipped_skills(self, user_id: int, display_name: str, skill_ids: list[str]) -> AbilityResult:
        profile = self.get_profile(user_id, display_name)
        available = {skill.id: skill for skill in self.unlocked_skills(profile)}
        selected = []
        for skill_id in skill_ids:
            if skill_id in available and skill_id not in selected:
                selected.append(skill_id)
            if len(selected) >= MAX_EQUIPPED_SKILLS:
                break
        profile.equipped_skill_ids = selected
        self._save()
        return AbilityResult(
            True,
            "어빌리티 장착을 저장했습니다.",
            profile,
            [available[skill_id] for skill_id in selected],
        )

    def craft_item(self, user_id: int, display_name: str, recipe_id: str) -> CraftResult:
        profile = self.get_profile(user_id, display_name)
        recipe = CRAFTING_RECIPE_BY_ID.get(recipe_id)
        if recipe is None:
            return CraftResult(False, "알 수 없는 제작법입니다.", profile)
        if recipe.result_item_id not in ITEM_BY_ID:
            return CraftResult(False, "제작 결과 장비 설정이 올바르지 않습니다.", profile, recipe)
        if profile.level < recipe.level_req:
            return CraftResult(False, f"Lv.{recipe.level_req}부터 제작할 수 있습니다.", profile, recipe)
        missing_materials = self.missing_crafting_materials(profile, recipe)
        missing_gold = max(0, recipe.gold - profile.gold)
        if missing_materials or missing_gold > 0:
            message = "재료가 부족합니다." if missing_materials else "골드가 부족합니다."
            return CraftResult(False, message, profile, recipe, missing_materials=missing_materials, missing_gold=missing_gold)

        profile.gold -= recipe.gold
        for material_id, amount in recipe.materials.items():
            profile.materials[material_id] = profile.materials.get(material_id, 0) - amount
            if profile.materials[material_id] <= 0:
                del profile.materials[material_id]
        item = self._grant_item(profile, recipe.result_item_id, recipe.result_stars)
        self._save()
        return CraftResult(True, "제작이 완료되었습니다.", profile, recipe, item)

    def roll_gacha(
        self,
        user_id: int,
        display_name: str,
        pool_id: str | None = None,
        draws: int | None = None,
    ) -> GachaResult:
        profile = self.get_profile(user_id, display_name)
        pool = GACHA_POOL_BY_ID.get(pool_id or GACHA_DEFAULT_POOL_ID)
        if pool is None:
            return GachaResult(False, "사용할 수 있는 가챠 풀이 없습니다.", profile)
        draw_count = max(1, int(draws or pool.draws))
        cost = self.gacha_cost(pool, draw_count)
        if pool.cost_material_id not in MATERIAL_BY_ID:
            return GachaResult(
                False,
                f"가챠 재료 `{pool.cost_material_id}`가 아직 재료 목록에 없습니다.",
                profile,
                pool,
                pool.cost_material_id,
                cost,
            )
        owned = profile.materials.get(pool.cost_material_id, 0)
        if owned < cost:
            material_name = self.material_name(pool.cost_material_id)
            return GachaResult(
                False,
                f"{material_name}이 부족합니다. {owned}/{cost}",
                profile,
                pool,
                pool.cost_material_id,
                cost,
            )

        entries = [
            entry for entry in pool.entries
            if entry.chance > 0 and self._gacha_candidates(entry)
        ]
        if not entries:
            return GachaResult(False, "가챠 보상 풀이 비어 있습니다.", profile, pool)

        profile.materials[pool.cost_material_id] = owned - cost
        if profile.materials[pool.cost_material_id] <= 0:
            del profile.materials[pool.cost_material_id]

        result = GachaResult(
            True,
            f"{pool.name} {draw_count}회 결과입니다.",
            profile,
            pool,
            pool.cost_material_id,
            cost,
        )
        for _ in range(draw_count):
            entry = self._choose_gacha_entry(entries)
            grant = self._grant_gacha_entry(profile, entry)
            if grant is None:
                continue
            result.items.extend(grant.items)
            for material_id, amount in grant.materials.items():
                result.materials[material_id] = result.materials.get(material_id, 0) + amount
        result.items, result.auto_sold_items, result.auto_sold_gold = self._auto_sell_items(profile, result.items)
        if result.auto_sold_gold > 0:
            profile.gold += result.auto_sold_gold
        self._save()
        return result

    def gacha_cost(self, pool: GachaPool, draws: int) -> int:
        draw_count = max(1, int(draws))
        base_draws = max(1, int(pool.draws))
        return max(1, (int(pool.cost_material_amount) * draw_count + base_draws - 1) // base_draws)

    def can_craft(self, profile: PlayerProfile, recipe: CraftingRecipe) -> bool:
        return (
            profile.level >= recipe.level_req
            and profile.gold >= recipe.gold
            and not self.missing_crafting_materials(profile, recipe)
            and recipe.result_item_id in ITEM_BY_ID
        )

    def missing_crafting_materials(self, profile: PlayerProfile, recipe: CraftingRecipe) -> dict[str, int]:
        missing: dict[str, int] = {}
        for material_id, required in recipe.materials.items():
            owned = profile.materials.get(material_id, 0)
            if owned < required:
                missing[material_id] = required - owned
        return missing

    def explore(self, user_id: int, display_name: str, dungeon_id: str) -> ExploreResult:
        profile = self.get_profile(user_id, display_name)
        result = self._explore_once(profile, dungeon_id)
        if result.ok:
            self._save()
        return result

    def explore_many(self, user_id: int, display_name: str, dungeon_id: str, count: int) -> ExploreBatchResult:
        profile = self.get_profile(user_id, display_name)
        dungeon = DUNGEON_BY_ID.get(dungeon_id)
        requested_count = max(1, min(50, int(count)))
        if dungeon is None:
            return ExploreBatchResult(False, "알 수 없는 던전입니다.", profile, daily_remaining=self.daily_remaining(profile))
        if EXPLORE_LIMIT_ENABLED:
            self._reset_daily_if_needed(profile)
            remaining = self.daily_remaining(profile)
            if remaining <= 0:
                return ExploreBatchResult(
                    False,
                    f"오늘 탐색 횟수를 모두 사용했습니다. 하루 {DAILY_EXPLORES}회까지 가능합니다.",
                    profile,
                    dungeon,
                    daily_remaining=0,
                )
            count = min(requested_count, remaining)
        else:
            count = requested_count
        if profile.level < dungeon.level_req:
            return ExploreBatchResult(
                False,
                f"{dungeon.name}은 Lv.{dungeon.level_req}부터 입장할 수 있습니다.",
                profile,
                dungeon,
                requested_count=requested_count,
                daily_remaining=self.daily_remaining(profile),
            )

        results: list[ExploreResult] = []
        for _ in range(count):
            result = self._explore_once(profile, dungeon_id)
            if not result.ok:
                break
            results.append(result)
        if results:
            self._save()
        if not results:
            return ExploreBatchResult(
                False,
                "탐색을 진행하지 못했습니다.",
                profile,
                dungeon,
                requested_count=requested_count,
                daily_remaining=self.daily_remaining(profile),
            )
        message = f"{len(results)}회 탐색 완료"
        if len(results) < requested_count:
            message += " (남은 탐색 횟수만 진행)"
        return ExploreBatchResult(
            True,
            message,
            profile,
            dungeon,
            results,
            requested_count,
            daily_remaining=self.daily_remaining(profile),
        )

    def _explore_once(self, profile: PlayerProfile, dungeon_id: str) -> ExploreResult:
        dungeon = DUNGEON_BY_ID.get(dungeon_id)
        if dungeon is None:
            return ExploreResult(False, "알 수 없는 던전입니다.", profile, daily_remaining=self.daily_remaining(profile))
        remaining = self.daily_remaining(profile)
        if EXPLORE_LIMIT_ENABLED:
            self._reset_daily_if_needed(profile)
            remaining = self.daily_remaining(profile)
            if remaining <= 0:
                return ExploreResult(False, f"오늘 탐색 횟수를 모두 사용했습니다. 하루 {DAILY_EXPLORES}회까지 가능합니다.", profile, dungeon, daily_remaining=0)
        if profile.level < dungeon.level_req:
            return ExploreResult(False, f"{dungeon.name}은 Lv.{dungeon.level_req}부터 입장할 수 있습니다.", profile, dungeon, daily_remaining=remaining)

        enemy = self._choose_enemy(dungeon)
        if EXPLORE_LIMIT_ENABLED:
            profile.daily_explores_used += 1
        battle = self._simulate_battle(profile, enemy.name, self._enemy_stats(enemy.stats))
        reward = RewardReport()
        if battle.won:
            profile.dungeon_clear_count += 1
            reward = self._grant_reward(profile, enemy.gold, enemy.exp, enemy.rewards, victory=True)
        else:
            reward = self._grant_reward(profile, enemy.gold, enemy.exp, None, victory=False)
        return ExploreResult(
            True,
            "탐색 완료",
            profile,
            dungeon,
            enemy,
            battle,
            reward,
            daily_remaining=self.daily_remaining(profile),
        )

    def challenge_boss(self, user_id: int, display_name: str, boss_id: str) -> BossResult:
        profile = self.get_profile(user_id, display_name)
        boss = BOSS_BY_ID.get(boss_id)
        if boss is None:
            return BossResult(False, "알 수 없는 보스입니다.", profile)
        if profile.level < boss.level_req:
            return BossResult(False, f"{boss.name}은 Lv.{boss.level_req}부터 도전할 수 있습니다.", profile, boss)

        weekly_key = self._week_key()
        battle = self._simulate_battle(
            profile,
            boss.name,
            self._enemy_stats(boss.stats),
            boss=boss,
        )
        reward = self._grant_boss_reward_to_profile(profile, boss, victory=battle.won, weekly_key=weekly_key)
        self._save()
        return BossResult(True, "보스 도전 완료", profile, boss, battle, reward, weekly_key)

    def grant_boss_reward(
        self,
        user_id: int,
        display_name: str,
        boss_id: str,
        *,
        victory: bool = True,
    ) -> RewardReport:
        profile = self.get_profile(user_id, display_name)
        boss = BOSS_BY_ID[boss_id]
        weekly_key = self._week_key()
        reward = self._grant_boss_reward_to_profile(profile, boss, victory=victory, weekly_key=weekly_key)
        self._save()
        return reward

    def _boss_reward_locked(self, profile: PlayerProfile, boss_id: str, weekly_key: str) -> bool:
        return (
            BOSS_WEEKLY_REWARD_LIMIT_ENABLED
            and profile.weekly_boss_clears.get(boss_id) == weekly_key
        )

    def _grant_boss_reward_to_profile(
        self,
        profile: PlayerProfile,
        boss: BossTemplate,
        *,
        victory: bool,
        weekly_key: str,
    ) -> RewardReport:
        if not victory:
            return RewardReport()
        reward_locked = self._boss_reward_locked(profile, boss.id, weekly_key)
        if reward_locked:
            return RewardReport(weekly_reward_locked=True)

        reward = self._grant_reward(
            profile,
            boss.gold,
            boss.exp,
            boss.rewards if victory else None,
            victory=victory,
        )
        if victory:
            reward.weekly_reward_claimed = True
            profile.boss_clear_count += 1
            if BOSS_WEEKLY_REWARD_LIMIT_ENABLED:
                profile.weekly_boss_clears[boss.id] = weekly_key
        return reward

    def enhancement_preview(self, user_id: int, display_name: str, item_uid: int) -> EnhancementPreview:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementPreview(False, "해당 장비를 찾지 못했습니다.", profile)
        if item.destroyed:
            return EnhancementPreview(False, "파괴된 흔적은 먼저 복구해야 합니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        if item.stars >= MAX_ENHANCEMENT_STARS:
            return EnhancementPreview(False, "이미 최대 강화 단계입니다.", profile, item)
        before_stats = scaled_item_stats(item.template_id, item.stars)
        after_stats = scaled_item_stats(item.template_id, item.stars + 1)
        return EnhancementPreview(
            True,
            "강화할 장비를 확인하세요.",
            profile,
            item,
            enhancement_cost(template.rarity, item.stars),
            enhancement_odds(template.rarity, item.stars),
            before_stats,
            after_stats,
            stat_delta(before_stats, after_stats),
            item.stars,
            item.stars + 1,
        )

    def restore_preview(
        self,
        user_id: int,
        display_name: str,
        item_uid: int,
        spare_uid: int | None = None,
    ) -> EnhancementPreview:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementPreview(False, "해당 장비를 찾지 못했습니다.", profile)
        if not item.destroyed:
            return EnhancementPreview(False, "파괴된 장비가 아닙니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        cost = restore_cost(template.rarity)
        spare = self._find_restore_spare(profile, item, spare_uid)
        before_stars = max(0, int(item.stars))
        after_stars = self._restore_target_stars(item)
        before_stats = scaled_item_stats(item.template_id, before_stars)
        after_stats = scaled_item_stats(item.template_id, after_stars)
        if spare is None:
            message = (
                "선택한 스페어를 사용할 수 없습니다."
                if spare_uid is not None
                else f"복구에는 같은 장비 스페어 1개가 필요합니다. 필요 장비: {template.name}"
            )
            return EnhancementPreview(
                False,
                message,
                profile,
                item,
                cost,
                before_stats=before_stats,
                after_stats=after_stats,
                before_stars=before_stars,
                after_stars=after_stars,
            )
        if profile.gold < cost:
            return EnhancementPreview(
                False,
                f"골드가 부족합니다. 필요: {cost}G, 보유: {profile.gold}G",
                profile,
                item,
                cost,
                before_stats=before_stats,
                after_stats=after_stats,
                before_stars=before_stars,
                after_stars=after_stars,
                spare_item=spare,
            )
        return EnhancementPreview(
            True,
            f"복구할 장비를 확인하세요. +{before_stars} 흔적 → +{after_stars}",
            profile,
            item,
            cost,
            before_stats=before_stats,
            after_stats=after_stats,
            before_stars=before_stars,
            after_stars=after_stars,
            spare_item=spare,
        )

    def enhance(self, user_id: int, display_name: str, item_uid: int) -> EnhancementResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementResult(False, "해당 장비를 찾지 못했습니다.", profile)
        if item.destroyed:
            return EnhancementResult(False, "파괴된 흔적은 먼저 복구해야 합니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        if item.stars >= MAX_ENHANCEMENT_STARS:
            return EnhancementResult(False, "이미 최대 강화 단계입니다.", profile, item)

        cost = enhancement_cost(template.rarity, item.stars)
        odds = enhancement_odds(template.rarity, item.stars)
        before = item.stars
        if profile.gold < cost:
            return EnhancementResult(False, f"골드가 부족합니다. 필요: {cost}G, 보유: {profile.gold}G", profile, item, cost, before, before, "no_gold", odds)

        profile.gold -= cost
        roll = self.rng.random()
        success, _fail, destroy = odds
        if roll < success:
            item.stars += 1
            outcome = "success"
        elif roll < success + destroy:
            item.destroyed = True
            profile.equipped_item_uids = [
                uid for uid in profile.equipped_item_uids
                if uid != item.uid
            ]
            outcome = "destroyed"
        else:
            outcome = "failed"
        self._save()
        return EnhancementResult(True, "강화 완료", profile, item, cost, before, item.stars, outcome, odds)

    def restore(
        self,
        user_id: int,
        display_name: str,
        item_uid: int,
        spare_uid: int | None = None,
    ) -> EnhancementResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementResult(False, "해당 장비를 찾지 못했습니다.", profile)
        if not item.destroyed:
            return EnhancementResult(False, "파괴된 장비가 아닙니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        cost = restore_cost(template.rarity)
        spare = self._find_restore_spare(profile, item, spare_uid)
        before_stars = max(0, int(item.stars))
        after_stars = self._restore_target_stars(item)
        if spare is None:
            message = (
                "선택한 스페어를 사용할 수 없습니다."
                if spare_uid is not None
                else f"복구에는 같은 장비 스페어 1개가 필요합니다. 필요 장비: {template.name}"
            )
            return EnhancementResult(
                False,
                message,
                profile,
                item,
                cost,
                before_stars,
                after_stars,
                "no_spare",
            )
        if profile.gold < cost:
            return EnhancementResult(
                False,
                f"골드가 부족합니다. 필요: {cost}G, 보유: {profile.gold}G",
                profile,
                item,
                cost,
                before_stars,
                after_stars,
                "no_gold",
            )
        profile.gold -= cost
        profile.inventory = [
            inventory_item for inventory_item in profile.inventory
            if inventory_item.uid != spare.uid
        ]
        profile.equipped_item_uids = [
            equipped_uid for equipped_uid in profile.equipped_item_uids
            if equipped_uid != spare.uid
        ]
        item.destroyed = False
        item.stars = after_stars
        self._save()
        return EnhancementResult(True, "복구 완료", profile, item, cost, before_stars, after_stars, "restored", spare_item=spare)

    def equip_item(self, user_id: int, display_name: str, item_uid: int) -> EquipmentResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EquipmentResult(False, "해당 장비를 찾지 못했습니다.", profile)
        if item.destroyed:
            return EquipmentResult(False, "파괴된 장비는 장착할 수 없습니다.", profile, item)
        self._cleanup_equipped_items(profile)
        if item.uid in profile.equipped_item_uids:
            return EquipmentResult(True, "이미 장착 중인 장비입니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        if template.rarity == "legendary" and self._has_equipped_legendary(profile):
            return EquipmentResult(False, "레전드리 장비는 하나만 장착할 수 있습니다.", profile, item)
        if len(profile.equipped_item_uids) >= MAX_EQUIPPED_ITEMS:
            return EquipmentResult(False, f"장비는 최대 {MAX_EQUIPPED_ITEMS}개까지 장착할 수 있습니다.", profile, item)
        profile.equipped_item_uids.append(item.uid)
        self._save()
        return EquipmentResult(True, "장비를 장착했습니다.", profile, item)

    def set_equipped_items(self, user_id: int, display_name: str, item_uids: list[int]) -> EquipmentResult:
        profile = self.get_profile(user_id, display_name)
        valid = {
            item.uid: item for item in profile.inventory
            if not item.destroyed and item.template_id in ITEM_BY_ID
        }
        selected = []
        has_legendary = False
        for uid in item_uids:
            if uid in valid and uid not in selected:
                template = ITEM_BY_ID[valid[uid].template_id]
                if template.rarity == "legendary":
                    if has_legendary:
                        continue
                    has_legendary = True
                selected.append(uid)
            if len(selected) >= MAX_EQUIPPED_ITEMS:
                break
        profile.equipped_item_uids = selected
        self._save()
        return EquipmentResult(True, "장착 상태를 저장했습니다.", profile)

    def auto_equip_best(self, user_id: int, display_name: str) -> EquipmentResult:
        profile = self.get_profile(user_id, display_name)
        candidates = sorted(
            [
                item for item in profile.inventory
                if not item.destroyed and item.template_id in ITEM_BY_ID
            ],
            key=self.item_score,
            reverse=True,
        )
        best = []
        has_legendary = False
        for item in candidates:
            template = ITEM_BY_ID[item.template_id]
            if template.rarity == "legendary":
                if has_legendary:
                    continue
                has_legendary = True
            best.append(item)
            if len(best) >= MAX_EQUIPPED_ITEMS:
                break
        profile.equipped_item_uids = [item.uid for item in best]
        self._save()
        return EquipmentResult(True, "전투력 기준 최강 장비를 장착했습니다.", profile)

    def unequip_item(self, user_id: int, display_name: str, item_uid: int) -> EquipmentResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item_uid not in profile.equipped_item_uids:
            return EquipmentResult(False, "장착 중인 장비가 아닙니다.", profile, item)
        profile.equipped_item_uids = [
            uid for uid in profile.equipped_item_uids
            if uid != item_uid
        ]
        self._save()
        return EquipmentResult(True, "장비를 해제했습니다.", profile, item)

    def toggle_equip_item(self, user_id: int, display_name: str, item_uid: int) -> EquipmentResult:
        profile = self.get_profile(user_id, display_name)
        if item_uid in profile.equipped_item_uids:
            return self.unequip_item(user_id, display_name, item_uid)
        return self.equip_item(user_id, display_name, item_uid)

    def sell_item(self, user_id: int, display_name: str, item_uid: int) -> SellResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return SellResult(False, "해당 장비를 찾지 못했습니다.", profile)
        if item.uid in profile.equipped_item_uids:
            return SellResult(False, "장착 중인 장비는 먼저 장착 해제해야 판매할 수 있습니다.", profile)
        price = self.item_sell_price(item)
        profile.inventory = [owned for owned in profile.inventory if owned.uid != item.uid]
        profile.gold += price
        self._save()
        return SellResult(True, "장비를 판매했습니다.", profile, price, 1, [self.item_title(item)])

    def sell_items_by_uids(self, user_id: int, display_name: str, item_uids: list[int]) -> SellResult:
        profile = self.get_profile(user_id, display_name)
        equipped = set(profile.equipped_item_uids)
        selected = set(item_uids)
        sold_items = []
        kept_items = []
        total_gold = 0
        for item in profile.inventory:
            if item.uid in selected and item.uid not in equipped and item.template_id in ITEM_BY_ID:
                total_gold += self.item_sell_price(item)
                sold_items.append(self.item_title(item))
            else:
                kept_items.append(item)
        if not sold_items:
            return SellResult(False, "판매할 수 있는 선택 장비가 없습니다.", profile)
        profile.inventory = kept_items
        profile.gold += total_gold
        self._save()
        return SellResult(True, "선택한 장비를 판매했습니다.", profile, total_gold, len(sold_items), sold_items)

    def sell_items_by_rarity(self, user_id: int, display_name: str, rarities: list[str]) -> SellResult:
        profile = self.get_profile(user_id, display_name)
        rarity_set = {rarity for rarity in rarities if rarity in RARITIES}
        equipped = set(profile.equipped_item_uids)
        sold_items = []
        kept_items = []
        total_gold = 0
        for item in profile.inventory:
            template = ITEM_BY_ID.get(item.template_id)
            if template is not None and template.rarity in rarity_set and item.uid not in equipped:
                total_gold += self.item_sell_price(item)
                sold_items.append(self.item_title(item))
            else:
                kept_items.append(item)
        if not sold_items:
            return SellResult(False, "해당 등급에서 판매할 수 있는 장비가 없습니다.", profile)
        profile.inventory = kept_items
        profile.gold += total_gold
        self._save()
        return SellResult(True, "선택 등급 장비를 일괄 판매했습니다.", profile, total_gold, len(sold_items), sold_items)

    def set_auto_sell_rarities(self, user_id: int, display_name: str, rarities: list[str]) -> SellResult:
        profile = self.get_profile(user_id, display_name)
        selected = [
            rarity for rarity in RARITIES
            if rarity in set(rarities)
        ]
        profile.auto_sell_rarities = selected
        self._save()
        return SellResult(True, "자동판매 등급 설정을 저장했습니다.", profile)

    def sell_auto_sell_items(self, user_id: int, display_name: str) -> SellResult:
        profile = self.get_profile(user_id, display_name)
        if not profile.auto_sell_rarities:
            return SellResult(False, "자동판매 등급이 설정되어 있지 않습니다.", profile)
        return self.sell_items_by_rarity(user_id, display_name, profile.auto_sell_rarities)

    def item_sell_price(self, item: ItemInstance) -> int:
        return sell_price(item.template_id, item.stars, destroyed=item.destroyed)

    def equipped_items(self, profile: PlayerProfile) -> list[ItemInstance]:
        valid_items = [
            item for item in profile.inventory
            if not item.destroyed and item.template_id in ITEM_BY_ID
        ]
        by_uid = {item.uid: item for item in valid_items}
        equipped = [
            by_uid[uid]
            for uid in profile.equipped_item_uids
            if uid in by_uid
        ][:MAX_EQUIPPED_ITEMS]
        return equipped

    def item_score(self, item: ItemInstance) -> float:
        if item.template_id not in ITEM_BY_ID:
            return 0.0
        score = 0.0
        for key, value in scaled_item_stats(item.template_id, item.stars).items():
            if key == "base_atk":
                score += value * 20
            elif key == "max_hp":
                score += value * 2.0
            elif key == "dmg_mitigation":
                score += value * 28
            else:
                score += value * 850
        return score

    def item_title(self, item: ItemInstance) -> str:
        template = ITEM_BY_ID[item.template_id]
        destroyed = " 흔적" if item.destroyed else ""
        return f"[{RARITY_LABELS[template.rarity]}] {template.name} +{item.stars}{destroyed}"

    def item_stats_text(self, item: ItemInstance) -> str:
        stats = scaled_item_stats(item.template_id, item.stars)
        stat_text = self.format_stats(stats, signed=True)
        effect_text = self.item_template_effects_text(item.template_id)
        if effect_text:
            if stat_text == "스탯 없음":
                return f"영속 효과: {effect_text}"
            return f"{stat_text}\n영속 효과: {effect_text}"
        return stat_text

    def item_template_effects_text(self, template_id: str) -> str:
        template = ITEM_BY_ID.get(template_id)
        if template is None:
            return ""
        parts = self._stat_effect_summary_parts(
            template.stat_effects,
            {},
            self_label="자신",
            allies_label="참전자 모두",
        )
        parts.extend(
            self.special_effects_summary(
                template.effects,
                self_label="자신",
                allies_label="참전자 모두",
            )
        )
        return " · ".join(parts)

    def material_name(self, material_id: str) -> str:
        material = MATERIAL_BY_ID.get(material_id)
        return material.name if material is not None else material_id

    def material_quantity_text(self, profile: PlayerProfile, material_id: str, required: int | None = None) -> str:
        owned = profile.materials.get(material_id, 0)
        if required is None:
            return f"{self.material_name(material_id)} x{owned}"
        return f"{self.material_name(material_id)} {owned}/{required}"

    def material_cost_text(self, profile: PlayerProfile, materials: dict[str, int]) -> str:
        if not materials:
            return "재료 없음"
        return ", ".join(
            self.material_quantity_text(profile, material_id, amount)
            for material_id, amount in materials.items()
        )

    def recipe_result_text(self, recipe: CraftingRecipe) -> str:
        template = ITEM_BY_ID.get(recipe.result_item_id)
        if template is None:
            return "알 수 없는 장비"
        stats = scaled_item_stats(template.id, recipe.result_stars)
        stars = f" +{recipe.result_stars}" if recipe.result_stars else ""
        lines = [
            f"[{RARITY_LABELS[template.rarity]}] {template.name}{stars}",
            self.format_stats(stats, signed=True),
        ]
        effect_text = self.item_template_effects_text(template.id)
        if effect_text:
            lines.append(f"영속 효과: {effect_text}")
        return "\n".join(lines)

    def recipe_status_text(self, profile: PlayerProfile, recipe: CraftingRecipe) -> str:
        if recipe.result_item_id not in ITEM_BY_ID:
            return "설정 오류"
        if profile.level < recipe.level_req:
            return f"Lv.{recipe.level_req} 필요"
        missing_materials = self.missing_crafting_materials(profile, recipe)
        missing_gold = max(0, recipe.gold - profile.gold)
        if not missing_materials and missing_gold <= 0:
            return "제작 가능"
        bits = []
        if missing_gold:
            bits.append(f"골드 -{missing_gold}G")
        for material_id, amount in missing_materials.items():
            bits.append(f"{self.material_name(material_id)} -{amount}")
        return "부족: " + ", ".join(bits)

    def reward_summary(self, reward: RewardTemplate, *, base_gold: int = 0, base_exp: int = 0) -> str:
        parts = []
        if base_gold:
            parts.append(f"{base_gold}G")
        if base_exp:
            parts.append(f"{base_exp}EXP")
        if reward.item_drops:
            parts.append("장비")
        if reward.material_drops:
            material_names = ", ".join(self.material_name(drop.id) for drop in reward.material_drops[:3])
            parts.append(f"재료 {material_names}")
        return " · ".join(parts) if parts else "보상 없음"

    def format_stats(self, stats: CombatStats | dict[str, float], *, signed: bool = False) -> str:
        raw = stats.__dict__ if isinstance(stats, CombatStats) else stats
        parts: list[str] = []
        for key in STAT_ORDER:
            value = raw.get(key, 0)
            if not value:
                continue
            numeric_value = float(value)
            parts.append(
                f"{self._format_stat_label(key, numeric_value)} "
                f"{self._format_stat_value(key, numeric_value, signed=signed)}"
            )
        return ", ".join(parts) if parts else "스탯 없음"

    def _stat_effect_summary_parts(
        self,
        effects: list[StatEffect],
        legacy_mods: dict[str, float],
        *,
        self_label: str,
        allies_label: str,
    ) -> list[str]:
        if not effects:
            return [f"{self_label} {self.format_stats(legacy_mods, signed=True)}"] if legacy_mods else []

        parts: list[str] = []
        for effect in effects:
            if not effect.stat or not effect.value:
                continue
            target_label = allies_label if effect.target == "allies" else self_label
            stat_text = self.format_stats({effect.stat: effect.value}, signed=True)
            if stat_text == "스탯 없음":
                continue
            extras = [self._effect_duration_summary(effect.duration)]
            if effect.stat == "life_steal":
                cap_text = self._heal_cap_summary(effect.heal_cap)
                if cap_text:
                    extras.append(f"흡수 상한 {cap_text}")
            if effect.undispellable:
                extras.append("소거불가")
            parts.append(f"{target_label} {stat_text} ({', '.join(extras)})")
        return parts

    def skill_summary(self, skill: SkillTemplate) -> str:
        parts: list[str] = []
        if skill.damage_multiplier > 0 and skill.hits > 0:
            parts.append(f"{skill.damage_multiplier * 100:.0f}% x {skill.hits}")
        if skill.heal_power > 0:
            heal_target = "참전자 모두 " if skill.heal_target == "allies" else ""
            parts.append(f"{heal_target}회복 {skill.heal_power:.2f}x")
            cap_text = self._heal_cap_summary(skill.heal_cap)
            if cap_text:
                parts.append(f"회복 상한 {cap_text}")
        parts.extend(
            self._stat_effect_summary_parts(
                skill.player_stat_effects,
                skill.player_mods,
                self_label="자신",
                allies_label="참전자 모두",
            )
        )
        if skill.damage_cut > 0 and "damage_cut" not in skill.player_mods:
            parts.append(f"피해 차단 {skill.damage_cut * 100:.0f}%")
        parts.extend(
            self._stat_effect_summary_parts(
                skill.enemy_stat_effects,
                skill.enemy_mods,
                self_label="적",
                allies_label="적 전체",
            )
        )
        player_effects = self.special_effects_summary(
            skill.player_effects,
            self_label="자신",
            allies_label="참전자 모두",
        )
        if player_effects:
            parts.extend(player_effects)
        enemy_effects = self.special_effects_summary(
            skill.enemy_effects,
            self_label="적",
            allies_label="적 전체",
        )
        if enemy_effects:
            parts.extend(enemy_effects)
        action_summary = self.effect_actions_summary(skill.effect_actions)
        if action_summary:
            parts.append(action_summary)
        if skill.cooldown > 0:
            parts.append(f"쿨 {skill.cooldown}턴")
        if skill.uses > 0:
            parts.append(f"전투당 {skill.uses}회")
        return " · ".join(parts) if parts else "기본 효과"

    def special_effects_summary(
        self,
        effects: CombatSpecialEffects,
        *,
        self_label: str = "자신",
        allies_label: str = "참전자 모두",
    ) -> list[str]:
        parts = []
        if effects.flurry is not None:
            parts.append(
                f"{allies_label if effects.flurry.target == 'allies' else self_label} 난격 {effects.flurry.count}"
                f"{self._effect_meta_summary(effects.flurry.duration, effects.flurry.undispellable)}"
            )
        if effects.double_strike is not None:
            parts.append(
                f"{allies_label if effects.double_strike.target == 'allies' else self_label} 재행동 {effects.double_strike.count}회"
                f"{self._effect_meta_summary(effects.double_strike.duration, effects.double_strike.undispellable)}"
            )
        for bonus in effects.bonus_damage:
            parts.append(
                f"{allies_label if bonus.target == 'allies' else self_label} 추격 {bonus.ratio * 100:.0f}%"
                f"{self._effect_meta_summary(bonus.duration, bonus.undispellable)}"
            )
        for reinforce in effects.critical_reinforce:
            parts.append(
                f"{allies_label if reinforce.target == 'allies' else self_label} 크리 리인포스 {reinforce.ratio * 100:.0f}%"
                f"{self._effect_meta_summary(reinforce.duration, reinforce.undispellable)}"
            )
        for final_effect in effects.final_damage:
            parts.append(
                f"{allies_label if final_effect.target == 'allies' else self_label} 최종 데미지 {self._signed_effect_ratio_text(final_effect.ratio)}"
                f"{self._effect_meta_summary(final_effect.duration, final_effect.undispellable)}"
            )
        for post_attack in effects.post_attack_ability_damage:
            parts.append(
                f"{allies_label if post_attack.target == 'allies' else self_label} 공격 후 어빌 피해 {post_attack.ratio * 100:.0f}% {post_attack.count}타"
                f"{self._effect_meta_summary(post_attack.duration, post_attack.undispellable)}"
            )
        for guard in effects.dispel_guard:
            parts.append(
                f"{allies_label if guard.target == 'allies' else self_label} 디스펠 가드"
                f"{self._guard_meta_summary(guard.duration, guard.count, guard.undispellable)}"
            )
        for veil in effects.veil:
            parts.append(
                f"{allies_label if veil.target == 'allies' else self_label} 마운트"
                f"{self._guard_meta_summary(veil.duration, veil.count, veil.undispellable)}"
            )
        return parts

    def _effect_meta_summary(self, duration: int, undispellable: bool = False) -> str:
        extras = [self._effect_duration_summary(duration)]
        if undispellable:
            extras.append("소거불가")
        return f" ({', '.join(extras)})"

    def _guard_meta_summary(self, duration: int, count: int, undispellable: bool = False) -> str:
        extras = [f"{count}회" if count > 0 else self._effect_duration_summary(duration)]
        if undispellable:
            extras.append("소거불가")
        return f" ({', '.join(extras)})"

    def _effect_duration_summary(self, duration: int) -> str:
        if duration < 0:
            return "무한"
        return f"{max(1, int(duration))}턴"

    def _signed_effect_ratio_text(self, ratio: float) -> str:
        direction = "증가" if ratio >= 0 else "감소"
        return f"{direction} {abs(ratio) * 100:.0f}%"

    def effect_actions_summary(self, actions: list[EffectAction]) -> str:
        labels = {
            "dispel": "디스펠",
            "clear_all": "클리어 올",
            "stack_increase": "스택 증가",
            "stack_decrease": "스택 감소",
            "stack_set": "스택 지정",
            "stack_remove": "스택 제거",
            "stack_max": "스택 최대",
        }
        targets = {
            "self": "자신",
            "me": "자신",
            "enemy": "상대",
            "ally": "아군",
            "allies": "참전자 모두",
            "opponent": "상대",
            "opponents": "상대 전체",
            "enemies": "상대 전체",
        }
        parts = []
        for action in actions:
            label = labels.get(action.action, action.action)
            target = targets.get(action.target, action.target)
            if action.action in STACK_EFFECT_ACTIONS:
                template = STACK_EFFECT_BY_ID.get(action.stack_effect_id)
                effect_name = template.name if template is not None else action.stack_effect_id
                value = "" if action.action in {"stack_remove", "stack_max"} else f" {action.value}"
                parts.append(f"{label}({target}, {effect_name}{value})")
            else:
                count = f" x{action.count}" if action.count > 1 else ""
                parts.append(f"{label}({target}{count})")
        return ", ".join(parts)

    def level_progress(self, profile: PlayerProfile) -> tuple[int, int]:
        previous = previous_level_exp(profile.level)
        required = max(1, next_level_exp(profile.level) - previous)
        progress = max(0, min(required, profile.exp - previous))
        return progress, required

    def _simulate_battle(
        self,
        profile: PlayerProfile,
        enemy_name: str,
        enemy_base_stats: CombatStats,
        *,
        boss: BossTemplate | None = None,
    ) -> BattleReport:
        player_base = self._player_stats(profile)
        enemy_base = enemy_base_stats
        player_hp = player_base.final_hp
        enemy_hp = enemy_base.final_hp
        player_effects: list[ActiveEffect] = self._permanent_effects(profile)
        enemy_effects: list[ActiveEffect] = []
        triggered_patterns: set[int] = set()
        skills = self.equipped_skills(profile)
        uses_left = {skill.id: skill.uses for skill in skills if skill.uses > 0}
        cooldowns = {skill.id: 0 for skill in skills}
        log: list[str] = []
        skills_used: list[str] = []

        for turn in range(1, 25):
            player_stats = self._stats_with_effects(player_base, player_effects)
            enemy_stats = self._stats_with_effects(enemy_base, enemy_effects)
            skill = self._choose_skill(
                skills,
                uses_left,
                cooldowns,
                player_effects,
                enemy_effects,
                player_stats,
                enemy_stats,
                player_hp,
                enemy_hp,
            )
            if skill is None:
                attack = self._basic_attack(player_stats, player_hp, enemy_stats, enemy_hp, player_effects)
                dealt_segments = self._clamped_damage_segments(attack.life_steal_segments, enemy_hp)
                enemy_hp = max(0, enemy_hp - attack.damage)
                attack.heal = self._life_steal_heal_segments(
                    player_stats,
                    player_effects,
                    dealt_segments,
                    player_stats.final_hp,
                )
                if attack.heal > 0:
                    player_hp = min(player_stats.final_hp, player_hp + attack.heal)
                log_text = self._attack_log_text(attack)
                log.append(f"{turn}T 기본 공격: {enemy_name}에게 {log_text}")
            else:
                self._mark_skill_used(skill, uses_left, cooldowns)
                skills_used.append(skill.name)
                skill_result = self._use_player_skill(
                    skill,
                    player_stats,
                    enemy_stats,
                    player_hp,
                    enemy_hp,
                    player_effects,
                    enemy_effects,
                    ally_effects=[player_effects],
                    opponent_effects=[enemy_effects],
                )
                life_steal_heal = 0
                if skill_result.damage > 0:
                    dealt_damage = min(enemy_hp, skill_result.damage)
                    enemy_hp = max(0, enemy_hp - skill_result.damage)
                    life_steal_heal = self._life_steal_heal(
                        player_stats,
                        player_effects,
                        dealt_damage,
                        player_stats.final_hp,
                    )
                total_heal = skill_result.heal + life_steal_heal
                if total_heal > 0:
                    player_hp = min(player_stats.final_hp, player_hp + total_heal)
                action_bits = []
                if skill_result.damage > 0:
                    action_bits.append(f"{skill_result.damage} 피해")
                if skill_result.dispels:
                    action_bits.append(f"디스펠 {skill_result.dispels}회")
                if skill_result.clear_alls:
                    action_bits.append(f"클리어 올 {skill_result.clear_alls}회")
                if skill_result.heal > 0:
                    action_bits.append(f"{skill_result.heal} 회복")
                if life_steal_heal > 0:
                    action_bits.append(f"{life_steal_heal} 흡수")
                if not action_bits:
                    action_bits.append("효과 발동")
                log.append(f"{turn}T {skill.name}: {', '.join(action_bits)}")

            if enemy_hp <= 0:
                return BattleReport(True, turn, player_hp, player_base.final_hp, 0, enemy_base.final_hp, self._trim_log(log), skills_used)

            enemy_stats = self._stats_with_effects(enemy_base, enemy_effects)
            player_stats = self._stats_with_effects(player_base, player_effects)
            pattern = self._next_boss_pattern(boss, enemy_hp, enemy_base.final_hp, triggered_patterns)
            if pattern is None:
                attack = self._basic_attack(enemy_stats, enemy_hp, player_stats, player_hp, enemy_effects)
                dealt_segments = self._clamped_damage_segments(attack.life_steal_segments, player_hp)
                player_hp = max(0, player_hp - attack.damage)
                attack.heal = self._life_steal_heal_segments(
                    enemy_stats,
                    enemy_effects,
                    dealt_segments,
                    enemy_stats.final_hp,
                )
                if attack.heal > 0:
                    enemy_hp = min(enemy_stats.final_hp, enemy_hp + attack.heal)
                log.append(f"{turn}T {enemy_name} 반격: {self._attack_log_text(attack)}")
            else:
                damage = self._use_boss_pattern(pattern, enemy_stats, player_stats, enemy_hp, player_hp, player_effects, enemy_effects)
                if damage > 0:
                    dealt_damage = min(player_hp, damage)
                    player_hp = max(0, player_hp - damage)
                    heal = self._life_steal_heal(enemy_stats, enemy_effects, dealt_damage, enemy_stats.final_hp)
                    if heal > 0:
                        enemy_hp = min(enemy_stats.final_hp, enemy_hp + heal)
                    heal_text = f", {heal} 흡수" if heal > 0 else ""
                    log.append(f"{turn}T {pattern.name}: {damage} 피해{heal_text}")
                else:
                    log.append(f"{turn}T {pattern.name}: 특수 효과 발동")

            if player_hp <= 0:
                return BattleReport(False, turn, 0, player_base.final_hp, enemy_hp, enemy_base.final_hp, self._trim_log(log), skills_used)

            player_effects = self._tick_effects(player_effects)
            enemy_effects = self._tick_effects(enemy_effects)
            self._tick_cooldowns(cooldowns)

        return BattleReport(False, 24, player_hp, player_base.final_hp, enemy_hp, enemy_base.final_hp, self._trim_log(log), skills_used)

    def _choose_skill(
        self,
        skills: list[SkillTemplate],
        uses_left: dict[str, int],
        cooldowns: dict[str, int],
        player_effects: list[ActiveEffect],
        enemy_effects: list[ActiveEffect],
        player_stats: CombatStats,
        enemy_stats: CombatStats,
        player_hp: int,
        enemy_hp: int,
    ) -> SkillTemplate | None:
        available = [
            skill for skill in skills
            if self._skill_ready(skill, uses_left, cooldowns)
        ]
        if not available:
            return None

        player_ratio = self._hp_ratio(player_hp, player_stats.final_hp)
        enemy_ratio = self._hp_ratio(enemy_hp, enemy_stats.final_hp)
        incoming = self._estimated_basic_attack_damage(enemy_stats, enemy_hp, player_stats, player_hp, enemy_effects)

        heal_skills = [skill for skill in available if skill.role == "heal" and skill.heal_power > 0]
        if heal_skills:
            heal_skills.sort(key=lambda skill: skill.heal_power, reverse=True)
            best_heal = heal_skills[0]
            expected_heal = self._outgoing_damage(player_stats, player_hp) * best_heal.heal_power
            missing_hp = player_stats.final_hp - player_hp
            if player_ratio <= 0.55 or missing_hp >= expected_heal * 0.65 or incoming >= player_hp * 0.65:
                return best_heal

        defense_skills = [
            skill for skill in available
            if skill.role == "defense" and not self._has_active_effect(player_effects, skill.id)
        ]
        if defense_skills and (player_ratio <= 0.72 or incoming >= player_stats.final_hp * 0.16):
            defense_skills.sort(
                key=lambda skill: (
                    skill.damage_cut
                    + skill.player_mods.get("damage_cut", 0)
                    + skill.player_mods.get("defense", 0)
                    + skill.player_mods.get("garrison", 0)
                ),
                reverse=True,
            )
            return defense_skills[0]

        buff_skills = [
            skill for skill in available
            if skill.role == "buff" and not self._has_active_effect(player_effects, skill.id)
        ]
        if buff_skills and enemy_ratio >= 0.42:
            buff_skills.sort(key=lambda skill: skill.player_mods.get("atk", 0) + skill.player_mods.get("strength", 0) + skill.player_mods.get("dmg_amplification", 0), reverse=True)
            return buff_skills[0]

        debuff_skills = [
            skill for skill in available
            if skill.role == "debuff" and not self._has_active_effect(enemy_effects, skill.id)
        ]
        if debuff_skills and enemy_ratio >= 0.35:
            debuff_skills.sort(key=lambda skill: abs(sum(skill.enemy_mods.values())) + skill.damage_cut, reverse=True)
            return debuff_skills[0]

        attack_skills = [
            skill for skill in available
            if skill.damage_multiplier > 0 and skill.hits > 0
        ]
        if not attack_skills:
            return None
        attack_skills.sort(
            key=lambda skill: self._estimated_skill_damage(
                skill,
                player_stats,
                player_hp,
                enemy_stats,
                enemy_hp,
                player_effects,
            ),
            reverse=True,
        )
        best_attack = attack_skills[0]
        best_damage = self._estimated_skill_damage(
            best_attack,
            player_stats,
            player_hp,
            enemy_stats,
            enemy_hp,
            player_effects,
        )
        base_damage = self._estimated_basic_attack_damage(player_stats, player_hp, enemy_stats, enemy_hp, player_effects)
        if best_damage >= enemy_hp or best_damage >= base_damage * 1.15:
            return best_attack
        return None

    def _skill_ready(
        self,
        skill: SkillTemplate,
        uses_left: dict[str, int],
        cooldowns: dict[str, int],
    ) -> bool:
        if cooldowns.get(skill.id, 0) > 0:
            return False
        if skill.uses > 0 and uses_left.get(skill.id, 0) <= 0:
            return False
        return True

    def _mark_skill_used(
        self,
        skill: SkillTemplate,
        uses_left: dict[str, int],
        cooldowns: dict[str, int],
    ) -> None:
        if skill.uses > 0:
            uses_left[skill.id] = max(0, uses_left.get(skill.id, 0) - 1)
        if skill.cooldown > 0:
            cooldowns[skill.id] = skill.cooldown

    def _estimated_skill_damage(
        self,
        skill: SkillTemplate,
        player_stats: CombatStats,
        player_hp: int,
        enemy_stats: CombatStats,
        enemy_hp: int,
        player_effects: list[ActiveEffect] | None = None,
    ) -> float:
        if skill.damage_multiplier <= 0 or skill.hits <= 0:
            return 0.0
        return sum(
            self._estimated_skill_damage_hit(
                player_stats,
                player_hp,
                enemy_stats,
                enemy_hp,
                skill.damage_multiplier,
                player_effects,
            )
            for _ in range(skill.hits)
        )

    def _use_player_skill(
        self,
        skill: SkillTemplate,
        player_stats: CombatStats,
        enemy_stats: CombatStats,
        player_hp: int,
        enemy_hp: int,
        player_effects: list[ActiveEffect],
        enemy_effects: list[ActiveEffect],
        ally_effects: list[list[ActiveEffect]] | None = None,
        opponent_effects: list[list[ActiveEffect]] | None = None,
        player_stack_effects: list[ActiveStackEffect] | None = None,
        enemy_stack_effects: list[ActiveStackEffect] | None = None,
        ally_stack_effects: list[list[ActiveStackEffect]] | None = None,
        opponent_stack_effects: list[list[ActiveStackEffect]] | None = None,
    ) -> SkillUseResult:
        self._remove_effects_by_source(
            [
                player_effects,
                enemy_effects,
                *(ally_effects or []),
                *(opponent_effects or []),
            ],
            skill.id,
        )
        self._append_targeted_stat_effects(
            player_effects,
            source_id=skill.id,
            effects=skill.player_stat_effects,
            all_targets=ally_effects,
        )
        self._append_effects(
            player_effects,
            source_id=skill.id,
            special=skill.player_effects,
            undispellable=skill.player_undispellable,
            all_targets=ally_effects,
        )
        self._append_targeted_stat_effects(
            enemy_effects,
            source_id=skill.id,
            effects=skill.enemy_stat_effects,
            all_targets=opponent_effects,
        )
        self._append_effects(
            enemy_effects,
            source_id=skill.id,
            special=skill.enemy_effects,
            undispellable=skill.enemy_undispellable,
            all_targets=opponent_effects,
        )

        result = SkillUseResult()
        active_player_effects = self._effects_with_stacks(player_effects, player_stack_effects)
        if skill.damage_multiplier > 0 and skill.hits > 0:
            for _ in range(skill.hits):
                hit_damage = self._actual_skill_damage(
                    player_stats,
                    player_hp,
                    enemy_stats,
                    enemy_hp,
                    skill.damage_multiplier,
                    active_player_effects,
                )
                result.damage += hit_damage
                result.hit_damages.append(hit_damage)
            result.detail_lines.append(
                f"어빌리티({skill.name}): {self._damage_values_text(result.hit_damages)}"
            )

        if skill.heal_power > 0:
            outgoing = self._outgoing_damage(player_stats, player_hp)
            raw_heal = max(1, int(outgoing * skill.heal_power))
            result.raw_heal = raw_heal
            result.heal = self._apply_heal_cap(raw_heal, skill.heal_cap, player_stats.final_hp)
        dispels, clear_alls = self._apply_effect_actions(
            skill.effect_actions,
            self_effects=player_effects,
            enemy_effects=enemy_effects,
            ally_effects=ally_effects,
            opponent_effects=opponent_effects,
            self_stacks=player_stack_effects,
            enemy_stacks=enemy_stack_effects,
            ally_stacks=ally_stack_effects,
            opponent_stacks=opponent_stack_effects,
        )
        result.dispels += dispels
        result.clear_alls += clear_alls
        return result

    def _next_boss_pattern(
        self,
        boss: BossTemplate | None,
        enemy_hp: int,
        enemy_max_hp: int,
        triggered: set[int],
    ) -> BossPattern | None:
        if boss is None:
            return None
        ratio = enemy_hp / max(1, enemy_max_hp)
        for idx, pattern in enumerate(boss.patterns):
            if idx not in triggered and ratio <= pattern.threshold:
                triggered.add(idx)
                return pattern
        return None

    def _use_boss_pattern(
        self,
        pattern: BossPattern,
        boss_stats: CombatStats,
        player_stats: CombatStats,
        boss_hp: int,
        player_hp: int,
        player_effects: list[ActiveEffect],
        enemy_effects: list[ActiveEffect],
        ally_effects: list[list[ActiveEffect]] | None = None,
        opponent_effects: list[list[ActiveEffect]] | None = None,
        boss_stack_effects: list[ActiveStackEffect] | None = None,
        player_stack_effects: list[ActiveStackEffect] | None = None,
        ally_stack_effects: list[list[ActiveStackEffect]] | None = None,
        opponent_stack_effects: list[list[ActiveStackEffect]] | None = None,
        damage_details: list[int] | None = None,
    ) -> int:
        source_id = f"boss:{pattern.name}"
        self._append_targeted_stat_effects(
            player_effects,
            source_id=source_id,
            effects=pattern.player_stat_effects,
            all_targets=opponent_effects,
        )
        self._append_effects(
            player_effects,
            source_id=source_id,
            special=pattern.player_effects,
            undispellable=pattern.player_undispellable,
            all_targets=opponent_effects,
        )
        self._append_targeted_stat_effects(
            enemy_effects,
            source_id=source_id,
            effects=pattern.boss_stat_effects,
            all_targets=ally_effects,
        )
        self._append_effects(
            enemy_effects,
            source_id=source_id,
            special=pattern.boss_effects,
            undispellable=pattern.boss_undispellable,
            all_targets=ally_effects,
        )
        self._apply_effect_actions(
            pattern.effect_actions,
            self_effects=enemy_effects,
            enemy_effects=player_effects,
            ally_effects=ally_effects,
            opponent_effects=opponent_effects,
            self_stacks=boss_stack_effects,
            enemy_stacks=player_stack_effects,
            ally_stacks=ally_stack_effects,
            opponent_stacks=opponent_stack_effects,
        )
        damage = 0
        if pattern.damage_multiplier > 0 and pattern.hits > 0:
            active_boss_effects = self._effects_with_stacks(enemy_effects, boss_stack_effects)
            for _ in range(pattern.hits):
                hit_damage = self._actual_damage(
                    boss_stats,
                    boss_hp,
                    player_stats,
                    player_hp,
                    pattern.damage_multiplier,
                    active_boss_effects,
                )
                damage += hit_damage
                if damage_details is not None:
                    damage_details.append(hit_damage)
        damage += self._plain_damage_value(pattern, player_stats.final_hp)
        return damage

    def _plain_damage_value(self, pattern: BossPattern, target_max_hp: int) -> int:
        plain_damage = getattr(pattern, "plain_damage", None)
        if plain_damage is None or not plain_damage.has_damage:
            return 0
        # Plain damage is fixed damage: it bypasses defense, cuts, mitigation, and amplification.
        if plain_damage.mode == "target_max_hp_ratio":
            return max(0, int(target_max_hp * plain_damage.value))
        return max(0, int(plain_damage.value))

    def _player_stats(self, profile: PlayerProfile) -> CombatStats:
        stats = CombatStats(
            base_atk=self._level_base_atk(profile.level),
            max_hp=self._level_max_hp(profile.level),
            hp_bonus=float(profile.hp_bonus),
            atk=float(profile.atk),
            defense=self._level_defense(profile.level),
            defense_ignore=float(profile.defense_ignore),
            garrison=float(profile.garrison),
            strength=float(profile.strength),
            enmity=float(profile.enmity),
            damage_cut=float(profile.damage_cut),
            dmg_mitigation=float(profile.dmg_mitigation),
            dmg_amplification=float(profile.dmg_amplification),
            dmg_supplement=float(profile.dmg_supplement),
            skill_damage=float(profile.skill_damage),
            skill_dmg_supplement=float(profile.skill_dmg_supplement),
            critical_rate=float(profile.critical_rate),
            critical_damage=float(profile.critical_damage),
            double_attack_rate=float(profile.double_attack_rate),
            triple_attack_rate=float(profile.triple_attack_rate),
            life_steal=float(profile.life_steal),
            life_steal_cap=float(profile.life_steal_cap),
        )
        for key, value in self.current_job(profile).stats.items():
            self._apply_stat(stats, key, value)
        for item in self.equipped_items(profile):
            for key, value in scaled_item_stats(item.template_id, item.stars).items():
                self._apply_stat(stats, key, value)
        stats.base_atk = max(1, int(stats.base_atk))
        stats.max_hp = max(1, int(stats.max_hp))
        stats.defense = self._capped_defense(stats.defense)
        stats.defense_ignore = max(0.0, min(0.4, float(stats.defense_ignore)))
        stats.skill_dmg_supplement = max(0.0, min(200.0, float(stats.skill_dmg_supplement)))
        stats.life_steal_cap = max(0.0, float(stats.life_steal_cap))
        return stats

    def _enemy_stats(self, raw_stats: dict[str, float]) -> CombatStats:
        stats = CombatStats(
            base_atk=int(raw_stats.get("base_atk", 1)),
            max_hp=int(raw_stats.get("max_hp", 1)),
            hp_bonus=float(raw_stats.get("hp_bonus", 0.0)),
            atk=float(raw_stats.get("atk", 0.0)),
            defense=float(raw_stats.get("defense", 0.0)),
            defense_ignore=float(raw_stats.get("defense_ignore", 0.0)),
            garrison=float(raw_stats.get("garrison", 0.0)),
            strength=float(raw_stats.get("strength", 0.0)),
            enmity=float(raw_stats.get("enmity", 0.0)),
            damage_cut=float(raw_stats.get("damage_cut", 0.0)),
            dmg_mitigation=float(raw_stats.get("dmg_mitigation", 0.0)),
            dmg_amplification=float(raw_stats.get("dmg_amplification", 0.0)),
            dmg_supplement=float(raw_stats.get("dmg_supplement", 0.0)),
            skill_damage=float(raw_stats.get("skill_damage", 0.0)),
            skill_dmg_supplement=float(raw_stats.get("skill_dmg_supplement", 0.0)),
            critical_rate=float(raw_stats.get("critical_rate", 0.0)),
            critical_damage=float(raw_stats.get("critical_damage", 0.0)),
            double_attack_rate=float(raw_stats.get("double_attack_rate", 0.0)),
            triple_attack_rate=float(raw_stats.get("triple_attack_rate", 0.0)),
            life_steal=float(raw_stats.get("life_steal", 0.0)),
            life_steal_cap=float(raw_stats.get("life_steal_cap", 0.01)),
        )
        stats.defense = self._capped_defense(stats.defense)
        stats.defense_ignore = max(0.0, min(0.4, float(stats.defense_ignore)))
        stats.skill_dmg_supplement = max(0.0, min(200.0, float(stats.skill_dmg_supplement)))
        stats.life_steal_cap = max(0.0, float(stats.life_steal_cap))
        return stats

    def _stats_with_effects(
        self,
        base: CombatStats,
        effects: list[ActiveEffect],
        stack_effects: list[ActiveStackEffect] | None = None,
    ) -> CombatStats:
        stats = base.copy()
        effects = self._effects_with_stacks(effects, stack_effects)
        positive_mods: dict[str, float] = {}
        negative_mods: dict[str, float] = {}
        for effect in effects:
            if not self._effect_active(effect):
                continue
            for key, value in effect.mods.items():
                target = negative_mods if value < 0 else positive_mods
                target[key] = target.get(key, 0.0) + value
        stat_keys = dict.fromkeys([*positive_mods.keys(), *negative_mods.keys()])
        for key in stat_keys:
            negative_value = negative_mods.get(key, 0.0)
            if key in STACKED_DEBUFF_FLOORS:
                negative_value = max(negative_value, STACKED_DEBUFF_FLOORS[key])
            self._apply_stat(stats, key, positive_mods.get(key, 0.0) + negative_value)
        stats.base_atk = max(1, int(stats.base_atk))
        stats.max_hp = max(1, int(stats.max_hp))
        stats.defense = self._capped_defense(stats.defense)
        stats.defense_ignore = max(0.0, min(0.4, float(stats.defense_ignore)))
        stats.skill_dmg_supplement = max(0.0, min(200.0, float(stats.skill_dmg_supplement)))
        stats.life_steal_cap = max(0.0, float(stats.life_steal_cap))
        return stats

    def _effects_with_stacks(
        self,
        effects: list[ActiveEffect],
        stack_effects: list[ActiveStackEffect] | None = None,
    ) -> list[ActiveEffect]:
        if not stack_effects:
            return effects
        derived = self._stack_effect_active_effects(stack_effects)
        if not derived:
            return effects
        return [*effects, *derived]

    def _stack_effect_active_effects(self, stack_effects: list[ActiveStackEffect]) -> list[ActiveEffect]:
        active: list[ActiveEffect] = []
        for current in stack_effects:
            template = STACK_EFFECT_BY_ID.get(current.template_id)
            if template is None:
                continue
            stacks = max(0, min(template.max_stacks, int(current.stacks)))
            if stacks <= 0:
                continue
            tier = self._stack_effect_tier_for_stacks(template, stacks)
            if tier is None:
                continue
            source_id = f"stack:{template.id}"
            for effect in tier.stat_effects:
                if not effect.stat or not effect.value:
                    continue
                active.append(
                    ActiveEffect(
                        INFINITE_EFFECT_TURNS,
                        {effect.stat: effect.value},
                        source_id,
                        undispellable=True,
                        heal_cap=effect.heal_cap,
                    )
                )
            if tier.effects.has_any:
                active.append(
                    ActiveEffect(
                        INFINITE_EFFECT_TURNS,
                        {},
                        source_id,
                        tier.effects,
                        undispellable=True,
                    )
                )
        return active

    def _stack_effect_tier_for_stacks(self, template, stacks: int):
        eligible = [tier for tier in template.tiers if tier.stack <= stacks]
        if not eligible:
            return None
        return max(eligible, key=lambda tier: tier.stack)

    def _tick_effects(self, effects: list[ActiveEffect]) -> list[ActiveEffect]:
        next_effects: list[ActiveEffect] = []
        for effect in effects:
            if effect.turns == INFINITE_EFFECT_TURNS:
                next_effects.append(effect)
                continue
            if effect.turns - 1 > 0:
                next_effects.append(
                    ActiveEffect(
                        effect.turns - 1,
                        effect.mods,
                        effect.source_id,
                        effect.special,
                        effect.undispellable,
                        effect.heal_cap,
                    )
                )
        return next_effects

    def _tick_cooldowns(self, cooldowns: dict[str, int]) -> None:
        for skill_id, turns in list(cooldowns.items()):
            if turns > 0:
                cooldowns[skill_id] = turns - 1

    def _has_active_effect(self, effects: list[ActiveEffect], source_id: str) -> bool:
        return any(effect.source_id == source_id and self._effect_active(effect) for effect in effects)

    def _remove_effects_by_source(self, effect_lists: list[list[ActiveEffect]], source_id: str) -> None:
        seen: set[int] = set()
        for effects in effect_lists:
            identity = id(effects)
            if identity in seen:
                continue
            seen.add(identity)
            effects[:] = [effect for effect in effects if effect.source_id != source_id]

    def _apply_stat(self, stats: CombatStats, key: str, value: float) -> None:
        if not hasattr(stats, key):
            return
        setattr(stats, key, getattr(stats, key) + value)

    def _effect_active(self, effect: ActiveEffect) -> bool:
        return effect.turns == INFINITE_EFFECT_TURNS or effect.turns > 0

    def _capped_defense(self, value: float) -> float:
        return min(DEFENSE_CAP, float(value))

    def _level_steps(self, level: int) -> int:
        return max(0, int(level) - 1)

    def _level_base_atk(self, level: int) -> int:
        return max(1, int(float(PLAYER_START.get("base_atk", 12)) + self._level_steps(level) * LEVEL_UP_BASE_ATK))

    def _level_max_hp(self, level: int) -> int:
        return max(1, int(float(PLAYER_START.get("max_hp", 120)) + self._level_steps(level) * LEVEL_UP_MAX_HP))

    def _level_defense(self, level: int) -> float:
        return round(
            self._capped_defense(float(PLAYER_START.get("defense", 0.08)) + self._level_steps(level) * LEVEL_UP_DEFENSE),
            4,
        )

    def _effect_turns(self, duration: int) -> int:
        if duration < 0:
            return INFINITE_EFFECT_TURNS
        return max(1, duration)

    def _append_active_effect(self, target: list[ActiveEffect], effect: ActiveEffect) -> None:
        if self._is_debuff_effect(effect) and self._consume_guard(target, "veil"):
            return
        target.append(effect)

    def _consume_guard(self, effects: list[ActiveEffect], guard_field: str) -> bool:
        for index in range(len(effects) - 1, -1, -1):
            effect = effects[index]
            if not self._effect_active(effect):
                continue
            guards = getattr(effect.special, guard_field)
            if not guards:
                continue
            guard = guards[-1]
            if guard.count <= 0:
                return True
            next_count = guard.count - 1
            if next_count <= 0:
                effects.pop(index)
            else:
                next_guard = replace(guard, count=next_count)
                next_special = replace(effect.special, **{guard_field: [next_guard]})
                effects[index] = ActiveEffect(
                    effect.turns,
                    dict(effect.mods),
                    effect.source_id,
                    next_special,
                    effect.undispellable,
                    effect.heal_cap,
                )
            return True
        return False

    def _append_effects(
        self,
        target: list[ActiveEffect],
        *,
        source_id: str,
        special: CombatSpecialEffects | None = None,
        undispellable: bool = False,
        all_targets: list[list[ActiveEffect]] | None = None,
    ) -> None:
        if special is None or not special.has_any:
            return
        def effect_targets(effect_target: str) -> list[list[ActiveEffect]]:
            return all_targets if effect_target == "allies" and all_targets else [target]

        if special.flurry is not None:
            for effect_target in effect_targets(special.flurry.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(special.flurry.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(flurry=special.flurry),
                        special.flurry.undispellable,
                    )
                )
        if special.double_strike is not None:
            for effect_target in effect_targets(special.double_strike.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(special.double_strike.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(double_strike=special.double_strike),
                        special.double_strike.undispellable,
                    )
                )
        for bonus in special.bonus_damage:
            for effect_target in effect_targets(bonus.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(bonus.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(bonus_damage=[bonus]),
                        bonus.undispellable,
                    )
                )
        for reinforce in special.critical_reinforce:
            for effect_target in effect_targets(reinforce.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(reinforce.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(critical_reinforce=[reinforce]),
                        reinforce.undispellable,
                    )
                )
        for final_effect in special.final_damage:
            for effect_target in effect_targets(final_effect.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(final_effect.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(final_damage=[final_effect]),
                        final_effect.undispellable,
                    )
                )
        for post_attack in special.post_attack_ability_damage:
            for effect_target in effect_targets(post_attack.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(post_attack.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(post_attack_ability_damage=[post_attack]),
                        post_attack.undispellable,
                    )
                )
        for guard in special.dispel_guard:
            for effect_target in effect_targets(guard.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(guard.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(dispel_guard=[guard]),
                        guard.undispellable,
                    )
                )
        for veil in special.veil:
            for effect_target in effect_targets(veil.target):
                self._append_active_effect(
                    effect_target,
                    ActiveEffect(
                        self._effect_turns(veil.duration),
                        {},
                        source_id,
                        CombatSpecialEffects(veil=[veil]),
                        veil.undispellable,
                    )
                )

    def _append_stat_effects(
        self,
        target: list[ActiveEffect],
        *,
        source_id: str,
        effects: list[StatEffect],
    ) -> None:
        for effect in effects:
            self._append_stat_effect(target, source_id, effect)

    def _append_targeted_stat_effects(
        self,
        target: list[ActiveEffect],
        *,
        source_id: str,
        effects: list[StatEffect],
        all_targets: list[list[ActiveEffect]] | None = None,
    ) -> None:
        for effect in effects:
            targets = all_targets if effect.target == "allies" and all_targets else [target]
            for effect_target in targets:
                self._append_stat_effect(effect_target, source_id, effect)

    def _append_stat_effect(
        self,
        target: list[ActiveEffect],
        source_id: str,
        effect: StatEffect,
    ) -> None:
        if not effect.stat or not effect.value:
            return
        self._append_active_effect(
            target,
            ActiveEffect(
                self._effect_turns(effect.duration),
                {effect.stat: effect.value},
                source_id,
                undispellable=effect.undispellable,
                heal_cap=effect.heal_cap,
            )
        )

    def _permanent_effects(self, profile: PlayerProfile) -> list[ActiveEffect]:
        effects: list[ActiveEffect] = []
        self._append_permanent_effects(profile, effects)
        return effects

    def _append_permanent_effects(
        self,
        profile: PlayerProfile,
        target: list[ActiveEffect],
        *,
        all_targets: list[list[ActiveEffect]] | None = None,
    ) -> None:
        job = self.current_job(profile)
        if job.id:
            self._append_targeted_stat_effects(
                target,
                source_id=f"job:{job.id}",
                effects=job.stat_effects,
                all_targets=all_targets,
            )
            if job.effects.has_any:
                self._append_effects(
                    target,
                    source_id=f"job:{job.id}",
                    special=job.effects,
                    undispellable=job.undispellable,
                    all_targets=all_targets,
                )
        for item in self.equipped_items(profile):
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            self._append_targeted_stat_effects(
                target,
                source_id=f"item:{template.id}",
                effects=template.stat_effects,
                all_targets=all_targets,
            )
            if not template.effects.has_any:
                continue
            self._append_effects(
                target,
                source_id=f"item:{template.id}",
                special=template.effects,
                undispellable=template.undispellable,
                all_targets=all_targets,
            )

    def _apply_effect_actions(
        self,
        actions: list[EffectAction],
        *,
        self_effects: list[ActiveEffect],
        enemy_effects: list[ActiveEffect],
        ally_effects: list[list[ActiveEffect]] | None = None,
        opponent_effects: list[list[ActiveEffect]] | None = None,
        self_stacks: list[ActiveStackEffect] | None = None,
        enemy_stacks: list[ActiveStackEffect] | None = None,
        ally_stacks: list[list[ActiveStackEffect]] | None = None,
        opponent_stacks: list[list[ActiveStackEffect]] | None = None,
    ) -> tuple[int, int]:
        dispels = 0
        clear_alls = 0
        for action in actions:
            if not self._effect_action_conditions_match(
                action,
                self_stacks=self_stacks,
                enemy_stacks=enemy_stacks,
                ally_stacks=ally_stacks,
                opponent_stacks=opponent_stacks,
            ):
                continue
            if action.action in STACK_EFFECT_ACTIONS:
                stack_targets = self._stack_action_targets(
                    action.target,
                    self_stacks=self_stacks,
                    enemy_stacks=enemy_stacks,
                    ally_stacks=ally_stacks,
                    opponent_stacks=opponent_stacks,
                )
                for target in stack_targets:
                    self._apply_stack_action(target, action)
                continue
            targets = self._effect_action_targets(
                action.target,
                self_effects=self_effects,
                enemy_effects=enemy_effects,
                ally_effects=ally_effects,
                opponent_effects=opponent_effects,
            )
            stack_targets = self._stack_action_targets(
                action.target,
                self_stacks=self_stacks,
                enemy_stacks=enemy_stacks,
                ally_stacks=ally_stacks,
                opponent_stacks=opponent_stacks,
            )
            for target_index, target in enumerate(targets):
                stack_target = stack_targets[target_index] if target_index < len(stack_targets) else []
                for _ in range(action.count):
                    if action.action == "dispel":
                        if not self._consume_guard(target, "dispel_guard") and not self._has_stack_guard(stack_target, "dispel_guard"):
                            self._remove_latest_effect(target, want_buff=True)
                        dispels += 1
                    elif action.action == "clear_all":
                        self._remove_latest_effect(target, want_buff=False)
                        clear_alls += 1
        return dispels, clear_alls

    def _effect_action_conditions_match(
        self,
        action: EffectAction,
        *,
        self_stacks: list[ActiveStackEffect] | None,
        enemy_stacks: list[ActiveStackEffect] | None,
        ally_stacks: list[list[ActiveStackEffect]] | None,
        opponent_stacks: list[list[ActiveStackEffect]] | None,
    ) -> bool:
        conditions = getattr(action, "conditions", None) or []
        if not conditions:
            return True
        for condition in conditions:
            stack_targets = self._stack_condition_targets(
                condition.target,
                self_stacks=self_stacks,
                enemy_stacks=enemy_stacks,
                ally_stacks=ally_stacks,
                opponent_stacks=opponent_stacks,
            )
            if not stack_targets:
                return False
            if not any(self._stack_condition_matches(target, condition) for target in stack_targets):
                return False
        return True

    def _stack_condition_targets(
        self,
        target: str,
        *,
        self_stacks: list[ActiveStackEffect] | None,
        enemy_stacks: list[ActiveStackEffect] | None,
        ally_stacks: list[list[ActiveStackEffect]] | None,
        opponent_stacks: list[list[ActiveStackEffect]] | None,
    ) -> list[list[ActiveStackEffect]]:
        normalized = {
            "boss": "self",
            "player": "enemy",
        }.get(target, target)
        return self._stack_action_targets(
            normalized,
            self_stacks=self_stacks,
            enemy_stacks=enemy_stacks,
            ally_stacks=ally_stacks,
            opponent_stacks=opponent_stacks,
        )

    def _stack_condition_matches(self, stacks: list[ActiveStackEffect], condition) -> bool:
        current = 0
        for stack in stacks:
            if stack.template_id == condition.stack_effect_id:
                current = max(0, stack.stacks)
                break
        if current < condition.min_stacks:
            return False
        return condition.max_stacks < 0 or current <= condition.max_stacks

    def _has_stack_guard(self, stacks: list[ActiveStackEffect], guard_field: str) -> bool:
        for effect in self._stack_effect_active_effects(stacks):
            if not self._effect_active(effect):
                continue
            guards = getattr(effect.special, guard_field)
            if any(guard.count <= 0 for guard in guards):
                return True
        return False

    def _stack_action_targets(
        self,
        target: str,
        *,
        self_stacks: list[ActiveStackEffect] | None,
        enemy_stacks: list[ActiveStackEffect] | None,
        ally_stacks: list[list[ActiveStackEffect]] | None,
        opponent_stacks: list[list[ActiveStackEffect]] | None,
    ) -> list[list[ActiveStackEffect]]:
        self_stacks = self_stacks if self_stacks is not None else []
        enemy_stacks = enemy_stacks if enemy_stacks is not None else []
        if target in {"self", "me"}:
            return [self_stacks]
        if target in {"ally", "allies"}:
            return list(ally_stacks or [self_stacks])
        if target in {"opponent", "opponents", "enemies"}:
            return list(opponent_stacks or [enemy_stacks])
        return [enemy_stacks]

    def _apply_stack_action(self, stacks: list[ActiveStackEffect], action: EffectAction) -> None:
        template = STACK_EFFECT_BY_ID.get(action.stack_effect_id)
        if template is None:
            return
        operation = action.action.removeprefix("stack_")
        value = max(1, int(action.value or action.count or 1))
        current = next((effect for effect in stacks if effect.template_id == template.id), None)
        current_stacks = max(0, int(current.stacks)) if current is not None else 0
        if operation == "increase":
            next_stacks = current_stacks + value
        elif operation == "decrease":
            next_stacks = current_stacks - value
        elif operation == "set":
            next_stacks = value
        elif operation == "max":
            next_stacks = template.max_stacks
        elif operation == "remove":
            next_stacks = 0
        else:
            return
        next_stacks = max(0, min(template.max_stacks, next_stacks))
        if current is None:
            if next_stacks > 0:
                stacks.append(ActiveStackEffect(template.id, next_stacks))
            return
        if next_stacks <= 0:
            if current.persistent:
                current.stacks = 0
                return
            stacks[:] = [effect for effect in stacks if effect.template_id != template.id]
            return
        current.stacks = next_stacks

    def _apply_stack_conditions(
        self,
        stacks: list[ActiveStackEffect],
        *,
        objective: str,
        amount: int = 0,
        actor_is_holder: bool = True,
        hit_damages: list[int] | None = None,
    ) -> None:
        if not stacks:
            return
        for current in list(stacks):
            template = STACK_EFFECT_BY_ID.get(current.template_id)
            if template is None:
                continue
            for index, condition in enumerate(template.conditions):
                if condition.objective != objective:
                    continue
                if objective not in WARNING_STACK_EVENTS:
                    wants_holder = condition.target in {"self", "me", "holder"}
                    if wants_holder != actor_is_holder:
                        continue
                progress = max(1, amount) if objective in WARNING_STACK_EVENTS else max(0, amount)
                if objective == "hits":
                    damages = hit_damages or []
                    progress = sum(1 for damage in damages if damage >= condition.min_damage)
                if progress <= 0:
                    continue
                required = max(1, condition.required)
                if objective in WARNING_STACK_EVENTS:
                    times = max(1, progress // required)
                else:
                    progress_key = self._stack_condition_progress_key(index, condition)
                    total_progress = max(0, current.condition_progress.get(progress_key, 0)) + progress
                    if total_progress < required:
                        current.condition_progress[progress_key] = total_progress
                        continue
                    times = max(1, total_progress // required)
                    current.condition_progress[progress_key] = total_progress % required
                for _ in range(times):
                    self._apply_stack_action(
                        stacks,
                        EffectAction(
                            action=f"stack_{condition.operation}",
                            target="self",
                            stack_effect_id=template.id,
                            value=condition.value,
                        ),
                    )

    def _stack_condition_progress_key(self, index: int, condition) -> str:
        return ":".join(
            (
                str(index),
                condition.objective,
                condition.target,
                condition.operation,
                str(max(1, condition.required)),
                str(max(0, condition.min_damage)),
            )
        )

    def _effect_action_targets(
        self,
        target: str,
        *,
        self_effects: list[ActiveEffect],
        enemy_effects: list[ActiveEffect],
        ally_effects: list[list[ActiveEffect]] | None,
        opponent_effects: list[list[ActiveEffect]] | None,
    ) -> list[list[ActiveEffect]]:
        if target in {"self", "me"}:
            return [self_effects]
        if target in {"ally", "allies"}:
            return list(ally_effects or [self_effects])
        if target in {"opponent", "opponents", "enemies"}:
            return list(opponent_effects or [enemy_effects])
        return [enemy_effects]

    def _effect_source_label(self, source_id: str) -> str:
        if source_id.startswith("item:"):
            template_id = source_id.removeprefix("item:")
            return ITEM_BY_ID.get(template_id).name if template_id in ITEM_BY_ID else template_id
        if source_id.startswith("job:"):
            job_id = source_id.removeprefix("job:")
            return JOB_BY_ID.get(job_id).name if job_id in JOB_BY_ID else job_id
        if source_id.startswith("boss:"):
            return source_id.removeprefix("boss:") or "보스"
        skill = SKILL_BY_ID.get(source_id)
        if skill is not None:
            return skill.name
        return source_id or "효과"

    def _damage_values_text(self, values: list[int], *, limit: int = 600) -> str:
        if not values:
            return "없음"
        parts: list[str] = []
        for index, value in enumerate(values):
            next_parts = [*parts, str(value)]
            next_text = ", ".join(next_parts)
            if len(next_text) > limit:
                parts.append(f"... 외 {len(values) - index}타")
                break
            parts.append(str(value))
        return ", ".join(parts)

    def _damage_piece_text(self, base_damage: int, bonus_values: list[int]) -> str:
        if not bonus_values:
            return str(base_damage)
        return f"{base_damage}(+{'+'.join(str(value) for value in bonus_values)})"

    def _basic_attack_detail_label(
        self,
        action_index: int,
        actions: int,
        repeat_index: int,
        repeats: int,
    ) -> str:
        repeat_label = "평타" if repeats == 1 else f"평타 {repeat_index}"
        if actions == 1:
            return repeat_label
        return f"행동 {action_index} {repeat_label}"

    def _post_attack_detail_label(self, source_id: str, action_index: int, actions: int) -> str:
        label = f"추가어빌({self._effect_source_label(source_id)})"
        if actions == 1:
            return label
        return f"행동 {action_index} {label}"

    def _remove_latest_effect(self, effects: list[ActiveEffect], *, want_buff: bool) -> bool:
        for index in range(len(effects) - 1, -1, -1):
            effect = effects[index]
            if effect.undispellable or not self._effect_active(effect):
                continue
            if want_buff and not self._is_buff_effect(effect):
                continue
            if not want_buff and not self._is_debuff_effect(effect):
                continue
            effects.pop(index)
            return True
        return False

    def _is_buff_effect(self, effect: ActiveEffect) -> bool:
        values = [*effect.mods.values(), *self._special_effect_ratios(effect)]
        values = [value for value in values if value]
        return bool(values) and all(value >= 0 for value in values)

    def _is_debuff_effect(self, effect: ActiveEffect) -> bool:
        values = [*effect.mods.values(), *self._special_effect_ratios(effect)]
        values = [value for value in values if value]
        return bool(values) and all(value <= 0 for value in values)

    def _attack_specials(
        self,
        effects: list[ActiveEffect],
    ) -> tuple[int, int, list[BonusDamageEffect], list[tuple[str, PostAttackAbilityDamageEffect]]]:
        flurry_count = 1
        action_count = 1
        bonus_damage: list[BonusDamageEffect] = []
        item_bonus_ratio = 0.0
        item_bonus_template: BonusDamageEffect | None = None
        post_attack_ability_damage: list[tuple[str, PostAttackAbilityDamageEffect]] = []
        for effect in effects:
            if not self._effect_active(effect):
                continue
            if effect.special.flurry is not None:
                flurry_count = max(flurry_count, effect.special.flurry.count)
            if effect.special.double_strike is not None:
                action_count = max(action_count, effect.special.double_strike.count)
            for bonus in effect.special.bonus_damage:
                if effect.source_id.startswith("item:"):
                    item_bonus_ratio += bonus.ratio
                    item_bonus_template = item_bonus_template or bonus
                else:
                    bonus_damage.append(bonus)
            for post_attack in effect.special.post_attack_ability_damage:
                post_attack_ability_damage.append((effect.source_id, post_attack))
        if item_bonus_template is not None and item_bonus_ratio > 0:
            bonus_damage.append(replace(item_bonus_template, ratio=item_bonus_ratio))
        return flurry_count, action_count, bonus_damage, post_attack_ability_damage

    def _special_effect_ratios(self, effect: ActiveEffect) -> list[float]:
        if not self._effect_active(effect):
            return []
        ratios = [final_effect.ratio for final_effect in effect.special.final_damage]
        ratios.extend(bonus.ratio for bonus in effect.special.bonus_damage)
        ratios.extend(reinforce.ratio for reinforce in effect.special.critical_reinforce)
        ratios.extend(post_attack.ratio for post_attack in effect.special.post_attack_ability_damage)
        if effect.special.flurry is not None:
            ratios.append(1.0)
        if effect.special.double_strike is not None:
            ratios.append(1.0)
        if effect.special.dispel_guard:
            ratios.append(1.0)
        if effect.special.veil:
            ratios.append(1.0)
        return ratios

    def _final_damage_multiplier(self, effects: list[ActiveEffect] | None) -> float:
        if not effects:
            return 1.0
        multiplier = 1.0
        for effect in effects:
            if not self._effect_active(effect):
                continue
            for final_effect in effect.special.final_damage:
                multiplier *= max(0.0, 1 + final_effect.ratio)
        return multiplier

    def _critical_reinforce_multiplier(self, stats: CombatStats, effects: list[ActiveEffect] | None) -> float:
        overflow = max(0.0, stats.critical_rate - 1.0)
        if overflow <= 0 or not effects:
            return 1.0
        multiplier = 1.0
        for effect in effects:
            if not self._effect_active(effect):
                continue
            for reinforce in effect.special.critical_reinforce:
                multiplier *= 1 + overflow * reinforce.ratio
        return multiplier

    def _roll_attack_repeats(self, stats: CombatStats) -> int:
        triple_rate = max(0.0, min(1.0, stats.triple_attack_rate))
        double_rate = max(0.0, min(1.0, stats.double_attack_rate))
        if triple_rate > 0 and self.rng.random() < triple_rate:
            return 3
        if double_rate > 0 and self.rng.random() < double_rate:
            return 2
        return 1

    def _expected_attack_repeats(self, stats: CombatStats) -> float:
        triple_rate = max(0.0, min(1.0, stats.triple_attack_rate))
        double_rate = max(0.0, min(1.0, stats.double_attack_rate))
        return 3 * triple_rate + (1 - triple_rate) * (2 * double_rate + (1 - double_rate))

    def _basic_attack(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        attacker_effects: list[ActiveEffect],
        multiplier: float = 1.0,
    ) -> AttackOutcome:
        flurry_count, actions, bonus_effects, post_attack_effects = self._attack_specials(attacker_effects)
        final_damage_multiplier = self._final_damage_multiplier(attacker_effects)
        outcome = AttackOutcome(actions=actions, flurry_count=flurry_count)
        for action_index in range(1, actions + 1):
            action_damage = 0
            repeats = self._roll_attack_repeats(attacker)
            critical = self._roll_critical(attacker)
            if critical:
                outcome.critical_hits += 1
            if repeats == 3:
                outcome.triple_attacks += 1
            elif repeats == 2:
                outcome.double_attacks += 1
            for repeat_index in range(1, repeats + 1):
                base_damage = self._actual_damage(
                    attacker,
                    attacker_hp,
                    defender,
                    defender_hp,
                    multiplier,
                    attacker_effects,
                    include_supplement=False,
                    include_final_damage=False,
                    include_flat_mitigation=False,
                    forced_critical=critical,
                )
                supplement = self._supplement_damage(attacker)
                branch_entries: list[str] = []
                for hit_damage in self._split_damage(base_damage, flurry_count):
                    final_hit_damage = self._flat_mitigated_damage(
                        (hit_damage + supplement) * final_damage_multiplier,
                        defender,
                    )
                    outcome.damage += final_hit_damage
                    action_damage += final_hit_damage
                    outcome.hits += 1
                    outcome.hit_damages.append(final_hit_damage)
                    bonus_values: list[int] = []
                    if final_hit_damage <= 0:
                        branch_entries.append(self._damage_piece_text(final_hit_damage, bonus_values))
                        continue
                    for bonus in bonus_effects:
                        raw_bonus_damage = max(1, int(round(hit_damage * bonus.ratio))) + supplement
                        bonus_damage = self._flat_mitigated_damage(
                            raw_bonus_damage * final_damage_multiplier,
                            defender,
                        )
                        outcome.damage += bonus_damage
                        action_damage += bonus_damage
                        outcome.hits += 1
                        outcome.hit_damages.append(bonus_damage)
                        outcome.bonus_hits += 1
                        bonus_values.append(bonus_damage)
                    branch_entries.append(self._damage_piece_text(final_hit_damage, bonus_values))
                outcome.detail_lines.append(
                    f"{self._basic_attack_detail_label(action_index, actions, repeat_index, repeats)}: "
                    f"{', '.join(branch_entries)}"
                )
            for source_id, post_attack in post_attack_effects:
                ability_values: list[int] = []
                for _ in range(post_attack.count):
                    ability_damage = self._actual_damage(
                        attacker,
                        attacker_hp,
                        defender,
                        defender_hp,
                        post_attack.ratio,
                        attacker_effects,
                        include_skill_supplement=True,
                    )
                    outcome.damage += ability_damage
                    action_damage += ability_damage
                    outcome.ability_damage += ability_damage
                    outcome.hits += 1
                    outcome.ability_hits += 1
                    outcome.hit_damages.append(ability_damage)
                    ability_values.append(ability_damage)
                if ability_values:
                    outcome.detail_lines.append(
                        f"{self._post_attack_detail_label(source_id, action_index, actions)}: "
                        f"{self._damage_values_text(ability_values)}"
                    )
            if action_damage > 0:
                outcome.life_steal_segments.append(action_damage)
        return outcome

    def _estimated_basic_attack_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        attacker_effects: list[ActiveEffect],
        multiplier: float = 1.0,
    ) -> float:
        flurry_count, actions, bonus_effects, post_attack_effects = self._attack_specials(attacker_effects)
        final_damage_multiplier = self._final_damage_multiplier(attacker_effects)
        base_damage = self._estimated_damage(
            attacker,
            attacker_hp,
            defender,
            defender_hp,
            multiplier,
            attacker_effects,
            include_supplement=False,
            include_final_damage=False,
            include_flat_mitigation=False,
        )
        supplement = self._supplement_damage(attacker)
        base_hit_damage = base_damage / max(1, flurry_count)
        per_branch = self._estimated_flat_mitigated_damage(
            (base_hit_damage + supplement) * final_damage_multiplier,
            defender,
        )
        for bonus in bonus_effects:
            raw_bonus_damage = max(1.0, base_hit_damage * bonus.ratio) + supplement
            per_branch += self._estimated_flat_mitigated_damage(
                raw_bonus_damage * final_damage_multiplier,
                defender,
            )
        per_repeat = per_branch * flurry_count
        post_attack_damage = sum(
            self._estimated_damage(
                attacker,
                attacker_hp,
                defender,
                defender_hp,
                post_attack.ratio,
                attacker_effects,
                include_skill_supplement=True,
            ) * post_attack.count
            for _source_id, post_attack in post_attack_effects
        )
        return (per_repeat * self._expected_attack_repeats(attacker) + post_attack_damage) * actions

    def _split_damage(self, total: int, count: int) -> list[int]:
        count = max(1, count)
        base = max(0, total) // count
        remainder = max(0, total) % count
        return [
            base + (1 if index < remainder else 0)
            for index in range(count)
        ]

    def _attack_log_text(self, attack: AttackOutcome) -> str:
        parts = [f"{attack.damage} 피해"]
        if attack.hits > 1:
            parts.append(f"{attack.hits}타")
        if attack.actions > 1:
            parts.append(f"재행동 {attack.actions}회")
        if attack.triple_attacks:
            parts.append(f"트리플 {attack.triple_attacks}")
        if attack.double_attacks:
            parts.append(f"더블 {attack.double_attacks}")
        if attack.flurry_count > 1:
            parts.append(f"난격 {attack.flurry_count}")
        if attack.bonus_hits:
            parts.append(f"추격 {attack.bonus_hits}")
        if attack.ability_hits:
            parts.append(f"추가 어빌 {attack.ability_hits}")
        if attack.critical_hits:
            parts.append(f"크리 {attack.critical_hits}")
        if attack.heal:
            parts.append(f"{attack.heal} 흡수")
        return " · ".join(parts)

    def _outgoing_damage(self, stats: CombatStats, current_hp: int) -> float:
        ratio = self._hp_ratio(current_hp, stats.final_hp)
        return (
            stats.base_atk
            * (1 + stats.atk)
            * (1 + stats.strength * ratio)
            * (1 + stats.enmity * (1 - ratio))
            * (1 + stats.dmg_amplification)
        )

    def _skill_outgoing_damage(self, stats: CombatStats) -> float:
        return stats.base_atk * max(0.0, 1 + stats.skill_damage)

    def _supplement_damage(self, stats: CombatStats) -> int:
        amount = max(0.0, float(stats.dmg_supplement))
        amplification = max(0.0, 1 + float(stats.dmg_amplification))
        return max(0, int(round(amount * amplification)))

    def _skill_supplement_damage(self, stats: CombatStats) -> int:
        amount = max(0.0, min(200.0, float(stats.skill_dmg_supplement)))
        amplification = max(0.0, 1 + float(stats.dmg_amplification))
        return max(0, int(round(amount * amplification)))

    def _life_steal_heal(
        self,
        stats: CombatStats,
        effects: list[ActiveEffect],
        dealt_damage: int,
        target_max_hp: int,
    ) -> int:
        if dealt_damage <= 0 or stats.life_steal <= 0:
            return 0
        effect_ratio_total = 0.0
        heal = 0
        for effect in effects:
            if not self._effect_active(effect):
                continue
            ratio = max(0.0, float(effect.mods.get("life_steal", 0.0)))
            if ratio <= 0:
                continue
            effect_ratio_total += ratio
            heal += self._apply_heal_cap(int(round(dealt_damage * ratio)), effect.heal_cap, target_max_hp)
        base_ratio = max(0.0, stats.life_steal - effect_ratio_total)
        if base_ratio > 0:
            heal += int(round(dealt_damage * base_ratio))
        return self._apply_life_steal_cap(max(0, heal), stats, target_max_hp)

    def _life_steal_heal_segments(
        self,
        stats: CombatStats,
        effects: list[ActiveEffect],
        damage_segments: list[int],
        target_max_hp: int,
    ) -> int:
        return sum(
            self._life_steal_heal(stats, effects, damage, target_max_hp)
            for damage in damage_segments
            if damage > 0
        )

    def _clamped_damage_segments(self, damage_segments: list[int], target_hp: int) -> list[int]:
        remaining = max(0, int(target_hp))
        clamped: list[int] = []
        for damage in damage_segments:
            if remaining <= 0:
                break
            dealt = min(remaining, max(0, int(damage)))
            if dealt > 0:
                clamped.append(dealt)
                remaining -= dealt
        return clamped

    def _apply_heal_cap(self, heal: int, cap: HealCap | None, target_max_hp: int) -> int:
        heal = max(0, int(heal))
        if heal <= 0 or cap is None or not cap.has_cap:
            return heal
        if cap.mode == "flat":
            limit = int(cap.value)
        elif cap.mode == "max_hp_ratio":
            limit = int(max(1, target_max_hp) * cap.value)
        else:
            return heal
        return min(heal, max(0, limit))

    def _apply_life_steal_cap(self, heal: int, stats: CombatStats, target_max_hp: int) -> int:
        heal = max(0, int(heal))
        if heal <= 0:
            return 0
        limit = int(max(1, target_max_hp) * max(0.0, float(stats.life_steal_cap)))
        return min(heal, max(0, limit))

    def _estimated_flat_mitigated_damage(self, damage: float, defender: CombatStats) -> float:
        return max(1.0, damage - float(defender.dmg_mitigation))

    def _flat_mitigated_damage(self, damage: float, defender: CombatStats) -> int:
        return max(1, int(round(damage - float(defender.dmg_mitigation))))

    def _heal_cap_summary(self, cap: HealCap | None) -> str:
        if cap is None or not cap.has_cap:
            return ""
        if cap.mode == "flat":
            return f"{int(cap.value)}"
        if cap.mode == "max_hp_ratio":
            return f"최대 HP {cap.value * 100:.1f}%"
        return ""

    def _defense_factor(self, stats: CombatStats, current_hp: int, defense_ignore: float = 0.0) -> float:
        ratio = self._hp_ratio(current_hp, stats.final_hp)
        ignored = max(0.0, min(0.4, float(defense_ignore)))
        effective_defense = self._capped_defense(stats.defense + stats.garrison * (1 - ratio))
        return max(0.01, 1 + effective_defense - ignored)

    def _estimated_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
        attacker_effects: list[ActiveEffect] | None = None,
        include_supplement: bool = True,
        include_skill_supplement: bool = False,
        include_final_damage: bool = True,
        include_flat_mitigation: bool = True,
    ) -> float:
        damage = self._outgoing_damage(attacker, attacker_hp) * multiplier
        mitigated = damage / self._defense_factor(defender, defender_hp, attacker.defense_ignore)
        final = max(1.0, mitigated * max(0.05, 1 - defender.damage_cut))
        critical_chance = max(0.0, min(1.0, attacker.critical_rate))
        critical_bonus = max(0.0, 0.5 + attacker.critical_damage)
        final *= 1 + critical_chance * critical_bonus
        final *= self._critical_reinforce_multiplier(attacker, attacker_effects)
        if include_supplement:
            final += self._supplement_damage(attacker)
        if include_skill_supplement:
            final += self._skill_supplement_damage(attacker)
        if include_final_damage:
            final *= self._final_damage_multiplier(attacker_effects)
        if include_flat_mitigation:
            final = self._estimated_flat_mitigated_damage(final, defender)
        return final

    def _estimated_skill_damage_hit(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
        attacker_effects: list[ActiveEffect] | None = None,
        *,
        include_supplement: bool = True,
        include_final_damage: bool = True,
        include_flat_mitigation: bool = True,
    ) -> float:
        damage = self._skill_outgoing_damage(attacker) * multiplier
        mitigated = damage / self._defense_factor(defender, defender_hp, attacker.defense_ignore)
        final = max(1.0, mitigated * max(0.05, 1 - defender.damage_cut))
        critical_chance = max(0.0, min(1.0, attacker.critical_rate))
        critical_bonus = max(0.0, 0.5 + attacker.critical_damage)
        final *= 1 + critical_chance * critical_bonus
        final *= self._critical_reinforce_multiplier(attacker, attacker_effects)
        if include_supplement:
            final += self._supplement_damage(attacker)
            final += self._skill_supplement_damage(attacker)
        if include_final_damage:
            final *= self._final_damage_multiplier(attacker_effects)
        if include_flat_mitigation:
            final = self._estimated_flat_mitigated_damage(final, defender)
        return final

    def _roll_critical(self, attacker: CombatStats) -> bool:
        return self.rng.random() < max(0.0, min(1.0, attacker.critical_rate))

    def _actual_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
        attacker_effects: list[ActiveEffect] | None = None,
        *,
        include_supplement: bool = True,
        include_skill_supplement: bool = False,
        include_final_damage: bool = True,
        include_flat_mitigation: bool = True,
        forced_critical: bool | None = None,
    ) -> int:
        damage = self._outgoing_damage(attacker, attacker_hp) * multiplier
        mitigated = damage / self._defense_factor(defender, defender_hp, attacker.defense_ignore)
        estimated = max(1.0, mitigated * max(0.05, 1 - defender.damage_cut))
        spread = 0.95 + self.rng.random() * 0.10
        critical = self._roll_critical(attacker) if forced_critical is None else forced_critical
        if critical:
            estimated *= 1.5 + max(0.0, attacker.critical_damage)
        estimated *= self._critical_reinforce_multiplier(attacker, attacker_effects)
        supplement = self._supplement_damage(attacker) if include_supplement else 0
        if include_skill_supplement:
            supplement += self._skill_supplement_damage(attacker)
        result = max(1, int(estimated * spread)) + supplement
        if include_final_damage:
            result = max(1, int(round(result * self._final_damage_multiplier(attacker_effects))))
        if include_flat_mitigation:
            result = self._flat_mitigated_damage(result, defender)
        return result

    def _actual_skill_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
        attacker_effects: list[ActiveEffect] | None = None,
        *,
        include_supplement: bool = True,
        include_final_damage: bool = True,
        include_flat_mitigation: bool = True,
        forced_critical: bool | None = None,
    ) -> int:
        damage = self._skill_outgoing_damage(attacker) * multiplier
        mitigated = damage / self._defense_factor(defender, defender_hp, attacker.defense_ignore)
        estimated = max(1.0, mitigated * max(0.05, 1 - defender.damage_cut))
        spread = 0.95 + self.rng.random() * 0.10
        critical = self._roll_critical(attacker) if forced_critical is None else forced_critical
        if critical:
            estimated *= 1.5 + max(0.0, attacker.critical_damage)
        estimated *= self._critical_reinforce_multiplier(attacker, attacker_effects)
        supplement = self._supplement_damage(attacker) if include_supplement else 0
        if include_supplement:
            supplement += self._skill_supplement_damage(attacker)
        result = max(1, int(estimated * spread)) + supplement
        if include_final_damage:
            result = max(1, int(round(result * self._final_damage_multiplier(attacker_effects))))
        if include_flat_mitigation:
            result = self._flat_mitigated_damage(result, defender)
        return result

    def _hp_ratio(self, current_hp: int, max_hp: int) -> float:
        return max(0.0, min(1.0, current_hp / max(1, max_hp)))

    def _grant_exp(self, profile: PlayerProfile, exp: int) -> int:
        profile.exp += max(0, int(exp))
        levels = 0
        while profile.exp >= next_level_exp(profile.level):
            profile.level += 1
            profile.base_atk = self._level_base_atk(profile.level)
            profile.max_hp = self._level_max_hp(profile.level)
            profile.defense = self._level_defense(profile.level)
            levels += 1
        return levels

    def _choose_enemy(self, dungeon: DungeonTemplate) -> EnemyTemplate:
        total = sum(max(1, enemy.weight) for enemy in dungeon.enemies)
        roll = self.rng.randint(1, total)
        running = 0
        for enemy in dungeon.enemies:
            running += max(1, enemy.weight)
            if roll <= running:
                return enemy
        return dungeon.enemies[0]

    def _grant_reward(
        self,
        profile: PlayerProfile,
        base_gold: int,
        base_exp: int,
        drops: RewardTemplate | None,
        *,
        victory: bool,
    ) -> RewardReport:
        reward = RewardReport(consolation=not victory)
        reward.multiplier = self._reward_multiplier(victory)
        reward.gold = max(0, int(round(max(0, base_gold) * reward.multiplier)))
        reward.exp = max(0, int(round(max(0, base_exp) * reward.multiplier)))
        if drops is not None:
            for drop in drops.item_drops:
                item = self._roll_reward_item(profile, drop)
                if item is not None:
                    reward.dropped_items.append(item)
            if reward.dropped_items:
                reward.dropped_item = reward.dropped_items[0]
            for drop in drops.material_drops:
                if drop.id not in MATERIAL_BY_ID or self.rng.random() > drop.chance:
                    continue
                amount = self.rng.randint(drop.min, drop.max)
                if amount <= 0:
                    continue
                profile.materials[drop.id] = profile.materials.get(drop.id, 0) + amount
                reward.materials[drop.id] = reward.materials.get(drop.id, 0) + amount
        self._apply_auto_sell(profile, reward)
        reward.levels_gained = self._grant_exp(profile, reward.exp)
        profile.gold += reward.gold
        return reward

    def _reward_multiplier(self, victory: bool) -> float:
        if not victory:
            return max(0.0, REWARD_LOSS_MULTIPLIER)
        low = min(REWARD_WIN_MULTIPLIER_MIN, REWARD_WIN_MULTIPLIER_MAX)
        high = max(REWARD_WIN_MULTIPLIER_MIN, REWARD_WIN_MULTIPLIER_MAX)
        if high <= low:
            return max(0.0, low)
        return max(0.0, self.rng.uniform(low, high))

    def _choose_gacha_entry(self, entries: list[GachaEntry]) -> GachaEntry:
        total = sum(max(0.0, entry.chance) for entry in entries)
        if total <= 0:
            return entries[0]
        roll = self.rng.uniform(0.0, total)
        running = 0.0
        for entry in entries:
            running += max(0.0, entry.chance)
            if roll <= running:
                return entry
        return entries[-1]

    def _gacha_candidates(self, entry: GachaEntry) -> list[str]:
        if entry.type == "item":
            return [
                item_id
                for item_id in entry.item_ids
                if item_id in ITEM_BY_ID and not ITEM_BY_ID[item_id].excluded_from_gacha
            ]
        if entry.type == "item_rarity":
            return [
                item.id
                for item in ITEMS_BY_RARITY.get(entry.rarity, [])
                if not item.excluded_from_gacha
            ]
        if entry.type == "material":
            return [material_id for material_id in entry.material_ids if material_id in MATERIAL_BY_ID]
        if entry.type == "material_rarity":
            return [material.id for material in MATERIALS_BY_RARITY.get(entry.rarity, [])]
        return []

    def _grant_gacha_entry(self, profile: PlayerProfile, entry: GachaEntry) -> GachaGrant | None:
        candidates = self._gacha_candidates(entry)
        if not candidates:
            return None
        selected_id = self.rng.choice(candidates)
        grant = GachaGrant()
        if entry.type in {"item", "item_rarity"}:
            amount = entry.item_amounts.get(selected_id, 1) if entry.type == "item" else 1
            for _ in range(max(1, amount)):
                item = self._grant_item(profile, selected_id, entry.stars)
                if item is not None:
                    grant.items.append(item)
            return grant
        amount = entry.material_amounts.get(selected_id, 0)
        if amount <= 0:
            amount = self.rng.randint(entry.min, entry.max)
        profile.materials[selected_id] = profile.materials.get(selected_id, 0) + amount
        grant.materials[selected_id] = amount
        return grant

    def _roll_reward_item(self, profile: PlayerProfile, drop: RewardItemDrop) -> ItemInstance | None:
        if self.rng.random() > drop.chance:
            return None
        if drop.template_id:
            return self._grant_item(profile, drop.template_id, drop.stars)
        if drop.rarity:
            items = ITEMS_BY_RARITY.get(drop.rarity, [])
            if not items:
                return None
            template = self.rng.choice(items)
            return self._grant_item(profile, template.id, drop.stars)
        return None

    def _grant_item(self, profile: PlayerProfile, template_id: str, stars: int = 0) -> ItemInstance | None:
        if template_id not in ITEM_BY_ID:
            return None
        item = ItemInstance(profile.next_item_uid, template_id, stars=max(0, int(stars)))
        profile.next_item_uid += 1
        profile.inventory.append(item)
        return item

    def _apply_auto_sell(self, profile: PlayerProfile, reward: RewardReport) -> None:
        kept_items, sold_items, sold_gold = self._auto_sell_items(profile, reward.dropped_items)
        if not sold_items:
            return
        reward.dropped_items = kept_items
        reward.dropped_item = kept_items[0] if kept_items else None
        reward.auto_sold_items.extend(sold_items)
        reward.auto_sold_item = sold_items[0]
        reward.auto_sold_gold += sold_gold
        reward.gold += sold_gold

    def _auto_sell_items(
        self,
        profile: PlayerProfile,
        items: list[ItemInstance],
    ) -> tuple[list[ItemInstance], list[ItemInstance], int]:
        kept_items = []
        sold_items = []
        sold_gold = 0
        for item in items:
            if item.template_id not in ITEM_BY_ID:
                continue
            rarity = ITEM_BY_ID[item.template_id].rarity
            if rarity not in profile.auto_sell_rarities:
                kept_items.append(item)
                continue
            sold_gold += self.item_sell_price(item)
            sold_items.append(item)
        if sold_items:
            sold_uids = {item.uid for item in sold_items}
            profile.inventory = [owned for owned in profile.inventory if owned.uid not in sold_uids]
        return kept_items, sold_items, sold_gold

    def _reset_daily_if_needed(self, profile: PlayerProfile) -> None:
        today = self._today_key()
        if profile.daily_date != today:
            profile.daily_date = today
            profile.daily_explores_used = 0

    def _today_key(self) -> str:
        return datetime.now().astimezone().date().isoformat()

    def _week_key(self) -> str:
        return weekly_boss_key_for_date(datetime.now(RPG_TIMEZONE).date())

    def _find_item(self, profile: PlayerProfile, item_uid: int) -> ItemInstance | None:
        for item in profile.inventory:
            if item.uid == item_uid and item.template_id in ITEM_BY_ID:
                return item
        return None

    def _restore_target_stars(self, item: ItemInstance) -> int:
        return max(0, int(item.stars) - RESTORE_STAR_LOSS)

    def _restore_spare_candidates(self, profile: PlayerProfile, target: ItemInstance) -> list[ItemInstance]:
        candidates = [
            item for item in profile.inventory
            if item.uid != target.uid
            and item.template_id == target.template_id
            and item.template_id in ITEM_BY_ID
            and not item.destroyed
        ]
        equipped_uids = set(profile.equipped_item_uids)
        return sorted(candidates, key=lambda item: (item.uid in equipped_uids, item.stars, item.uid))

    def _find_restore_spare(
        self,
        profile: PlayerProfile,
        target: ItemInstance,
        spare_uid: int | None = None,
    ) -> ItemInstance | None:
        candidates = self._restore_spare_candidates(profile, target)
        if spare_uid is not None:
            return next((item for item in candidates if item.uid == spare_uid), None)
        return candidates[0] if candidates else None

    def _has_equipped_legendary(self, profile: PlayerProfile) -> bool:
        return any(
            ITEM_BY_ID[item.template_id].rarity == "legendary"
            for item in self.equipped_items(profile)
            if item.template_id in ITEM_BY_ID
        )

    def _cleanup_profile(self, profile: PlayerProfile) -> None:
        if profile.job_id not in JOB_BY_ID:
            profile.job_id = "novice"
        profile.exp = max(int(profile.exp), previous_level_exp(profile.level))
        profile.base_atk = self._level_base_atk(profile.level)
        profile.max_hp = self._level_max_hp(profile.level)
        profile.defense = self._level_defense(profile.level)
        profile.auto_sell_rarities = [
            rarity for rarity in profile.auto_sell_rarities
            if rarity in RARITIES
        ]
        profile.materials = {
            material_id: max(0, int(amount))
            for material_id, amount in profile.materials.items()
            if material_id in MATERIAL_BY_ID and int(amount) > 0
        }
        profile.inventory = [
            item for item in profile.inventory
            if item.uid > 0 and item.template_id in ITEM_BY_ID
        ]
        if not profile.equipment_initialized:
            profile.equipped_item_uids = [
                item.uid for item in sorted(
                    [
                        item for item in profile.inventory
                        if not item.destroyed and item.template_id in ITEM_BY_ID
                    ],
                    key=self.item_score,
                    reverse=True,
                )[:MAX_EQUIPPED_ITEMS]
            ]
            profile.equipment_initialized = True
        self._cleanup_equipped_items(profile)
        self._cleanup_equipped_skills(profile)
        profile.next_item_uid = max(
            profile.next_item_uid,
            max((item.uid for item in profile.inventory), default=0) + 1,
        )

    def _cleanup_equipped_items(self, profile: PlayerProfile) -> None:
        valid_uids = {
            item.uid for item in profile.inventory
            if item.uid > 0 and item.template_id in ITEM_BY_ID and not item.destroyed
        }
        cleaned = []
        has_legendary = False
        for uid in dict.fromkeys(profile.equipped_item_uids):
            if uid not in valid_uids:
                continue
            item = next((candidate for candidate in profile.inventory if candidate.uid == uid), None)
            if item is None:
                continue
            template = ITEM_BY_ID[item.template_id]
            if template.rarity == "legendary":
                if has_legendary:
                    continue
                has_legendary = True
            cleaned.append(uid)
            if len(cleaned) >= MAX_EQUIPPED_ITEMS:
                break
        profile.equipped_item_uids = cleaned

    def _cleanup_equipped_skills(self, profile: PlayerProfile) -> None:
        available = {skill.id for skill in self.unlocked_skills(profile)}
        profile.equipped_skill_ids = [
            skill_id for skill_id in profile.equipped_skill_ids
            if skill_id in available
        ][:MAX_EQUIPPED_SKILLS]

    def _save(self) -> None:
        self.store.save_profiles(self._profiles)

    def _trim_log(self, log: list[str]) -> list[str]:
        if len(log) <= 8:
            return log
        return log[:4] + ["..."] + log[-3:]

    def _format_stat_label(self, key: str, value: float) -> str:
        if key == "damage_cut":
            return "피격 데미지 감소" if value >= 0 else "피격 데미지 증가"
        if key == "dmg_mitigation":
            return "고정 피격 데미지 감소" if value >= 0 else "고정 피격 데미지 증가"
        label = STAT_LABELS.get(key, key)
        if value >= 0:
            return label
        for suffix in (" 증가", " 보너스"):
            if label.endswith(suffix):
                return f"{label[:-len(suffix)]} 감소"
        if label.endswith(" 감소"):
            return f"{label}량 감소"
        return f"{label} 감소"

    def _format_stat_value(self, key: str, value: float, *, signed: bool = False) -> str:
        display_value = abs(value) if value < 0 else value
        sign = "+" if signed and value >= 0 else ""
        if key == "critical_rate":
            display_value = min(display_value, 1.0)
        if key in PERCENT_STATS:
            return f"{display_value * 100:{sign}.1f}%"
        if key in INTEGER_STATS:
            return f"{round(display_value):{sign}d}"
        return f"{display_value:{sign}.1f}"
