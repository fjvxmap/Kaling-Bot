from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from random import Random

from .data import (
    BOSS_BY_ID,
    BOSSES,
    DAILY_EXPLORES,
    DUNGEON_BY_ID,
    DUNGEONS,
    INTEGER_STATS,
    ITEM_BY_ID,
    ITEMS_BY_RARITY,
    JOB_BY_ID,
    JOBS,
    MAX_ENHANCEMENT_STARS,
    MAX_EQUIPPED_ITEMS,
    PERCENT_STATS,
    RARITIES,
    RARITY_LABELS,
    SKILLS,
    STAT_LABELS,
    STAT_ORDER,
    BossPattern,
    BossTemplate,
    DungeonTemplate,
    EnemyTemplate,
    JobTemplate,
    SkillTemplate,
    enhancement_cost,
    enhancement_odds,
    next_level_exp,
    previous_level_exp,
    restore_cost,
    scaled_item_stats,
    stat_delta,
)
from .models import CombatStats, ItemInstance, PlayerProfile
from .store import RPGStore


@dataclass
class ActiveEffect:
    turns: int
    mods: dict[str, float]
    source_id: str


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
    stat_points: int = 0
    levels_gained: int = 0
    dropped_item: ItemInstance | None = None
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


@dataclass
class StatAllocationResult:
    ok: bool
    message: str
    profile: PlayerProfile
    spent: int = 0


@dataclass
class JobResult:
    ok: bool
    message: str
    profile: PlayerProfile
    job: JobTemplate | None = None


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

    def daily_remaining(self, profile: PlayerProfile) -> int:
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
        self._save()
        return JobResult(True, f"{job.name}으로 전직했습니다.", profile, job)

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

    def explore(self, user_id: int, display_name: str, dungeon_id: str) -> ExploreResult:
        profile = self.get_profile(user_id, display_name)
        dungeon = DUNGEON_BY_ID.get(dungeon_id)
        if dungeon is None:
            return ExploreResult(False, "알 수 없는 던전입니다.", profile, daily_remaining=self.daily_remaining(profile))
        self._reset_daily_if_needed(profile)
        remaining = self.daily_remaining(profile)
        if remaining <= 0:
            return ExploreResult(False, f"오늘 탐색 횟수를 모두 사용했습니다. 하루 {DAILY_EXPLORES}회까지 가능합니다.", profile, dungeon, daily_remaining=0)
        if profile.level < dungeon.level_req:
            return ExploreResult(False, f"{dungeon.name}은 Lv.{dungeon.level_req}부터 입장할 수 있습니다.", profile, dungeon, daily_remaining=remaining)

        enemy = self._choose_enemy(dungeon)
        profile.daily_explores_used += 1
        battle = self._simulate_battle(profile, enemy.name, self._enemy_stats(enemy.stats))
        reward = RewardReport()
        if battle.won:
            profile.dungeon_clear_count += 1
            reward.gold = enemy.gold + self.rng.randint(0, 20 * enemy.rank)
            reward.exp = enemy.exp
            reward.dropped_item = self._roll_item_drop(profile, enemy.rank, enemy.drop_chance)
            reward.levels_gained = self._grant_exp(profile, reward.exp)
            profile.gold += reward.gold
        else:
            reward.consolation = True
            reward.gold = max(1, enemy.gold // 5)
            reward.exp = max(1, enemy.exp // 5)
            reward.levels_gained = self._grant_exp(profile, reward.exp)
            profile.gold += reward.gold
        self._save()
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
        reward_locked = profile.weekly_boss_clears.get(boss.id) == weekly_key
        battle = self._simulate_battle(
            profile,
            boss.name,
            self._enemy_stats(boss.stats),
            boss=boss,
        )
        reward = RewardReport(weekly_reward_locked=reward_locked)
        if battle.won and not reward_locked:
            reward.gold = boss.gold + self.rng.randint(0, 120 * boss.rank)
            reward.exp = boss.exp
            reward.stat_points = boss.stat_points
            reward.dropped_item = self._roll_item_drop(profile, boss.rank + 1, boss.drop_chance)
            reward.levels_gained = self._grant_exp(profile, reward.exp)
            reward.weekly_reward_claimed = True
            profile.gold += reward.gold
            profile.stat_points += reward.stat_points
            profile.boss_clear_count += 1
            profile.weekly_boss_clears[boss.id] = weekly_key
        self._save()
        return BossResult(True, "보스 도전 완료", profile, boss, battle, reward, weekly_key)

    def allocate_stat(self, user_id: int, display_name: str, stat: str, amount: int) -> StatAllocationResult:
        profile = self.get_profile(user_id, display_name)
        amount = max(1, min(50, int(amount)))
        if stat not in {"attack", "hp", "defense"}:
            return StatAllocationResult(False, "올릴 수 없는 스탯입니다.", profile)
        if profile.stat_points < amount:
            return StatAllocationResult(False, f"스탯 포인트가 부족합니다. 보유: {profile.stat_points}", profile)

        profile.stat_points -= amount
        if stat == "attack":
            profile.base_atk += amount
            profile.base_atk_points += amount
            label = "공격력"
        elif stat == "hp":
            profile.max_hp += 5 * amount
            profile.max_hp_points += amount
            label = "최대 HP"
        else:
            profile.defense = round(profile.defense + 0.02 * amount, 4)
            profile.defense_points += amount
            label = "방어"
        self._save()
        return StatAllocationResult(True, f"{label}에 {amount}포인트를 투자했습니다.", profile, amount)

    def enhancement_preview(self, user_id: int, display_name: str, item_uid: int) -> EnhancementPreview:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementPreview(False, "해당 UID의 장비를 찾지 못했습니다.", profile)
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
        )

    def enhance(self, user_id: int, display_name: str, item_uid: int) -> EnhancementResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementResult(False, "해당 UID의 장비를 찾지 못했습니다.", profile)
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
            item.stars = 0
            item.destroyed = True
            outcome = "destroyed"
        else:
            outcome = "failed"
        self._save()
        return EnhancementResult(True, "강화 완료", profile, item, cost, before, item.stars, outcome, odds)

    def restore(self, user_id: int, display_name: str, item_uid: int) -> EnhancementResult:
        profile = self.get_profile(user_id, display_name)
        item = self._find_item(profile, item_uid)
        if item is None:
            return EnhancementResult(False, "해당 UID의 장비를 찾지 못했습니다.", profile)
        if not item.destroyed:
            return EnhancementResult(False, "파괴된 장비가 아닙니다.", profile, item)
        template = ITEM_BY_ID[item.template_id]
        cost = restore_cost(template.rarity)
        if profile.gold < cost:
            return EnhancementResult(False, f"골드가 부족합니다. 필요: {cost}G, 보유: {profile.gold}G", profile, item, cost)
        profile.gold -= cost
        item.destroyed = False
        item.stars = 0
        self._save()
        return EnhancementResult(True, "복구 완료", profile, item, cost, 0, 0, "restored")

    def equipped_items(self, profile: PlayerProfile) -> list[ItemInstance]:
        items = [
            item for item in profile.inventory
            if not item.destroyed and item.template_id in ITEM_BY_ID
        ]
        return sorted(items, key=self.item_score, reverse=True)[:MAX_EQUIPPED_ITEMS]

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
        destroyed = " 파괴됨" if item.destroyed else ""
        return f"#{item.uid} [{RARITY_LABELS[template.rarity]}] {template.name} +{item.stars}{destroyed}"

    def item_stats_text(self, item: ItemInstance) -> str:
        stats = scaled_item_stats(item.template_id, item.stars)
        return self.format_stats(stats, signed=True)

    def format_stats(self, stats: CombatStats | dict[str, float], *, signed: bool = False) -> str:
        raw = stats.__dict__ if isinstance(stats, CombatStats) else stats
        parts: list[str] = []
        for key in STAT_ORDER:
            value = raw.get(key, 0)
            if not value:
                continue
            parts.append(f"{STAT_LABELS[key]} {self._format_stat_value(key, float(value), signed=signed)}")
        return ", ".join(parts) if parts else "스탯 없음"

    def skill_summary(self, skill: SkillTemplate) -> str:
        parts: list[str] = []
        if skill.damage_multiplier > 0 and skill.hits > 0:
            parts.append(f"{skill.damage_multiplier * 100:.0f}% x {skill.hits}")
        if skill.heal_power > 0:
            parts.append(f"회복 {skill.heal_power:.2f}x")
        if skill.player_mods:
            parts.append(f"자신 {self.format_stats(skill.player_mods, signed=True)}")
        if skill.damage_cut > 0:
            parts.append(f"피해 차단 {skill.damage_cut * 100:.0f}%")
        if skill.enemy_mods:
            parts.append(f"적 {self.format_stats(skill.enemy_mods, signed=True)}")
        if skill.duration > 0 and (skill.player_mods or skill.enemy_mods or skill.damage_cut > 0):
            parts.append(f"{skill.duration}턴")
        if skill.cooldown > 0:
            parts.append(f"쿨 {skill.cooldown}턴")
        if skill.uses > 0:
            parts.append(f"전투당 {skill.uses}회")
        return " · ".join(parts) if parts else "기본 효과"

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
        player_effects: list[ActiveEffect] = []
        enemy_effects: list[ActiveEffect] = []
        triggered_patterns: set[int] = set()
        skills = self.unlocked_skills(profile)
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
                damage = self._actual_damage(player_stats, player_hp, enemy_stats, enemy_hp)
                enemy_hp = max(0, enemy_hp - damage)
                log.append(f"{turn}T 기본 공격: {enemy_name}에게 {damage} 피해")
            else:
                self._mark_skill_used(skill, uses_left, cooldowns)
                skills_used.append(skill.name)
                damage, heal = self._use_player_skill(
                    skill,
                    player_stats,
                    enemy_stats,
                    player_hp,
                    enemy_hp,
                    player_effects,
                    enemy_effects,
                )
                if heal > 0:
                    player_hp = min(player_stats.final_hp, player_hp + heal)
                if damage > 0:
                    enemy_hp = max(0, enemy_hp - damage)
                action_bits = []
                if damage > 0:
                    action_bits.append(f"{damage} 피해")
                if heal > 0:
                    action_bits.append(f"{heal} 회복")
                if not action_bits:
                    action_bits.append("효과 발동")
                log.append(f"{turn}T {skill.name}: {', '.join(action_bits)}")

            if enemy_hp <= 0:
                return BattleReport(True, turn, player_hp, player_base.final_hp, 0, enemy_base.final_hp, self._trim_log(log), skills_used)

            enemy_stats = self._stats_with_effects(enemy_base, enemy_effects)
            player_stats = self._stats_with_effects(player_base, player_effects)
            pattern = self._next_boss_pattern(boss, enemy_hp, enemy_base.final_hp, triggered_patterns)
            if pattern is None:
                damage = self._actual_damage(enemy_stats, enemy_hp, player_stats, player_hp)
                player_hp = max(0, player_hp - damage)
                log.append(f"{turn}T {enemy_name} 반격: {damage} 피해")
            else:
                damage = self._use_boss_pattern(pattern, enemy_stats, player_stats, enemy_hp, player_hp, player_effects, enemy_effects)
                if damage > 0:
                    player_hp = max(0, player_hp - damage)
                    log.append(f"{turn}T {pattern.name}: {damage} 피해")
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
        incoming = self._estimated_damage(enemy_stats, enemy_hp, player_stats, player_hp)

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
            defense_skills.sort(key=lambda skill: skill.damage_cut + skill.player_mods.get("defense", 0) + skill.player_mods.get("garrison", 0), reverse=True)
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
            key=lambda skill: self._estimated_skill_damage(skill, player_stats, player_hp, enemy_stats, enemy_hp),
            reverse=True,
        )
        best_attack = attack_skills[0]
        best_damage = self._estimated_skill_damage(best_attack, player_stats, player_hp, enemy_stats, enemy_hp)
        base_damage = self._estimated_damage(player_stats, player_hp, enemy_stats, enemy_hp)
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
    ) -> float:
        if skill.damage_multiplier <= 0 or skill.hits <= 0:
            return 0.0
        return sum(
            self._estimated_damage(player_stats, player_hp, enemy_stats, enemy_hp, skill.damage_multiplier)
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
    ) -> tuple[int, int]:
        if skill.player_mods or skill.damage_cut > 0:
            mods = dict(skill.player_mods)
            if skill.damage_cut > 0:
                mods["damage_cut"] = mods.get("damage_cut", 0.0) + skill.damage_cut
            player_effects.append(ActiveEffect(max(1, skill.duration), mods, skill.id))
        if skill.enemy_mods:
            enemy_effects.append(ActiveEffect(max(1, skill.duration), dict(skill.enemy_mods), skill.id))

        damage = 0
        if skill.damage_multiplier > 0 and skill.hits > 0:
            for _ in range(skill.hits):
                damage += self._actual_damage(player_stats, player_hp, enemy_stats, enemy_hp, skill.damage_multiplier)
        elif skill.player_mods or skill.enemy_mods or skill.heal_power > 0:
            damage = self._actual_damage(player_stats, player_hp, enemy_stats, enemy_hp, 0.65)

        heal = 0
        if skill.heal_power > 0:
            outgoing = self._outgoing_damage(player_stats, player_hp)
            heal = max(1, int(outgoing * skill.heal_power))
        return damage, heal

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
    ) -> int:
        source_id = f"boss:{pattern.name}"
        if pattern.player_mods:
            player_effects.append(ActiveEffect(max(1, pattern.duration), dict(pattern.player_mods), source_id))
        if pattern.boss_mods:
            enemy_effects.append(ActiveEffect(max(1, pattern.duration), dict(pattern.boss_mods), source_id))
        if pattern.damage_multiplier <= 0 or pattern.hits <= 0:
            return 0
        damage = 0
        for _ in range(pattern.hits):
            damage += self._actual_damage(boss_stats, boss_hp, player_stats, player_hp, pattern.damage_multiplier)
        return damage

    def _player_stats(self, profile: PlayerProfile) -> CombatStats:
        stats = CombatStats(
            base_atk=int(profile.base_atk),
            max_hp=int(profile.max_hp),
            hp_bonus=float(profile.hp_bonus),
            atk=float(profile.atk),
            defense=float(profile.defense),
            garrison=float(profile.garrison),
            strength=float(profile.strength),
            enmity=float(profile.enmity),
            damage_cut=float(profile.damage_cut),
            dmg_mitigation=float(profile.dmg_mitigation),
            dmg_amplification=float(profile.dmg_amplification),
        )
        for job in self.job_chain(profile):
            for key, value in job.stats.items():
                self._apply_stat(stats, key, value)
        for item in self.equipped_items(profile):
            for key, value in scaled_item_stats(item.template_id, item.stars).items():
                self._apply_stat(stats, key, value)
        stats.base_atk = max(1, int(stats.base_atk))
        stats.max_hp = max(1, int(stats.max_hp))
        return stats

    def _enemy_stats(self, raw_stats: dict[str, float]) -> CombatStats:
        return CombatStats(
            base_atk=int(raw_stats.get("base_atk", 1)),
            max_hp=int(raw_stats.get("max_hp", 1)),
            hp_bonus=float(raw_stats.get("hp_bonus", 0.0)),
            atk=float(raw_stats.get("atk", 0.0)),
            defense=float(raw_stats.get("defense", 0.0)),
            garrison=float(raw_stats.get("garrison", 0.0)),
            strength=float(raw_stats.get("strength", 0.0)),
            enmity=float(raw_stats.get("enmity", 0.0)),
            damage_cut=float(raw_stats.get("damage_cut", 0.0)),
            dmg_mitigation=float(raw_stats.get("dmg_mitigation", 0.0)),
            dmg_amplification=float(raw_stats.get("dmg_amplification", 0.0)),
        )

    def _stats_with_effects(self, base: CombatStats, effects: list[ActiveEffect]) -> CombatStats:
        stats = base.copy()
        for effect in effects:
            if effect.turns <= 0:
                continue
            for key, value in effect.mods.items():
                self._apply_stat(stats, key, value)
        stats.base_atk = max(1, int(stats.base_atk))
        stats.max_hp = max(1, int(stats.max_hp))
        return stats

    def _tick_effects(self, effects: list[ActiveEffect]) -> list[ActiveEffect]:
        return [
            ActiveEffect(effect.turns - 1, effect.mods, effect.source_id)
            for effect in effects
            if effect.turns - 1 > 0
        ]

    def _tick_cooldowns(self, cooldowns: dict[str, int]) -> None:
        for skill_id, turns in list(cooldowns.items()):
            if turns > 0:
                cooldowns[skill_id] = turns - 1

    def _has_active_effect(self, effects: list[ActiveEffect], source_id: str) -> bool:
        return any(effect.source_id == source_id and effect.turns > 0 for effect in effects)

    def _apply_stat(self, stats: CombatStats, key: str, value: float) -> None:
        if not hasattr(stats, key):
            return
        setattr(stats, key, getattr(stats, key) + value)

    def _outgoing_damage(self, stats: CombatStats, current_hp: int) -> float:
        ratio = self._hp_ratio(current_hp, stats.final_hp)
        return (
            stats.base_atk
            * (1 + stats.atk)
            * (1 + stats.strength * ratio)
            * (1 + stats.enmity * (1 - ratio))
            * (1 + stats.dmg_amplification)
        )

    def _defense_factor(self, stats: CombatStats, current_hp: int) -> float:
        ratio = self._hp_ratio(current_hp, stats.final_hp)
        return max(0.01, 1 + stats.defense + stats.garrison * (1 - ratio))

    def _estimated_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
    ) -> float:
        damage = self._outgoing_damage(attacker, attacker_hp) * multiplier
        mitigated = damage / self._defense_factor(defender, defender_hp) - defender.dmg_mitigation
        return max(1.0, mitigated * max(0.05, 1 - defender.damage_cut))

    def _actual_damage(
        self,
        attacker: CombatStats,
        attacker_hp: int,
        defender: CombatStats,
        defender_hp: int,
        multiplier: float = 1.0,
    ) -> int:
        estimated = self._estimated_damage(attacker, attacker_hp, defender, defender_hp, multiplier)
        spread = 0.95 + self.rng.random() * 0.10
        return max(1, int(estimated * spread))

    def _hp_ratio(self, current_hp: int, max_hp: int) -> float:
        return max(0.0, min(1.0, current_hp / max(1, max_hp)))

    def _grant_exp(self, profile: PlayerProfile, exp: int) -> int:
        profile.exp += max(0, int(exp))
        levels = 0
        while profile.exp >= next_level_exp(profile.level):
            profile.level += 1
            profile.stat_points += 2
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

    def _roll_item_drop(self, profile: PlayerProfile, rank: int, chance: float) -> ItemInstance | None:
        if self.rng.random() > chance:
            return None
        rarity = self._roll_rarity(rank)
        template = self.rng.choice(ITEMS_BY_RARITY[rarity])
        item = ItemInstance(profile.next_item_uid, template.id)
        profile.next_item_uid += 1
        profile.inventory.append(item)
        return item

    def _roll_rarity(self, rank: int) -> str:
        rank = max(1, rank)
        weights = {
            "normal": max(450, 6200 - 880 * rank),
            "rare": 2350 + 280 * rank,
            "epic": 850 + 230 * rank,
            "unique": 260 + 115 * rank,
            "legendary": 45 + 48 * rank,
        }
        total = sum(weights.values())
        roll = self.rng.randint(1, total)
        running = 0
        for rarity in RARITIES:
            running += weights[rarity]
            if roll <= running:
                return rarity
        return "normal"

    def _reset_daily_if_needed(self, profile: PlayerProfile) -> None:
        today = self._today_key()
        if profile.daily_date != today:
            profile.daily_date = today
            profile.daily_explores_used = 0

    def _today_key(self) -> str:
        return datetime.now().astimezone().date().isoformat()

    def _week_key(self) -> str:
        iso = datetime.now().astimezone().date().isocalendar()
        return f"{iso.year}-W{iso.week:02d}"

    def _find_item(self, profile: PlayerProfile, item_uid: int) -> ItemInstance | None:
        for item in profile.inventory:
            if item.uid == item_uid and item.template_id in ITEM_BY_ID:
                return item
        return None

    def _cleanup_profile(self, profile: PlayerProfile) -> None:
        if profile.job_id not in JOB_BY_ID:
            profile.job_id = "novice"
        profile.inventory = [
            item for item in profile.inventory
            if item.uid > 0 and item.template_id in ITEM_BY_ID
        ]
        profile.next_item_uid = max(
            profile.next_item_uid,
            max((item.uid for item in profile.inventory), default=0) + 1,
        )

    def _save(self) -> None:
        self.store.save_profiles(self._profiles)

    def _trim_log(self, log: list[str]) -> list[str]:
        if len(log) <= 8:
            return log
        return log[:4] + ["..."] + log[-3:]

    def _format_stat_value(self, key: str, value: float, *, signed: bool = False) -> str:
        sign = "+" if signed else ""
        if key in PERCENT_STATS:
            return f"{value * 100:{sign}.1f}%"
        if key in INTEGER_STATS:
            return f"{round(value):{sign}d}"
        return f"{value:{sign}.1f}"

