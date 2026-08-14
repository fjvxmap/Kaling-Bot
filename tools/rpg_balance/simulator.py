from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from random import Random
from statistics import mean, median
from typing import Iterable, Sequence

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    ITEMS_BY_RARITY,
    JOBS,
    JOB_BY_ID,
    MAX_EQUIPPED_SKILLS,
    SKILLS,
    SkillTemplate,
)
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile


DEFAULT_SETS = ("epic", "unique", "unique-plus")


class _MemoryStore:
    def load_profiles(self) -> dict[int, PlayerProfile]:
        return {}

    def save_profiles(self, profiles: dict[int, PlayerProfile]) -> None:
        return None


@dataclass(frozen=True)
class SimConfig:
    level: int
    turns: int
    stars: int
    enemy_defense: float
    enemy_damage_cut: float
    enemy_mitigation: float
    enemy_level: int
    enemy_hp: int


@dataclass(frozen=True)
class BalanceResult:
    job_id: str
    job_name: str
    set_name: str
    dpt: float
    basic_dpt: float
    skill_dpt: float
    survival: float
    items: tuple[str, ...]
    skills: tuple[str, ...]


@dataclass(frozen=True)
class RotationResult:
    dpt: float
    basic_dpt: float
    skill_dpt: float
    total_damage: float


@dataclass(frozen=True)
class BossTrialResult:
    won: bool
    turns: int
    player_hp: int
    boss_hp: int


class BalanceSimulator:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.service = RPGService(store=_MemoryStore(), rng=Random(20260710))

    def run_set(
        self,
        job_id: str,
        set_name: str,
        *,
        item_candidates: int,
        skill_candidates: int,
    ) -> BalanceResult:
        job = JOB_BY_ID[job_id]
        item_combos = self._item_combos(job_id, set_name, item_candidates)
        if not item_combos:
            item_combos = [()]
        best: BalanceResult | None = None
        for item_ids in item_combos:
            skill_combos = self._skill_combos(job_id, item_ids, skill_candidates)
            for skills in skill_combos:
                rotation = self._simulate(job_id, item_ids, skills)
                if best is None or rotation.dpt > best.dpt:
                    profile = self._profile(job_id, item_ids)
                    best = BalanceResult(
                        job_id=job.id,
                        job_name=job.name,
                        set_name=set_name,
                        dpt=rotation.dpt,
                        basic_dpt=rotation.basic_dpt,
                        skill_dpt=rotation.skill_dpt,
                        survival=self._survival_score(profile),
                        items=tuple(item_ids),
                        skills=tuple(skill.id for skill in skills),
                    )
        if best is None:
            raise RuntimeError(f"no simulation result for {job_id}:{set_name}")
        return best

    def _simulate(
        self,
        job_id: str,
        item_ids: Sequence[str],
        skills: Sequence[SkillTemplate],
    ) -> RotationResult:
        profile = self._profile(job_id, item_ids)
        return self.simulate_profile(profile, skills)

    def simulate_profile(
        self,
        profile: PlayerProfile,
        skills: Sequence[SkillTemplate] | None = None,
        enemy_stats: CombatStats | None = None,
    ) -> RotationResult:
        profile = PlayerProfile.from_dict(profile.to_dict())
        skills = tuple(skills if skills is not None else self.service.combat_skills(profile))
        base_stats = self.service._player_stats(profile)
        enemy_base = enemy_stats or self._enemy_stats()
        player_effects = self.service._permanent_effects(profile)
        enemy_effects = []
        cooldowns: dict[str, int] = {}
        uses_left = {skill.id: skill.uses for skill in skills if skill.uses > 0}
        basic_total = 0.0
        skill_total = 0.0

        def ready(skill: SkillTemplate) -> bool:
            if cooldowns.get(skill.id, 0) > 0:
                return False
            return skill.uses <= 0 or uses_left.get(skill.id, 0) > 0

        def use_skill(skill: SkillTemplate) -> None:
            nonlocal skill_total
            player_stats = self.service._stats_with_effects(base_stats, player_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects)
            result = self.service._use_player_skill(
                skill,
                player_stats,
                enemy_stats,
                player_stats.final_hp,
                enemy_stats.final_hp,
                player_effects,
                enemy_effects,
            )
            player_stats = self.service._stats_with_effects(base_stats, player_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects)
            skill_total += self.service._estimated_skill_damage(
                skill,
                player_stats,
                player_stats.final_hp,
                enemy_stats,
                enemy_stats.final_hp,
                player_effects,
            ) * max(1, result.activations)
            if skill.uses > 0:
                uses_left[skill.id] = max(0, uses_left.get(skill.id, 0) - 1)
            if skill.cooldown > 0:
                cooldowns[skill.id] = skill.cooldown

        for _turn in range(self.config.turns):
            support_skills = [
                skill for skill in skills
                if ready(skill) and (skill.damage_multiplier <= 0 or skill.hits <= 0)
            ]
            damage_skills = [
                skill for skill in skills
                if ready(skill) and skill.damage_multiplier > 0 and skill.hits > 0
            ]
            for skill in sorted(support_skills, key=self._support_score, reverse=True):
                use_skill(skill)
            for skill in sorted(damage_skills, key=lambda skill: (
                self._support_score(skill),
                self._skill_damage_estimate(base_stats, enemy_base, player_effects, enemy_effects, skill),
            ), reverse=True):
                use_skill(skill)

            player_stats = self.service._stats_with_effects(base_stats, player_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects)
            basic_total += self.service._estimated_basic_attack_damage(
                player_stats,
                player_stats.final_hp,
                enemy_stats,
                enemy_stats.final_hp,
                player_effects,
            )
            player_effects = self.service._tick_effects(player_effects)
            enemy_effects = self.service._tick_effects(enemy_effects)
            self.service._tick_cooldowns(cooldowns)

        turns = max(1, self.config.turns)
        total = basic_total + skill_total
        return RotationResult(
            dpt=total / turns,
            basic_dpt=basic_total / turns,
            skill_dpt=skill_total / turns,
            total_damage=total,
        )

    def _item_combos(
        self,
        job_id: str,
        set_name: str,
        candidate_count: int,
    ) -> list[tuple[str, ...]]:
        if set_name == "none":
            return [()]
        if set_name in ITEMS_BY_RARITY:
            candidates = self._top_items(job_id, ITEMS_BY_RARITY[set_name], candidate_count)
            return self._limited_combinations(candidates, 4)
        if set_name == "unique-plus":
            unique_items = self._top_items(job_id, ITEMS_BY_RARITY.get("unique", []), candidate_count)
            legendary_items = [item.id for item in ITEMS_BY_RARITY.get("legendary", [])]
            combos = set(self._limited_combinations(unique_items, 4))
            for legendary_id in legendary_items:
                for uniques in self._limited_combinations(unique_items, 3):
                    combos.add((legendary_id, *uniques))
            return sorted(combos)
        raise ValueError(f"unknown item set: {set_name}")

    def _top_items(self, job_id: str, items: Iterable[object], limit: int) -> list[str]:
        scored = [
            (self._single_item_score(job_id, item.id), item.id)
            for item in items
        ]
        return [
            item_id for _score, item_id
            in sorted(scored, reverse=True)[:max(1, limit)]
        ]

    def _single_item_score(self, job_id: str, item_id: str) -> float:
        profile = self._profile(job_id, [item_id])
        base_stats = self.service._player_stats(profile)
        player_effects = self.service._permanent_effects(profile)
        player_stats = self.service._stats_with_effects(base_stats, player_effects)
        enemy_stats = self._enemy_stats()
        basic = self.service._estimated_basic_attack_damage(
            player_stats,
            player_stats.final_hp,
            enemy_stats,
            enemy_stats.final_hp,
            player_effects,
        )
        skill_scores = [
            (
                self._skill_candidate_score(
                    skill,
                    player_stats,
                    enemy_stats,
                    player_effects,
                    [],
                ),
                skill,
            )
            for skill in self._available_skills(job_id)
        ]
        normal = sorted((score for score, skill in skill_scores if not skill.special), reverse=True)[:MAX_EQUIPPED_SKILLS]
        special = sorted((score for score, skill in skill_scores if skill.special), reverse=True)[:1]
        return basic + sum([*normal, *special]) / max(1, self.config.turns)

    def _skill_combos(
        self,
        job_id: str,
        item_ids: Sequence[str],
        candidate_count: int,
    ) -> list[tuple[SkillTemplate, ...]]:
        skills = self._available_skills(job_id)
        if not skills:
            return [()]
        profile = self._profile(job_id, item_ids)
        base_stats = self.service._player_stats(profile)
        player_effects = self.service._permanent_effects(profile)
        enemy_effects = []
        enemy_base = self._enemy_stats()
        scored = [
            (
                max(
                    self._support_score(skill),
                    self._skill_candidate_score(
                        skill,
                        base_stats,
                        enemy_base,
                        player_effects,
                        enemy_effects,
                    ),
                ),
                skill,
            )
            for skill in skills
        ]
        ranked = sorted(scored, key=lambda row: row[0], reverse=True)
        normal_candidates = [
            skill for _score, skill in ranked if not skill.special
        ][:max(1, candidate_count)]
        special_candidates = [skill for _score, skill in ranked if skill.special]
        normal_count = min(MAX_EQUIPPED_SKILLS, len(normal_candidates))
        normal_combos = (
            [tuple(normal_candidates)]
            if len(normal_candidates) <= normal_count
            else list(combinations(normal_candidates, normal_count))
        )
        if not special_candidates:
            return normal_combos or [()]
        special_scored = sorted(
            special_candidates,
            key=lambda skill: max(
                self._support_score(skill),
                self._skill_candidate_score(
                    skill,
                    base_stats,
                    enemy_base,
                    player_effects,
                    enemy_effects,
                ),
            ),
            reverse=True,
        )[:max(1, min(candidate_count, len(special_candidates)))]
        return [tuple([*normal, special]) for normal in normal_combos for special in special_scored]

    def _skill_damage_estimate(
        self,
        player_base: CombatStats,
        enemy_base: CombatStats,
        player_effects: list[object],
        enemy_effects: list[object],
        skill: SkillTemplate,
    ) -> float:
        player_stats = self.service._stats_with_effects(player_base, player_effects)
        enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects)
        return self.service._estimated_skill_damage(
            skill,
            player_stats,
            player_stats.final_hp,
            enemy_stats,
            enemy_stats.final_hp,
            player_effects,
        )

    def _skill_candidate_score(
        self,
        skill: SkillTemplate,
        player_base: CombatStats,
        enemy_base: CombatStats,
        player_effects: list[object],
        enemy_effects: list[object],
    ) -> float:
        damage = self._skill_damage_estimate(
            player_base,
            enemy_base,
            player_effects,
            enemy_effects,
            skill,
        )
        cadence = self.config.turns if skill.uses > 0 else max(1, skill.cooldown)
        return damage / max(1, cadence) + self._support_score(skill)

    def _available_skills(self, job_id: str) -> list[SkillTemplate]:
        chain = self._job_chain_ids(job_id)
        return [
            skill for skill in SKILLS
            if skill.unlock_level <= self.config.level
            and any(skill_job_id in chain for skill_job_id in skill.job_ids)
        ]

    def _job_chain_ids(self, job_id: str) -> set[str]:
        ids: set[str] = set()
        job = JOB_BY_ID[job_id]
        while job.id and job.id not in ids:
            ids.add(job.id)
            if not job.parent_id:
                break
            job = JOB_BY_ID[job.parent_id]
        return ids

    def _profile(self, job_id: str, item_ids: Sequence[str]) -> PlayerProfile:
        profile = PlayerProfile.create(1, "BalanceSim")
        profile.level = self.config.level
        profile.job_id = job_id
        profile.inventory = []
        profile.equipped_item_uids = []
        profile.next_item_uid = 1
        for item_id in item_ids:
            uid = profile.next_item_uid
            profile.next_item_uid += 1
            profile.inventory.append(
                ItemInstance(uid=uid, template_id=item_id, stars=self.config.stars)
            )
            profile.equipped_item_uids.append(uid)
        return profile

    def _enemy_stats(self) -> CombatStats:
        return CombatStats(
            base_atk=1,
            max_hp=self.config.enemy_hp,
            level=self.config.enemy_level,
            defense=self.config.enemy_defense,
            damage_cut=self.config.enemy_damage_cut,
            dmg_mitigation=self.config.enemy_mitigation,
        )

    def _survival_score(self, profile: PlayerProfile) -> float:
        stats = self.service._player_stats(profile)
        return (
            stats.final_hp
            * (1 + max(0.0, stats.defense))
            / max(0.05, 1 - stats.damage_cut)
            + stats.dmg_mitigation * 20
        )

    def _support_score(self, skill: SkillTemplate) -> float:
        score = 0.0
        for effect in skill.player_stat_effects:
            duration = self._score_duration(effect.duration)
            target_bonus = 1.8 if effect.target == "allies" else 1.0
            score += self._stat_effect_score(effect.stat, effect.value, duration) * target_bonus
        for effect in skill.enemy_stat_effects:
            duration = self._score_duration(effect.duration)
            score += self._enemy_effect_score(effect.stat, -effect.value, duration)
        for special in (skill.player_effects, skill.enemy_effects):
            if special.flurry is not None:
                score += 450
            if special.double_strike is not None:
                score += 650
            score += sum(bonus.ratio * 650 for bonus in special.bonus_damage)
            score += sum(final.ratio * 1000 for final in special.final_damage)
            score += sum(reinforce.ratio * 350 for reinforce in special.critical_reinforce)
            score += sum(
                post_attack.ratio * post_attack.count * 120
                for post_attack in special.post_attack_ability_damage
            )
            score += len(special.veil) * 320
            score += len(special.dispel_guard) * 260
        score += sum(action.count * 180 for action in skill.effect_actions)
        score += skill.heal_power * 700
        return score

    def _stat_effect_score(self, stat: str, value: float, duration: int) -> float:
        weight = {
            "atk": 1000,
            "skill_damage": 1000,
            "dmg_amplification": 1000,
            "critical_rate": 500,
            "critical_damage": 500,
            "double_attack_rate": 500,
            "triple_attack_rate": 500,
            "hp_bonus": 520,
            "defense": 520,
            "damage_cut": 520,
            "life_steal": 350,
            "life_steal_cap": 350,
            "dmg_supplement": 8,
            "skill_dmg_supplement": 8,
        }.get(stat, 250)
        return value * weight * duration / max(1, self.config.turns)

    def _enemy_effect_score(self, stat: str, value: float, duration: int) -> float:
        weight = {
            "defense": 650,
            "damage_cut": 650,
            "atk": 520,
        }.get(stat, 250)
        return value * weight * duration / max(1, self.config.turns)

    def _score_duration(self, duration: int) -> int:
        if duration < 0:
            return self.config.turns
        return max(1, duration)

    def _limited_combinations(self, values: Sequence[str], size: int) -> list[tuple[str, ...]]:
        if not values:
            return [()]
        if len(values) <= size:
            return [tuple(values)]
        return list(combinations(values, size))

    def simulate_boss_trial(
        self,
        profile: PlayerProfile,
        boss_id: str,
        *,
        seed: int,
        max_turns: int = 120,
    ) -> BossTrialResult:
        from bot.cogs.rpg import RPGCog

        boss = BOSS_BY_ID[boss_id]
        service = RPGService(store=_MemoryStore(), rng=Random(seed))
        trial_profile = PlayerProfile.from_dict(profile.to_dict())
        service._profiles[trial_profile.user_id] = trial_profile
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            boss,
            trial_profile.user_id,
            trial_profile.display_name,
            practice=True,
        )
        if session is None:
            raise RuntimeError(message)
        ok, message = engine._start_boss_session(session, trial_profile.user_id)
        if not ok:
            raise RuntimeError(message)

        role_order = {"debuff": 0, "buff": 1, "heal": 2, "attack": 3}
        actions = 0
        while not (session.completed or session.failed or session.cancelled) and actions < max_turns:
            participant = session.participants.get(trial_profile.user_id)
            if participant is None or not participant.alive:
                break
            skills = sorted(
                service.combat_skills(trial_profile),
                key=lambda skill: (role_order.get(skill.role, 4), skill.cooldown, skill.id),
            )
            for skill in skills:
                if participant.ability_cooldowns.get(skill.id, 0) > 0:
                    continue
                if engine._ability_used_out(participant, skill):
                    continue
                if skill.role == "heal" and participant.hp >= participant.max_hp * 0.8:
                    continue
                engine._boss_use_ability(
                    session,
                    trial_profile.user_id,
                    trial_profile.display_name,
                    skill.id,
                )
                if session.completed or session.failed or not participant.alive:
                    break
            if session.completed or session.failed or not participant.alive:
                break
            warning = participant.pending_warning
            if (
                warning is not None
                and warning.remaining_turns <= 1
                and not engine._warning_complete(warning)
            ):
                engine._boss_guard(
                    session,
                    trial_profile.user_id,
                    trial_profile.display_name,
                )
            else:
                engine._boss_attack(
                    session,
                    trial_profile.user_id,
                    trial_profile.display_name,
                )
            actions += 1

        participant = session.participants.get(trial_profile.user_id)
        return BossTrialResult(
            won=session.completed,
            turns=actions,
            player_hp=participant.hp if participant is not None else 0,
            boss_hp=session.boss_hp,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RPG balance simulations.")
    parser.add_argument("--level", type=int, default=50)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--stars", type=int, default=0)
    parser.add_argument("--tier", type=int, default=5)
    parser.add_argument("--jobs", nargs="*", default=[])
    parser.add_argument("--sets", nargs="*", default=list(DEFAULT_SETS))
    parser.add_argument("--item-candidates", type=int, default=7)
    parser.add_argument("--skill-candidates", type=int, default=6)
    parser.add_argument("--enemy-defense", type=float, default=0.85)
    parser.add_argument("--enemy-damage-cut", type=float, default=0.0)
    parser.add_argument("--enemy-mitigation", type=float, default=0.0)
    parser.add_argument("--enemy-level", type=int, default=30)
    parser.add_argument("--enemy-hp", type=int, default=10_000_000)
    parser.add_argument("--state", type=Path, help="Read-only RPG state JSON to analyze.")
    parser.add_argument("--profiles", nargs="*", default=[], help="Profile IDs or display names to include.")
    parser.add_argument("--boss", choices=sorted(BOSS_BY_ID), help="Use an actual boss as the target.")
    parser.add_argument("--hard-report", action="store_true", help="Run the live boss engine against every hard boss.")
    parser.add_argument("--trials", type=int, default=5, help="Trials per profile and hard boss.")
    parser.add_argument("--details", action="store_true")
    return parser.parse_args(argv)


def load_state_profiles(path: Path) -> list[PlayerProfile]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw_profiles, dict):
        raise ValueError("state JSON does not contain a profiles object")
    profiles: list[PlayerProfile] = []
    for user_id, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            continue
        profile = PlayerProfile.from_dict(raw)
        profile.user_id = int(user_id)
        profiles.append(profile)
    return profiles


def print_state_report(
    simulator: BalanceSimulator,
    profiles: Sequence[PlayerProfile],
    selected_profiles: Sequence[str],
    boss_id: str | None,
) -> int:
    selected = {str(value) for value in selected_profiles}
    if selected:
        profiles = [
            profile for profile in profiles
            if str(profile.user_id) in selected or profile.display_name in selected
        ]
    if not profiles:
        raise SystemExit("no matching profiles in state file")

    boss = BOSS_BY_ID.get(boss_id or "")
    enemy = (
        simulator.service._enemy_stats(boss.stats, level=boss.level_req)
        if boss is not None
        else simulator._enemy_stats()
    )
    target_name = f"{boss.name} [{boss.difficulty}]" if boss is not None else "synthetic target"
    print(
        f"state profiles={len(profiles)} turns={simulator.config.turns} "
        f"target={target_name} hp={enemy.final_hp:.0f} defense={enemy.defense:.2f}"
    )
    print(
        f"{'profile':18s} {'job':14s} {'lv':>3s} {'dpt':>9s} {'basic':>9s} "
        f"{'skills':>9s} {'kill':>7s} {'hp':>7s} {'inc':>7s} {'hits':>6s}"
    )
    print("-" * 105)
    for profile in sorted(profiles, key=lambda row: (row.display_name, row.user_id)):
        rotation = simulator.simulate_profile(profile, enemy_stats=enemy)
        stats = simulator.service.profile_stats(profile)
        incoming = simulator.service._estimated_basic_attack_damage(
            enemy,
            enemy.final_hp,
            stats,
            stats.final_hp,
            [],
        )
        target_hp = enemy.final_hp
        kill_turns = target_hp / rotation.dpt if rotation.dpt > 0 else float("inf")
        survival_hits = stats.final_hp / incoming if incoming > 0 else float("inf")
        job = JOB_BY_ID.get(profile.job_id)
        print(
            f"{profile.display_name[:18]:18s} {(job.name if job else profile.job_id)[:14]:14s} "
            f"{profile.level:3d} {rotation.dpt:9.0f} {rotation.basic_dpt:9.0f} "
            f"{rotation.skill_dpt:9.0f} {kill_turns:7.1f} {stats.final_hp:7d} "
            f"{incoming:7.0f} {survival_hits:6.1f}"
        )
        print(
            "  stats: "
            f"base_atk={stats.base_atk} atk={stats.atk:.3f} def={stats.defense:.3f} "
            f"ignore={stats.defense_ignore:.3f} amp={stats.dmg_amplification:.3f} "
            f"supp={stats.dmg_supplement:.0f} skill={stats.skill_damage:.3f} "
            f"skill_supp={stats.skill_dmg_supplement:.0f} crit={stats.critical_rate:.3f}"
        )
        item_names = [simulator.service.item_title(item) for item in simulator.service.equipped_items(profile)]
        skill_names = [skill.name for skill in simulator.service.combat_skills(profile)]
        print(f"  items: {', '.join(item_names) or '(none)'}")
        print(f"  skills: {', '.join(skill_names) or '(none)'}")
    return 0


def print_hard_boss_report(
    simulator: BalanceSimulator,
    profiles: Sequence[PlayerProfile],
    selected_profiles: Sequence[str],
    trials: int,
) -> int:
    selected = {str(value) for value in selected_profiles}
    if selected:
        profiles = [
            profile for profile in profiles
            if str(profile.user_id) in selected or profile.display_name in selected
        ]
    if not profiles:
        raise SystemExit("no matching profiles in state file")
    hard_bosses = [boss for boss in BOSSES if boss.difficulty == "hard"]
    trial_count = max(1, min(50, int(trials)))
    print(f"hard boss engine report profiles={len(profiles)} trials={trial_count}")
    print(
        f"{'boss':22s} {'profile':18s} {'win':>7s} {'turns':>7s} "
        f"{'calc':>7s} {'basic in':>9s} {'hits':>6s} {'boss left':>10s}"
    )
    print("-" * 105)
    for boss_index, boss in enumerate(hard_bosses):
        for profile_index, profile in enumerate(profiles):
            rows = [
                simulator.simulate_boss_trial(
                    profile,
                    boss.id,
                    seed=20260814 + boss_index * 1000 + profile_index * 100 + trial,
                )
                for trial in range(trial_count)
            ]
            wins = [row for row in rows if row.won]
            win_rate = len(wins) / len(rows)
            turn_text = f"{median(row.turns for row in rows):.0f}"
            boss_left = mean(row.boss_hp for row in rows if not row.won) if len(wins) < len(rows) else 0
            enemy = simulator.service._enemy_stats(boss.stats, level=boss.level_req)
            rotation = simulator.simulate_profile(profile, enemy_stats=enemy)
            stats = simulator.service.profile_stats(profile)
            incoming = simulator.service._estimated_basic_attack_damage(
                enemy,
                enemy.final_hp,
                stats,
                stats.final_hp,
                [],
            )
            calculated_turns = enemy.final_hp / rotation.dpt if rotation.dpt > 0 else float("inf")
            survival_hits = stats.final_hp / incoming if incoming > 0 else float("inf")
            print(
                f"{boss.name[:22]:22s} {profile.display_name[:18]:18s} "
                f"{win_rate:6.0%} {turn_text:>7s} {calculated_turns:7.1f} "
                f"{incoming:9.0f} {survival_hits:6.1f} {boss_left:10.0f}"
            )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = SimConfig(
        level=max(1, args.level),
        turns=max(1, args.turns),
        stars=max(0, args.stars),
        enemy_defense=args.enemy_defense,
        enemy_damage_cut=args.enemy_damage_cut,
        enemy_mitigation=args.enemy_mitigation,
        enemy_level=max(1, args.enemy_level),
        enemy_hp=max(1, args.enemy_hp),
    )
    simulator = BalanceSimulator(config)
    if args.state is not None:
        profiles = load_state_profiles(args.state)
        if args.hard_report:
            return print_hard_boss_report(
                simulator,
                profiles,
                args.profiles,
                args.trials,
            )
        return print_state_report(
            simulator,
            profiles,
            args.profiles,
            args.boss,
        )
    job_ids = list(args.jobs) if args.jobs else [
        job.id for job in JOBS
        if job.tier >= args.tier
    ]
    unknown_jobs = [job_id for job_id in job_ids if job_id not in JOB_BY_ID]
    if unknown_jobs:
        raise SystemExit(f"unknown jobs: {', '.join(unknown_jobs)}")

    results: list[BalanceResult] = []
    for job_id in job_ids:
        for set_name in args.sets:
            results.append(
                simulator.run_set(
                    job_id,
                    set_name,
                    item_candidates=args.item_candidates,
                    skill_candidates=args.skill_candidates,
                )
            )

    baselines = {
        result.job_id: result.dpt
        for result in results
        if result.set_name == "epic"
    }
    print(
        f"level={config.level} turns={config.turns} stars={config.stars} "
        f"enemy_defense={config.enemy_defense:.2f}"
    )
    print(f"{'job':14s} {'set':12s} {'dpt':>9s} {'basic':>9s} {'skills':>9s} {'vs_epic':>8s} {'survival':>9s}")
    print("-" * 78)
    for result in sorted(results, key=lambda row: (row.job_id, row.set_name)):
        baseline = baselines.get(result.job_id)
        ratio = result.dpt / baseline if baseline else 0.0
        ratio_text = f"{ratio:.2f}" if baseline else "-"
        print(
            f"{result.job_id:14s} {result.set_name:12s} "
            f"{result.dpt:9.0f} {result.basic_dpt:9.0f} {result.skill_dpt:9.0f} "
            f"{ratio_text:>8s} {result.survival:9.0f}"
        )
        if args.details:
            items = ", ".join(result.items) if result.items else "(none)"
            skills = ", ".join(result.skills) if result.skills else "(none)"
            print(f"  items:  {items}")
            print(f"  skills: {skills}")
    return 0
