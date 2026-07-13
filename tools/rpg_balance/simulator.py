from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import combinations
from random import Random
from typing import Iterable, Sequence

from bot.services.rpg.data import (
    ITEMS_BY_RARITY,
    JOBS,
    JOB_BY_ID,
    SKILLS,
    SkillTemplate,
)
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile


DEFAULT_SETS = ("epic", "unique", "unique-plus")


@dataclass(frozen=True)
class SimConfig:
    level: int
    turns: int
    stars: int
    enemy_defense: float
    enemy_damage_cut: float
    enemy_mitigation: float


@dataclass(frozen=True)
class BalanceResult:
    job_id: str
    job_name: str
    set_name: str
    dpt: float
    survival: float
    items: tuple[str, ...]
    skills: tuple[str, ...]


class BalanceSimulator:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.service = RPGService(rng=Random(20260710))

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
                dpt = self._simulate(job_id, item_ids, skills)
                if best is None or dpt > best.dpt:
                    profile = self._profile(job_id, item_ids)
                    best = BalanceResult(
                        job_id=job.id,
                        job_name=job.name,
                        set_name=set_name,
                        dpt=dpt,
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
    ) -> float:
        profile = self._profile(job_id, item_ids)
        base_stats = self.service._player_stats(profile)
        enemy_base = self._enemy_stats()
        player_effects = self.service._permanent_effects(profile)
        enemy_effects = []
        cooldowns: dict[str, int] = {}
        uses_left = {skill.id: skill.uses for skill in skills if skill.uses > 0}
        total = 0.0

        def ready(skill: SkillTemplate) -> bool:
            if cooldowns.get(skill.id, 0) > 0:
                return False
            return skill.uses <= 0 or uses_left.get(skill.id, 0) > 0

        def use_skill(skill: SkillTemplate) -> None:
            nonlocal total
            player_stats = self.service._stats_with_effects(base_stats, player_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects)
            total += self.service._estimated_skill_damage(
                skill,
                player_stats,
                player_stats.final_hp,
                enemy_stats,
                enemy_stats.final_hp,
                player_effects,
            )
            self.service._use_player_skill(
                skill,
                player_stats,
                enemy_stats,
                player_stats.final_hp,
                enemy_stats.final_hp,
                player_effects,
                enemy_effects,
            )
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
            total += self.service._estimated_basic_attack_damage(
                player_stats,
                player_stats.final_hp,
                enemy_stats,
                enemy_stats.final_hp,
                player_effects,
            )
            player_effects = self.service._tick_effects(player_effects)
            enemy_effects = self.service._tick_effects(enemy_effects)
            self.service._tick_cooldowns(cooldowns)

        return total / max(1, self.config.turns)

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
            self.service._estimated_skill_damage(
                skill,
                player_stats,
                player_stats.final_hp,
                enemy_stats,
                enemy_stats.final_hp,
                player_effects,
            ) + self._support_score(skill)
            for skill in self._available_skills(job_id)
        ]
        return basic + sum(sorted(skill_scores, reverse=True)[:4]) / max(1, self.config.turns)

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
                    self._skill_damage_estimate(base_stats, enemy_base, player_effects, enemy_effects, skill)
                    / max(1, self.config.turns),
                ),
                skill,
            )
            for skill in skills
        ]
        candidates = [
            skill for _score, skill
            in sorted(scored, key=lambda row: row[0], reverse=True)[:max(1, candidate_count)]
        ]
        if len(candidates) <= 4:
            return [tuple(candidates)]
        return list(combinations(candidates, 4))

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
            max_hp=10_000_000,
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
    parser.add_argument("--details", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = SimConfig(
        level=max(1, args.level),
        turns=max(1, args.turns),
        stars=max(0, args.stars),
        enemy_defense=args.enemy_defense,
        enemy_damage_cut=args.enemy_damage_cut,
        enemy_mitigation=args.enemy_mitigation,
    )
    job_ids = list(args.jobs) if args.jobs else [
        job.id for job in JOBS
        if job.tier >= args.tier
    ]
    unknown_jobs = [job_id for job_id in job_ids if job_id not in JOB_BY_ID]
    if unknown_jobs:
        raise SystemExit(f"unknown jobs: {', '.join(unknown_jobs)}")

    simulator = BalanceSimulator(config)
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
    print(f"{'job':14s} {'set':12s} {'dpt':>9s} {'vs_epic':>8s} {'survival':>9s}")
    print("-" * 58)
    for result in sorted(results, key=lambda row: (row.job_id, row.set_name)):
        baseline = baselines.get(result.job_id)
        ratio = result.dpt / baseline if baseline else 0.0
        ratio_text = f"{ratio:.2f}" if baseline else "-"
        print(
            f"{result.job_id:14s} {result.set_name:12s} "
            f"{result.dpt:9.0f} {ratio_text:>8s} {result.survival:9.0f}"
        )
        if args.details:
            items = ", ".join(result.items) if result.items else "(none)"
            skills = ", ".join(result.skills) if result.skills else "(none)"
            print(f"  items:  {items}")
            print(f"  skills: {skills}")
    return 0

