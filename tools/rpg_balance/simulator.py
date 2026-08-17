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
    ITEM_BY_ID,
    ITEMS_BY_RARITY,
    JOBS,
    JOB_BY_ID,
    MAX_EQUIPPED_ITEMS,
    MAX_EQUIPPED_SKILLS,
    SKILLS,
    SkillTemplate,
)
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile


DEFAULT_SETS = ("epic", "unique", "unique-plus")
IMMORTAL_HP_BUFFER = 10**15

# Progression snapshots used by the hard-mode tuning report.  They deliberately
# stop before the current boss's drop and omit potentials, so a report cannot
# accidentally balance an encounter around rewards that require clearing it.
HARD_BOSS_STAGE_STARS = {
    "guardian_angel_slime_hard": 3,
    "lotus_hard": 3,
    "demian_hard": 3,
    "lucid_hard": 4,
    "dusk_hard": 4,
    "verus_hilla_hard": 5,
    "dunkel_hard": 5,
    "black_mage_hard": 6,
    "beelzebub_hard": 7,
    "lucilius_hard": 7,
    "first_adversary_hard": 8,
}


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
    boss_stacks: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class StageLegalLoadout:
    profile: PlayerProfile
    requested_job_id: str
    effective_job_id: str
    boss_id: str
    stars: int
    dpt: float
    survival: float
    items: tuple[str, ...]
    skills: tuple[str, ...]


def stage_legal_item_ids(boss_id: str) -> tuple[str, ...]:
    """Return gacha uniques, Twilight Mark, and only preceding hard drops."""
    hard_bosses = [boss for boss in BOSSES if boss.difficulty == "hard"]
    boss_index = next(
        (index for index, boss in enumerate(hard_bosses) if boss.id == boss_id),
        -1,
    )
    if boss_index < 0:
        raise ValueError(f"not a hard boss: {boss_id}")
    item_ids = [
        item.id
        for item in ITEM_BY_ID.values()
        if item.rarity == "unique" and not item.excluded_from_gacha
    ]
    if "twilight_mark" in ITEM_BY_ID:
        item_ids.append("twilight_mark")
    for boss in hard_bosses[:boss_index]:
        item_ids.extend(
            drop.template_id
            for drop in boss.rewards.item_drops
            if drop.template_id in ITEM_BY_ID
        )
    return tuple(dict.fromkeys(item_ids))


def stage_legal_job_id(job_id: str, level: int) -> str:
    """Resolve a requested final job to its highest level-legal ancestor."""
    job = JOB_BY_ID.get(job_id)
    if job is None:
        raise ValueError(f"unknown job: {job_id}")
    while job.level_req > level and job.parent_id:
        job = JOB_BY_ID[job.parent_id]
    if job.level_req > level:
        raise ValueError(f"job unavailable at level {level}: {job_id}")
    return job.id


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

    def stage_legal_loadout(
        self,
        job_id: str,
        boss_id: str,
        *,
        item_candidates: int = 5,
        skill_candidates: int = 6,
        candidate_trials: int = 2,
    ) -> StageLegalLoadout:
        """Build a reproducible progression-legal DPT/EHP Pareto loadout.

        Equipment is shortlisted on the DPT/EHP frontier and optional real-engine
        trials compare utility-capable DPT, sustain, and balanced 5+1 rotations.
        The stage snapshot checks class access to required debuff/dispel/clear
        tools; it intentionally does not claim current gear meets authored
        damage or hit thresholds. Candidate trials are only a selection
        heuristic; published figures require a separate five-or-more-seed run.
        """
        if job_id not in JOB_BY_ID:
            raise ValueError(f"unknown job: {job_id}")
        boss = BOSS_BY_ID.get(boss_id)
        stars = HARD_BOSS_STAGE_STARS.get(boss_id)
        if boss is None or boss.difficulty != "hard" or stars is None:
            raise ValueError(f"hard boss has no progression snapshot: {boss_id}")
        effective_job_id = stage_legal_job_id(job_id, boss.level_req)
        stage_simulator = BalanceSimulator(
            SimConfig(
                level=boss.level_req,
                turns=50,
                stars=stars,
                enemy_defense=float(boss.stats.get("defense", 0.0)),
                enemy_damage_cut=float(boss.stats.get("damage_cut", 0.0)),
                enemy_mitigation=float(boss.stats.get("dmg_mitigation", 0.0)),
                enemy_level=boss.level_req,
                enemy_hp=max(1, int(boss.stats.get("max_hp", 1))),
            )
        )
        legal_items = stage_legal_item_ids(boss_id)
        single_dpt_scores: dict[str, float] = {}
        if not legal_items:
            item_combos: list[tuple[str, ...]] = [()]
        else:
            shortlist_size = max(MAX_EQUIPPED_ITEMS, int(item_candidates))
            single_dpt_scores = {
                item_id: stage_simulator._single_item_score(effective_job_id, item_id)
                for item_id in legal_items
            }
            dpt_ranked = sorted(
                legal_items,
                key=single_dpt_scores.__getitem__,
                reverse=True,
            )[:shortlist_size]
            ehp_ranked = sorted(
                legal_items,
                key=lambda item_id: stage_simulator._survival_score(
                    stage_simulator._profile(effective_job_id, [item_id])
                ),
                reverse=True,
            )[:shortlist_size]
            item_pool = tuple(dict.fromkeys([*dpt_ranked, *ehp_ranked]))
            equipped_count = min(MAX_EQUIPPED_ITEMS, len(item_pool))
            item_combos = list(combinations(item_pool, equipped_count)) or [()]

        provisional_items = max(
            item_combos,
            key=lambda item_ids: sum(
                single_dpt_scores.get(item_id, 0.0)
                for item_id in item_ids
            ),
        )
        provisional_skills, _rotation = stage_simulator._best_rotation_for_items(
            effective_job_id,
            provisional_items,
            skill_candidates,
        )
        measured: list[tuple[float, float, tuple[str, ...]]] = []
        for item_ids in item_combos:
            profile = stage_simulator._profile(effective_job_id, item_ids)
            rotation = stage_simulator.simulate_profile(profile, provisional_skills)
            measured.append(
                (
                    rotation.dpt,
                    stage_simulator._survival_score(profile),
                    item_ids,
                )
            )

        # A DPT-descending scan produces the non-dominated DPT/EHP frontier.
        frontier: list[tuple[float, float, tuple[str, ...]]] = []
        best_survival = -1.0
        for row in sorted(measured, key=lambda value: (value[0], value[1]), reverse=True):
            if row[1] > best_survival:
                frontier.append(row)
                best_survival = row[1]
        frontier_limit = 10
        if len(frontier) > frontier_limit:
            indices = {
                round(index * (len(frontier) - 1) / (frontier_limit - 1))
                for index in range(frontier_limit)
            }
            frontier = [frontier[index] for index in sorted(indices)]

        best_choice: tuple[
            tuple[int, int, float, float],
            float,
            float,
            tuple[str, ...],
            tuple[SkillTemplate, ...],
        ] | None = None
        seed_base = 20260817 + sum(
            (index + 1) * ord(character)
            for index, character in enumerate(f"{boss_id}:{job_id}")
        )
        for _rough_dpt, _rough_survival, item_ids in frontier:
            try:
                rotation_options = stage_simulator._stage_rotation_options(
                    effective_job_id,
                    item_ids,
                    skill_candidates,
                    boss_id,
                )
            except RuntimeError:
                continue
            for skills, rotation in rotation_options:
                profile = stage_simulator._profile(effective_job_id, item_ids)
                profile.equipped_skill_ids = [skill.id for skill in skills if not skill.special]
                profile.equipped_special_skill_id = next(
                    (skill.id for skill in skills if skill.special),
                    "",
                )
                trials = [
                    stage_simulator.simulate_boss_trial(
                        profile,
                        boss_id,
                        seed=seed_base + trial,
                        max_turns=120,
                        warning_adapted=True,
                    )
                    for trial in range(max(0, int(candidate_trials)))
                ]
                if trials:
                    wins = sum(result.won for result in trials)
                    durable = sum(
                        result.won or result.player_hp > 0 or result.turns >= 35
                        for result in trials
                    )
                    progress = mean(
                        1.0 - result.boss_hp / max(1, int(boss.stats.get("max_hp", 1)))
                        for result in trials
                    )
                    longevity = mean(min(60, result.turns) for result in trials) / 60
                    win_turn_score = -mean(
                        result.turns for result in trials if result.won
                    ) / 120 if wins else 0.0
                else:
                    wins = durable = 0
                    progress = longevity = win_turn_score = 0.0
                survival = stage_simulator._survival_score(profile)
                # Durability precedes raw progress so an eyepatch glass cannon
                # that dies immediately cannot beat a viable progression set;
                # any actual clear still outranks a pure survival timeout.
                score = (
                    wins,
                    durable,
                    progress if wins else longevity,
                    win_turn_score if wins else progress,
                )
                choice = (score, rotation.dpt, survival, item_ids, skills)
                if best_choice is None or choice[0] > best_choice[0]:
                    best_choice = choice
        if best_choice is None:
            raise RuntimeError(f"no stage-legal loadout for {job_id}:{boss_id}")

        _score, dpt, survival, item_ids, skills = best_choice
        profile = stage_simulator._profile(effective_job_id, item_ids)
        profile.equipped_skill_ids = [skill.id for skill in skills if not skill.special]
        profile.equipped_special_skill_id = next(
            (skill.id for skill in skills if skill.special),
            "",
        )
        return StageLegalLoadout(
            profile=profile,
            requested_job_id=job_id,
            effective_job_id=effective_job_id,
            boss_id=boss_id,
            stars=stars,
            dpt=dpt,
            survival=survival,
            items=tuple(item_ids),
            skills=tuple(skill.id for skill in skills),
        )

    def _best_rotation_for_items(
        self,
        job_id: str,
        item_ids: Sequence[str],
        skill_candidates: int,
        *,
        boss_id: str | None = None,
    ) -> tuple[tuple[SkillTemplate, ...], RotationResult]:
        best: tuple[tuple[SkillTemplate, ...], RotationResult] | None = None
        combos = (
            self._warning_capable_skill_combos(
                job_id,
                item_ids,
                skill_candidates,
                boss_id,
            )
            if boss_id
            else self._skill_combos(job_id, item_ids, skill_candidates)
        )
        for skills in combos:
            rotation = self._simulate(job_id, item_ids, skills)
            if best is None or rotation.dpt > best[1].dpt:
                best = (tuple(skills), rotation)
        if best is None:
            suffix = f":{boss_id}" if boss_id else ""
            raise RuntimeError(f"no skill rotation for {job_id}{suffix}")
        return best

    def _stage_rotation_options(
        self,
        job_id: str,
        item_ids: Sequence[str],
        skill_candidates: int,
        boss_id: str,
    ) -> list[tuple[tuple[SkillTemplate, ...], RotationResult]]:
        combos = self._warning_capable_skill_combos(
            job_id,
            item_ids,
            skill_candidates,
            boss_id,
        )
        measured = [
            (tuple(skills), self._simulate(job_id, item_ids, skills))
            for skills in combos
        ]
        if not measured:
            raise RuntimeError(f"no stage rotation for {job_id}:{boss_id}")
        dpt_choice = max(measured, key=lambda row: row[1].dpt)
        sustain_choice = max(
            measured,
            key=lambda row: (
                sum(self._sustain_skill_score(skill) for skill in row[0]),
                row[1].dpt,
            ),
        )
        balanced_choice = max(
            measured,
            key=lambda row: row[1].dpt
            + sum(self._sustain_skill_score(skill) for skill in row[0]),
        )
        selected: list[tuple[tuple[SkillTemplate, ...], RotationResult]] = []
        seen: set[tuple[str, ...]] = set()
        for choice in (dpt_choice, sustain_choice, balanced_choice):
            skill_ids = tuple(skill.id for skill in choice[0])
            if skill_ids in seen:
                continue
            seen.add(skill_ids)
            selected.append(choice)
        return selected

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
        # Candidate order must not affect balance results. Actual hit segments
        # are sampled to model per-hit life-steal caps, so every profile run
        # starts from the same deterministic random stream.
        self.service.rng = Random(20260710)
        profile = PlayerProfile.from_dict(profile.to_dict())
        skills = tuple(skills if skills is not None else self.service.combat_skills(profile))
        base_stats = self.service._player_stats(profile)
        enemy_base = enemy_stats or self._enemy_stats()
        player_effects = self.service._permanent_effects(profile)
        enemy_effects = []
        player_stack_effects = self.service.initial_player_stack_effects(profile)
        enemy_stack_effects = []
        player_hp = self.service._stats_with_effects(
            base_stats,
            player_effects,
            player_stack_effects,
        ).final_hp
        cooldowns: dict[str, int] = {}
        uses_left = {skill.id: skill.uses for skill in skills if skill.uses > 0}
        basic_total = 0.0
        skill_total = 0.0

        def ready(skill: SkillTemplate) -> bool:
            if cooldowns.get(skill.id, 0) > 0:
                return False
            return skill.uses <= 0 or uses_left.get(skill.id, 0) > 0

        def use_skill(skill: SkillTemplate) -> None:
            nonlocal player_hp, skill_total
            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects, enemy_stack_effects)
            before_skill_hp = player_hp
            expected_damage = self.service._estimated_skill_damage(
                skill,
                player_stats,
                before_skill_hp,
                enemy_stats,
                enemy_stats.final_hp,
                self.service._effects_with_stacks(player_effects, player_stack_effects),
            )
            result = self.service._use_player_skill(
                skill,
                player_stats,
                enemy_stats,
                player_hp,
                enemy_stats.final_hp,
                player_effects,
                enemy_effects,
                player_stack_effects=player_stack_effects,
                enemy_stack_effects=enemy_stack_effects,
                ally_stack_effects=[player_stack_effects],
                opponent_stack_effects=[enemy_stack_effects],
            )
            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            skill_total += expected_damage * max(1, result.activations)
            player_hp = max(0, player_hp - result.self_hp_loss)
            life_steal_heal = self.service._life_steal_heal_segments(
                player_stats,
                self.service._effects_with_stacks(player_effects, player_stack_effects),
                result.hit_damages,
                player_stats.final_hp,
            )
            life_steal_heal = self.service.cap_ability_life_steal(
                profile,
                life_steal_heal,
                player_stats.final_hp,
            )
            player_hp = min(player_stats.final_hp, player_hp + life_steal_heal)
            before_event_max_hp = player_stats.final_hp
            self.service.apply_player_stack_event(
                player_stack_effects,
                enemy_stack_effects,
                objective="ability",
                amount=1,
                current_hp=player_hp,
                max_hp=before_event_max_hp,
            )
            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            player_hp = self.service._rescale_current_hp_for_max_change(
                player_hp,
                before_event_max_hp,
                player_stats.final_hp,
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

            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            enemy_stats = self.service._stats_with_effects(enemy_base, enemy_effects, enemy_stack_effects)
            basic_damage = self.service._estimated_basic_attack_damage(
                player_stats,
                player_hp,
                enemy_stats,
                enemy_stats.final_hp,
                self.service._effects_with_stacks(player_effects, player_stack_effects),
            )
            basic_total += basic_damage
            basic_outcome = self.service._basic_attack(
                player_stats,
                player_hp,
                enemy_stats,
                enemy_stats.final_hp,
                self.service._effects_with_stacks(player_effects, player_stack_effects),
            )
            player_hp = min(
                player_stats.final_hp,
                player_hp + self.service._life_steal_heal_segments(
                    player_stats,
                    self.service._effects_with_stacks(player_effects, player_stack_effects),
                    basic_outcome.life_steal_segments,
                    player_stats.final_hp,
                ),
            )
            before_event_max_hp = player_stats.final_hp
            self.service.apply_player_stack_event(
                player_stack_effects,
                enemy_stack_effects,
                objective="triple_attack",
                amount=basic_outcome.triple_attacks,
                current_hp=player_hp,
                max_hp=before_event_max_hp,
            )
            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            player_hp = self.service._rescale_current_hp_for_max_change(
                player_hp,
                before_event_max_hp,
                player_stats.final_hp,
            )
            turn_end_before_max_hp = player_stats.final_hp
            extra_cooldown_reduction = self.service.apply_player_turn_end(
                profile,
                player_stack_effects,
                enemy_stack_effects,
                current_hp=player_hp,
                max_hp=turn_end_before_max_hp,
            )
            player_stats = self.service._stats_with_effects(base_stats, player_effects, player_stack_effects)
            player_hp = self.service._rescale_current_hp_for_max_change(
                player_hp,
                turn_end_before_max_hp,
                player_stats.final_hp,
            )
            player_effects = self.service._tick_effects(player_effects)
            enemy_effects = self.service._tick_effects(enemy_effects)
            player_stack_effects = self.service.tick_stack_effects(player_stack_effects)
            enemy_stack_effects = self.service.tick_stack_effects(enemy_stack_effects)
            self.service._tick_player_cooldowns(
                profile,
                cooldowns,
                extra_job_reduction=extra_cooldown_reduction,
            )

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
                    self._dpt_support_score(skill),
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
                self._dpt_support_score(skill),
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

    def _warning_capable_skill_combos(
        self,
        job_id: str,
        item_ids: Sequence[str],
        candidate_count: int,
        boss_id: str,
    ) -> list[tuple[SkillTemplate, ...]]:
        requirements = self._boss_utility_requirements(boss_id)
        regular = self._skill_combos(job_id, item_ids, candidate_count)
        profile = self._profile(job_id, item_ids)
        capable_regular = [
            skills for skills in regular
            if self._skills_cover_requirements(skills, requirements)
        ]
        if capable_regular:
            return capable_regular

        skills = self._available_skills(job_id)
        base_stats = self.service._player_stats(profile)
        player_effects = self.service._permanent_effects(profile)
        enemy_base = self._enemy_stats()
        scored = sorted(
            [
                (
                    max(
                        self._dpt_support_score(skill),
                        self._skill_candidate_score(
                            skill,
                            base_stats,
                            enemy_base,
                            player_effects,
                            [],
                        ),
                    ),
                    skill,
                )
                for skill in skills
            ],
            key=lambda row: row[0],
            reverse=True,
        )
        normal_ranked = [skill for _score, skill in scored if not skill.special]
        special_ranked = [skill for _score, skill in scored if skill.special]
        normal_pool = normal_ranked[:max(MAX_EQUIPPED_SKILLS, candidate_count)]
        # Pull the best two providers for each missing utility onto the DPT
        # shortlist. This keeps the search bounded while still considering a
        # job-native option and the universal fallback.
        for requirement in sorted(requirements):
            providers = [
                skill for skill in normal_ranked
                if self._skill_utilities(skill).intersection({requirement})
            ][:2]
            for skill in providers:
                if skill not in normal_pool:
                    normal_pool.append(skill)
        for providers in (
            sorted(normal_ranked, key=lambda skill: skill.hits, reverse=True)[:3],
            sorted(
                normal_ranked,
                key=lambda skill: skill.damage_multiplier * max(1, skill.hits),
                reverse=True,
            )[:3],
            sorted(normal_ranked, key=self._sustain_skill_score, reverse=True)[:2],
        ):
            for skill in providers:
                if skill not in normal_pool:
                    normal_pool.append(skill)
        normal_pool = normal_pool[:14]
        normal_count = min(MAX_EQUIPPED_SKILLS, len(normal_pool))
        normal_combos = (
            [tuple(normal_pool)]
            if len(normal_pool) <= normal_count
            else list(combinations(normal_pool, normal_count))
        )
        special_options: list[SkillTemplate | None] = special_ranked or [None]
        result = [
            tuple([*normal, *([special] if special is not None else [])])
            for normal in normal_combos
            for special in special_options
            if self._skills_cover_requirements(
                tuple([*normal, *([special] if special is not None else [])]),
                requirements,
            )
        ]
        if not result:
            raise RuntimeError(
                f"warning utility unavailable for {job_id}:{boss_id}: "
                f"{','.join(sorted(requirements))}"
            )
        score_by_id = {skill.id: score for score, skill in scored}
        dpt_ranked_result = sorted(
            result,
            key=lambda combo: sum(score_by_id.get(skill.id, 0.0) for skill in combo),
            reverse=True,
        )
        sustain_ranked_result = sorted(
            result,
            key=lambda combo: sum(self._sustain_skill_score(skill) for skill in combo),
            reverse=True,
        )
        selected: list[tuple[SkillTemplate, ...]] = []
        seen: set[tuple[str, ...]] = set()
        for combo in [*dpt_ranked_result[:24], *sustain_ranked_result[:8]]:
            skill_ids = tuple(skill.id for skill in combo)
            if skill_ids in seen:
                continue
            seen.add(skill_ids)
            selected.append(combo)
        return selected

    @staticmethod
    def _boss_utility_requirements(boss_id: str) -> frozenset[str]:
        boss = BOSS_BY_ID[boss_id]
        return frozenset(
            objective.objective
            for warning in boss.warnings
            for objective in warning.objectives
            if objective.objective in {"debuff", "dispel", "clear_all"}
        )

    @staticmethod
    def _skill_utilities(skill: SkillTemplate) -> frozenset[str]:
        utilities: set[str] = set()
        if any(float(effect.value) < 0 for effect in skill.enemy_stat_effects) or any(
            float(value) < 0 for value in skill.enemy_mods.values()
        ):
            utilities.add("debuff")
        for action in skill.effect_actions:
            if action.action == "dispel" and action.target in {"enemy", "enemies"}:
                utilities.add("dispel")
            if action.action == "clear_all" and action.target in {"self", "ally", "allies"}:
                utilities.add("clear_all")
        return frozenset(utilities)

    @classmethod
    def _skills_cover_requirements(
        cls,
        skills: Sequence[SkillTemplate],
        requirements: frozenset[str],
    ) -> bool:
        covered = {
            utility
            for skill in skills
            for utility in cls._skill_utilities(skill)
        }
        return requirements.issubset(covered)

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
        return damage / max(1, cadence) + self._dpt_support_score(skill)

    def _available_skills(self, job_id: str) -> list[SkillTemplate]:
        chain = self._job_chain_ids(job_id)
        return [
            skill for skill in SKILLS
            if skill.unlock_level <= self.config.level
            and not skill.equipment_granted
            and (
                not skill.job_ids
                or any(skill_job_id in chain for skill_job_id in skill.job_ids)
            )
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

    def _dpt_support_score(self, skill: SkillTemplate) -> float:
        offensive_stats = {
            "base_atk",
            "atk",
            "strength",
            "enmity",
            "dmg_amplification",
            "dmg_supplement",
            "skill_damage",
            "skill_dmg_supplement",
            "critical_rate",
            "critical_damage",
            "double_attack_rate",
            "triple_attack_rate",
        }
        score = 0.0
        for effect in skill.player_stat_effects:
            if effect.stat not in offensive_stats:
                continue
            duration = self._score_duration(effect.duration)
            score += self._stat_effect_score(effect.stat, effect.value, duration)
        for effect in skill.enemy_stat_effects:
            if effect.stat not in {"defense", "damage_cut", "dmg_mitigation"}:
                continue
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
        score += sum(
            action.count * 180
            for action in skill.effect_actions
            if action.action.startswith("stack_")
        )
        return score

    @staticmethod
    def _sustain_skill_score(skill: SkillTemplate) -> float:
        weights = {
            "max_hp": 4.0,
            "hp_bonus": 700.0,
            "defense": 500.0,
            "damage_cut": 900.0,
            "garrison": 650.0,
            "dmg_mitigation": 12.0,
            "life_steal": 1_200.0,
            "life_steal_cap": 1_200.0,
            "healing_bonus": 700.0,
            "heal_cap_bonus": 700.0,
        }
        score = skill.heal_power * 1_500.0
        score += 250.0 if skill.role == "heal" else 0.0
        score += 120.0 if skill.role == "defense" else 0.0
        for effect in skill.player_stat_effects:
            score += max(0.0, effect.value) * weights.get(effect.stat, 0.0)
        for special in (skill.player_effects, skill.enemy_effects):
            score += len(special.invulnerability) * 2_000.0
            score += len(special.veil) * 450.0
            score += len(special.dispel_guard) * 350.0
        return score

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
        warning_adapted: bool = False,
        immortal_player: bool = False,
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
        if immortal_player:
            # Durability calibration must not silently turn into a survivability
            # calibration.  The production stat block stays untouched, while a
            # simulator-only HP buffer lets incoming attacks retain their real
            # damage, hit segments, stack events, and warning side effects.  HP
            # ratios used by outgoing damage remain clamped to the full-HP state.
            participant = session.participants[trial_profile.user_id]
            participant.hp = IMMORTAL_HP_BUFFER

            # Pattern application normally rescales current HP whenever an
            # effect changes max HP.  Keep that real max-HP bookkeeping, but do
            # not let it collapse the simulator-only buffer mid-action.
            def preserve_diagnostic_hp(current: object, _before_max_hp: int) -> None:
                current.max_hp = engine._participant_max_hp(current)

            engine._sync_participant_hp_from_snapshot = preserve_diagnostic_hp
            real_life_steal = engine._apply_participant_life_steal
            real_skill_heal = engine._apply_boss_skill_heal

            def preserve_after_life_steal(current: object, *args: object, **kwargs: object) -> int:
                healed = real_life_steal(current, *args, **kwargs)
                current.hp = IMMORTAL_HP_BUFFER
                return healed

            def preserve_after_skill_heal(
                current_session: object,
                current: object,
                *args: object,
                **kwargs: object,
            ) -> int:
                healed = real_skill_heal(current_session, current, *args, **kwargs)
                for member in current_session.participants.values():
                    if member.alive:
                        member.hp = IMMORTAL_HP_BUFFER
                return healed

            engine._apply_participant_life_steal = preserve_after_life_steal
            engine._apply_boss_skill_heal = preserve_after_skill_heal

        role_order = {"debuff": 0, "buff": 1, "defense": 1, "heal": 2, "attack": 3}
        actions = 0
        while not (session.completed or session.failed or session.cancelled) and actions < max_turns:
            participant = session.participants.get(trial_profile.user_id)
            if participant is None or not participant.alive:
                break
            if immortal_player:
                # End-of-turn max-HP synchronization restores the real combat
                # maximum, so renew the diagnostic buffer before every action.
                participant.hp = IMMORTAL_HP_BUFFER
            reserve_abilities = warning_adapted and self._should_reserve_for_warning(
                engine,
                session,
                participant,
            )
            skills = sorted(
                service.combat_skills(trial_profile),
                key=lambda skill: (role_order.get(skill.role, 4), skill.cooldown, skill.id),
            )
            if warning_adapted and participant.pending_warning is None:
                dispellable_boss_buff = any(
                    service._effect_active(effect)
                    and not effect.undispellable
                    and not service._is_debuff_effect(effect)
                    for effect in participant.boss_effects
                )
                if dispellable_boss_buff:
                    dispel_skill = next(
                        (
                            skill
                            for skill in skills
                            if "dispel" in self._skill_utilities(skill)
                            and participant.ability_cooldowns.get(skill.id, 0) <= 0
                            and not engine._ability_used_out(participant, skill)
                        ),
                        None,
                    )
                    if dispel_skill is not None:
                        engine._boss_use_ability(
                            session,
                            trial_profile.user_id,
                            trial_profile.display_name,
                            dispel_skill.id,
                        )
                for buff_skill in skills:
                    if participant.pending_warning is not None:
                        break
                    if buff_skill.role != "buff":
                        continue
                    if participant.ability_cooldowns.get(buff_skill.id, 0) > 0:
                        continue
                    if engine._ability_used_out(participant, buff_skill):
                        continue
                    engine._boss_use_ability(
                        session,
                        trial_profile.user_id,
                        trial_profile.display_name,
                        buff_skill.id,
                    )
            if (
                warning_adapted
                and reserve_abilities
                and participant.pending_warning is None
                and participant.hp < participant.max_hp * 0.65
            ):
                recovery_skill = next(
                    (
                        skill
                        for skill in skills
                        if skill.role in {"heal", "defense"}
                        and participant.ability_cooldowns.get(skill.id, 0) <= 0
                        and not engine._ability_used_out(participant, skill)
                    ),
                    None,
                )
                if recovery_skill is not None:
                    engine._boss_use_ability(
                        session,
                        trial_profile.user_id,
                        trial_profile.display_name,
                        recovery_skill.id,
                    )
            if warning_adapted and participant.pending_warning is not None:
                attempted_skill_ids: set[str] = set()
                while participant.pending_warning is not None:
                    ready_skills = [
                        skill
                        for skill in skills
                        if skill.id not in attempted_skill_ids
                        and participant.ability_cooldowns.get(skill.id, 0) <= 0
                        and not engine._ability_used_out(participant, skill)
                    ]
                    skill = self._best_warning_skill(
                        service,
                        trial_profile,
                        session,
                        participant,
                        ready_skills,
                    )
                    if skill is None:
                        break
                    attempted_skill_ids.add(skill.id)
                    warning_before = participant.pending_warning
                    engine._boss_use_ability(
                        session,
                        trial_profile.user_id,
                        trial_profile.display_name,
                        skill.id,
                    )
                    if session.completed or session.failed or not participant.alive:
                        break
                    if participant.pending_warning is not warning_before:
                        break
            elif not reserve_abilities:
                for skill in skills:
                    if participant.ability_cooldowns.get(skill.id, 0) > 0:
                        continue
                    if engine._ability_used_out(participant, skill):
                        continue
                    if skill.role == "heal" and participant.hp >= participant.max_hp * 0.8:
                        continue
                    warning_before = participant.pending_warning
                    engine._boss_use_ability(
                        session,
                        trial_profile.user_id,
                        trial_profile.display_name,
                        skill.id,
                    )
                    if session.completed or session.failed or not participant.alive:
                        break
                    # A tactical player stops spending cooldowns once the
                    # current warning is solved, preserving options for a
                    # queued or immediately chained warning.
                    if (
                        warning_adapted
                        and warning_before is not None
                        and participant.pending_warning is not warning_before
                    ):
                        break
            if session.completed or session.failed or not participant.alive:
                break
            warning = participant.pending_warning
            if (
                warning is not None
                and warning.remaining_turns <= 1
                and not engine._warning_complete(warning)
                and not self._normal_attack_can_progress_warning(warning)
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
            boss_stacks=tuple(sorted(
                (stack.template_id, stack.stacks)
                for stack in (participant.boss_stack_effects if participant is not None else [])
            )),
        )

    def _best_warning_skill(
        self,
        service: RPGService,
        profile: PlayerProfile,
        session: object,
        participant: object,
        skills: Sequence[SkillTemplate],
    ) -> SkillTemplate | None:
        """Spend only cooldowns that the visible warning still needs."""
        warning = getattr(participant, "pending_warning", None)
        if warning is None or not skills:
            return None
        incomplete = [
            objective
            for objective in warning.objectives
            if objective.progress < objective.required
        ]
        if not incomplete:
            return None

        player_base = service.profile_stats(profile)
        player_effects = service._effects_with_stacks(
            participant.player_effects,
            participant.player_stack_effects,
        )
        player_stats = service._stats_with_effects(
            player_base,
            participant.player_effects,
            participant.player_stack_effects,
        )
        boss_base = service._enemy_stats(session.boss.stats, level=session.boss.level_req)
        boss_stats = service._stats_with_effects(
            boss_base,
            participant.boss_effects,
            participant.boss_stack_effects,
        )
        basic_damage = service._estimated_basic_attack_damage(
            player_stats,
            participant.hp,
            boss_stats,
            session.boss_hp,
            player_effects,
        )
        flurry, actions, bonus_effects, post_attack_effects = service._attack_specials(
            player_effects
        )
        basic_hits = actions * (
            service._expected_attack_repeats(player_stats)
            * flurry
            * (1 + len(bonus_effects))
            + sum(effect.count for _source_id, effect in post_attack_effects)
        )
        remaining_turns = max(1, int(getattr(warning, "remaining_turns", 1)))
        basic_damage_capacity = basic_damage * remaining_turns * 0.8
        basic_hit_capacity = basic_hits * remaining_turns * 0.8

        ranked: list[tuple[tuple[float, float, float, float], SkillTemplate]] = []
        for skill in skills:
            utilities = self._skill_utilities(skill)
            skill_damage = service._estimated_skill_damage(
                skill,
                player_stats,
                participant.hp,
                boss_stats,
                session.boss_hp,
                player_effects,
            )
            skill_hits = max(0, int(skill.hits))
            score = 0.0
            for objective in incomplete:
                gap = max(1, objective.required - objective.progress)
                kind = objective.objective
                if kind in {"debuff", "dispel", "clear_all"} and kind in utilities:
                    score += 3.0
                elif kind == "ability":
                    score += 1.0
                elif kind == "ability_damage":
                    score += min(1.5, skill_damage / gap)
                elif kind == "damage" and gap > basic_damage_capacity:
                    score += min(1.5, skill_damage / gap)
                elif kind == "hits" and gap > basic_hit_capacity:
                    if objective.min_damage <= 0 or (
                        skill_hits > 0 and skill_damage / skill_hits >= objective.min_damage
                    ):
                        score += min(1.5, skill_hits / gap)
            if score <= 0:
                continue
            priority = (
                score,
                -float(skill.uses > 0),
                -float(skill.cooldown),
                skill_damage,
            )
            ranked.append((priority, skill))
        return max(ranked, key=lambda row: row[0])[1] if ranked else None

    @staticmethod
    def _should_reserve_for_warning(engine: object, session: object, participant: object) -> bool:
        if getattr(participant, "pending_warning", None) is not None:
            return False
        if getattr(participant, "queued_warnings", None):
            return True
        future_turn = max(1, int(getattr(participant, "turn", 1)) + 1)
        for template in getattr(getattr(session, "boss", None), "warnings", []):
            conditions = getattr(template, "activation_conditions", [])
            turn_conditions = [
                condition for condition in conditions
                if getattr(condition, "kind", "") == "turn_multiple"
            ]
            if not turn_conditions or not all(
                future_turn % max(1, int(getattr(condition, "multiple", 1) or 1)) == 0
                for condition in turn_conditions
            ):
                continue
            if all(
                getattr(condition, "kind", "") == "turn_multiple"
                or engine._warning_activation_condition_met(session, participant, condition)
                for condition in conditions
            ):
                return True
        if not engine._boss_has_ct_system(session):
            return False
        ct_max = engine._current_ct_max(session)
        # The stage report models a cautious solo player: CT candidates are not
        # known until they appear, so spending a long cooldown between gauges
        # can make a one-turn utility/hit check impossible by construction.
        # Hold the bar while no warning is active and spend only what the
        # revealed warning needs; the normal attack still advances damage/CT.
        return ct_max > 0

    @staticmethod
    def _normal_attack_can_progress_warning(warning: object) -> bool:
        attack_objectives = {
            "damage",
            "hits",
            "triple_attack",
            "double_attack",
        }
        incomplete = [
            objective
            for objective in getattr(warning, "objectives", [])
            if objective.progress < objective.required
        ]
        if not incomplete or any(
            objective.objective not in attack_objectives
            for objective in incomplete
        ):
            return False
        for objective in incomplete:
            if objective.min_damage >= 9_999:
                return False
            if objective.objective == "damage" and objective.required >= 50_000:
                return False
            if objective.objective in {"hits", "triple_attack", "double_attack"} and objective.required >= 99:
                return False
        return True


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
    parser.add_argument(
        "--stage-hard-report",
        action="store_true",
        help="Build progression-legal profiles and run every hard boss through the live engine.",
    )
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


def print_stage_hard_boss_report(
    simulator: BalanceSimulator,
    job_ids: Sequence[str],
    trials: int,
    *,
    details: bool,
) -> int:
    hard_bosses = [boss for boss in BOSSES if boss.difficulty == "hard"]
    trial_count = max(5, min(50, int(trials)))
    print(
        f"stage-legal hard boss report jobs={len(job_ids)} trials={trial_count} "
        "potential=none skills=warning-utility-aware pilot=warning-adapted"
    )
    print(
        f"{'boss':24s} {'star':>4s} {'win':>7s} {'win med':>8s} "
        f"{'all med':>8s} {'alive':>7s} {'boss left':>10s}"
    )
    print("-" * 82)
    for boss_index, boss in enumerate(hard_bosses):
        boss_results: list[BossTrialResult] = []
        detail_rows = []
        for job_index, job_id in enumerate(job_ids):
            loadout = simulator.stage_legal_loadout(job_id, boss.id)
            rows = [
                simulator.simulate_boss_trial(
                    loadout.profile,
                    boss.id,
                    seed=20260817 + boss_index * 1000 + job_index * 100 + trial,
                    max_turns=120,
                    warning_adapted=True,
                )
                for trial in range(trial_count)
            ]
            boss_results.extend(rows)
            wins = [row for row in rows if row.won]
            detail_rows.append((job_id, loadout, rows, wins))
        wins = [row for row in boss_results if row.won]
        win_median = f"{median(row.turns for row in wins):.0f}" if wins else "-"
        boss_left = mean(row.boss_hp for row in boss_results if not row.won) if len(wins) < len(boss_results) else 0
        print(
            f"{boss.id[:24]:24s} {HARD_BOSS_STAGE_STARS[boss.id]:4d} "
            f"{len(wins) / max(1, len(boss_results)):6.0%} {win_median:>8s} "
            f"{median(row.turns for row in boss_results):8.0f} "
            f"{sum(row.player_hp > 0 for row in boss_results) / max(1, len(boss_results)):6.0%} "
            f"{boss_left:10.0f}"
        )
        if details:
            for job_id, loadout, rows, job_wins in detail_rows:
                turn_text = f"{median(row.turns for row in job_wins):.0f}" if job_wins else "-"
                print(
                    f"  {job_id:14s}->{loadout.effective_job_id:14s} "
                    f"win={len(job_wins)}/{len(rows)} med={turn_text:>3s} "
                    f"dpt={loadout.dpt:7.0f} ehp={loadout.survival:8.0f} "
                    f"items={','.join(loadout.items)} skills={','.join(loadout.skills)}"
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
    if args.stage_hard_report:
        if args.state is not None:
            raise SystemExit("--stage-hard-report uses synthetic profiles and cannot be combined with --state")
        job_ids = list(args.jobs) if args.jobs else [
            job.id for job in JOBS if job.tier >= args.tier
        ]
        unknown_jobs = [job_id for job_id in job_ids if job_id not in JOB_BY_ID]
        if unknown_jobs:
            raise SystemExit(f"unknown jobs: {', '.join(unknown_jobs)}")
        return print_stage_hard_boss_report(
            simulator,
            job_ids,
            args.trials,
            details=args.details,
        )
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
