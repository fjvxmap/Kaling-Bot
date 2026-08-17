from __future__ import annotations

import unittest
from dataclasses import replace
from random import Random

from bot.cogs.rpg import RPGCog
from bot.services.rpg.data import (
    BOSS_BY_ID,
    EXPLORE_SKILL_DAMAGE_MULTIPLIER,
    JOB_BY_ID,
    SKILL_BY_ID,
    STACK_EFFECT_BY_ID,
    SelfHpCost,
)
from bot.services.rpg.manager import ActiveStackEffect, AttackOutcome, RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile
from tools.rpg_balance.simulator import BalanceSimulator, SimConfig


class _MemoryStore:
    def load_profiles(self) -> dict[int, PlayerProfile]:
        return {}

    def save_profiles(self, profiles: dict[int, PlayerProfile]) -> None:
        return None


class SarasaJobTests(unittest.TestCase):
    def service(self, seed: int = 20260817) -> RPGService:
        return RPGService(store=_MemoryStore(), rng=Random(seed))

    def geared_sarasa(self) -> PlayerProfile:
        profile = PlayerProfile.create(99, "GearedSarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_ground_zero"]
        for uid, template_id in enumerate(
            ("hrunting", "eden", "harmonia", "genesis_badge"),
            start=1,
        ):
            profile.inventory.append(
                ItemInstance(uid=uid, template_id=template_id, stars=10)
            )
            profile.equipped_item_uids.append(uid)
        profile.next_item_uid = len(profile.inventory) + 1
        return profile

    def test_job_chain_is_reachable_from_novice(self) -> None:
        service = self.service()
        profile = service.get_profile(1, "Tester")
        profile.level = 3

        self.assertIn("sarasa_1", {job.id for job in service.available_jobs(profile)})
        for level, job_id in ((3, "sarasa_1"), (10, "sarasa_2"), (25, "sarasa_3"), (50, "sarasa_4")):
            profile.level = level
            result = service.advance_job(profile.user_id, profile.display_name, job_id)
            self.assertTrue(result.ok, result.message)

        self.assertEqual(
            [job.id for job in service.job_chain(profile)],
            ["novice", "sarasa_1", "sarasa_2", "sarasa_3", "sarasa_4"],
        )
        self.assertEqual(JOB_BY_ID["sarasa_4"].name, "십천중 사라사")

        profile.level = 45
        profile.job_id = "sarasa_3"
        stage_skill_ids = {skill.id for skill in service.unlocked_skills(profile)}
        self.assertIn("sarasa_vorpal_rage", stage_skill_ids)
        self.assertIn("sarasa_berserk_forge", stage_skill_ids)
        self.assertNotIn("sarasa_ground_zero", stage_skill_ids)
        self.assertNotIn("sarasa_three_tigers_blessing", stage_skill_ids)

    def test_original_abilities_are_split_between_third_and_fourth_advancement(self) -> None:
        expected = {
            "sarasa_vorpal_rage": ("보팔 레이지", 25, ("sarasa_3",)),
            "sarasa_berserk_forge": ("베르세르크 포지", 25, ("sarasa_3",)),
            "sarasa_ground_zero": ("그라운드 제로", 50, ("sarasa_4",)),
            "sarasa_three_tigers_blessing": ("삼인의 축복", 50, ("sarasa_4",)),
        }
        for skill_id, authored in expected.items():
            skill = SKILL_BY_ID[skill_id]
            with self.subTest(skill=skill_id):
                self.assertEqual((skill.name, skill.unlock_level, skill.job_ids), authored)

        ground_zero = SKILL_BY_ID["sarasa_ground_zero"]
        berserk_forge = SKILL_BY_ID["sarasa_berserk_forge"]
        self.assertIsNone(berserk_forge.player_effects.double_strike)
        self.assertEqual(berserk_forge.hp_variants[0].player_effects.double_strike.count, 2)
        self.assertEqual(ground_zero.uses, 1)
        self.assertFalse(ground_zero.hp_scaled_damage)
        self.assertEqual((ground_zero.self_hp_cost.mode, ground_zero.self_hp_cost.value), ("set", 1))
        self.assertEqual(ground_zero.effect_actions[0].stack_effect_id, "sarasa_tiger_soul")
        last_breath = STACK_EFFECT_BY_ID["sarasa_tiger_soul"]
        self.assertEqual(last_breath.name, "잔명")
        self.assertFalse(last_breath.tiers[0].effects.invulnerability)
        last_breath_mods = {
            effect.stat: effect.value for effect in last_breath.tiers[0].stat_effects
        }
        self.assertEqual(last_breath_mods["damage_cut"], 0.35)
        self.assertEqual(last_breath_mods["life_steal"], 0.02)
        self.assertEqual(last_breath_mods["life_steal_cap"], 0.03)

        special = SKILL_BY_ID["sarasa_astro_divergence"]
        self.assertTrue(special.special)
        self.assertEqual(special.job_ids, ("sarasa_4",))
        self.assertEqual(special.cooldown, 6)
        self.assertEqual(special.self_hp_cost.value, 0.15)
        self.assertFalse(special.effect_actions[0].repeat_on_recast)

    def test_enmity_sources_stay_bounded_for_endgame_gear(self) -> None:
        final_job = JOB_BY_ID["sarasa_4"]
        self.assertEqual(final_job.stats["enmity"], 0.05)
        self.assertEqual(final_job.stats["skill_dmg_supplement"], 30)
        self.assertNotIn("atk", final_job.stats)
        progression = [JOB_BY_ID[f"sarasa_{tier}"] for tier in range(1, 5)]
        self.assertEqual(
            [job.stats["base_atk"] for job in progression],
            sorted(job.stats["base_atk"] for job in progression),
        )
        self.assertEqual(
            [job.stats["skill_dmg_supplement"] for job in progression],
            sorted(job.stats["skill_dmg_supplement"] for job in progression),
        )
        self.assertTrue(all("atk" not in job.stats for job in progression))
        self.assertEqual(SKILL_BY_ID["sarasa_faultline"].damage_multiplier, 1.25)
        self.assertEqual(SKILL_BY_ID["sarasa_fracture_line"].damage_multiplier, 1.1)
        self.assertEqual(SKILL_BY_ID["sarasa_vorpal_rage"].damage_multiplier, 1.8)
        for skill_id in (
            "sarasa_reverse_flow",
            "sarasa_enmity_form",
            "sarasa_vorpal_rage",
            "sarasa_three_tigers_blessing",
        ):
            effects = [
                effect
                for effect in SKILL_BY_ID[skill_id].player_stat_effects
                if effect.stat == "enmity"
            ]
            with self.subTest(skill=skill_id):
                self.assertEqual(len(effects), 1)
                self.assertLessEqual(effects[0].value, 0.05)
                self.assertLessEqual(effects[0].duration, 2)

    def test_discord_ability_panel_explains_the_survival_mechanic(self) -> None:
        service = self.service()
        profile = service.get_profile(98, "DiscordSarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"
        cog = RPGCog.__new__(RPGCog)
        cog.service = service

        embed = cog._ability_embed(profile)
        available_text = "\n".join(
            field.value for field in embed.fields if field.name.startswith("사용 가능")
        )

        self.assertIn("잔명", available_text)
        self.assertIn("피해를 무효화하지는 않는다", available_text)
        self.assertIn("삼인의 축복", available_text)
        self.assertIn("HP 35% 이하", available_text)
        self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))

    def test_ground_zero_pays_cost_once_and_keeps_fixed_damage_when_recast(self) -> None:
        player = CombatStats(base_atk=100, max_hp=1_000, enmity=1.0, skill_damage=0.3)
        enemy = CombatStats(base_atk=1, max_hp=100_000)
        ground_zero = SKILL_BY_ID["sarasa_ground_zero"]

        cost_service = self.service(9)
        player_effects = []
        player_stacks = []
        cost_result = cost_service._use_player_skill(
            ground_zero,
            player,
            enemy,
            1_000,
            enemy.final_hp,
            player_effects,
            [],
            player_stack_effects=player_stacks,
            enemy_stack_effects=[],
        )

        full_hp_service = self.service(9)
        full_hp_result = full_hp_service._use_player_skill(
            replace(ground_zero, self_hp_cost=SelfHpCost()),
            player,
            enemy,
            1_000,
            enemy.final_hp,
            [],
            [],
            player_stack_effects=[],
            enemy_stack_effects=[],
        )
        self.assertEqual(cost_result.self_hp_loss, 999)
        self.assertEqual(cost_result.damage, full_hp_result.damage)

        recast_service = self.service(15)
        effects = []
        stacks = []
        blessing = SKILL_BY_ID["sarasa_three_tigers_blessing"]
        recast_service._use_player_skill(
            blessing,
            player,
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        buffed_player = recast_service._stats_with_effects(player, effects, stacks)
        recast_result = recast_service._use_player_skill(
            ground_zero,
            buffed_player,
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        self.assertEqual(recast_result.activations, 2)
        self.assertEqual(recast_result.self_hp_loss, 349)
        self.assertEqual(len(recast_result.hit_damages), ground_zero.hits * 2)

    def test_existing_skills_keep_the_hp_independent_damage_formula(self) -> None:
        skill = SKILL_BY_ID["arrow_blow"]
        self.assertFalse(skill.hp_scaled_damage)
        player = CombatStats(base_atk=100, max_hp=1_000, enmity=5.0, skill_damage=0.3)
        enemy = CombatStats(base_atk=1, max_hp=100_000)

        full_hp_estimate = self.service()._estimated_skill_damage(
            skill,
            player,
            1_000,
            enemy,
            enemy.final_hp,
        )
        low_hp_estimate = self.service()._estimated_skill_damage(
            skill,
            player,
            1,
            enemy,
            enemy.final_hp,
        )
        self.assertEqual(full_hp_estimate, low_hp_estimate)

        full_hp_result = self.service(51)._use_player_skill(
            skill,
            player,
            enemy,
            1_000,
            enemy.final_hp,
            [],
            [],
        )
        low_hp_result = self.service(51)._use_player_skill(
            skill,
            player,
            enemy,
            1,
            enemy.final_hp,
            [],
            [],
        )
        self.assertEqual(full_hp_result.damage, low_hp_result.damage)

    def test_exploration_applies_self_hp_cost(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(2, "Explorer")
        profile.level = 3
        profile.job_id = "sarasa_1"
        profile.equipped_skill_ids = ["sarasa_reverse_flow"]
        initial_hp = service.profile_stats(profile).final_hp

        report = service._simulate_battle(
            profile,
            "Target",
            CombatStats(base_atk=1, max_hp=1),
        )

        expected_cost = round(initial_hp * 0.18)
        self.assertTrue(report.won)
        self.assertTrue(any("역류" in line and f"HP {expected_cost} 소모" in line for line in report.log))
        self.assertLessEqual(report.player_hp, initial_hp)

    def test_exploration_ground_zero_uses_per_hit_life_steal_caps(self) -> None:
        profile = self.geared_sarasa()
        ground_zero = SKILL_BY_ID["sarasa_ground_zero"]
        enemy = CombatStats(base_atk=1, max_hp=100_000_000, defense=0.85)

        expected_service = self.service(77)
        player_base = expected_service._player_stats(profile)
        player_effects = expected_service._permanent_effects(profile)
        player_stacks = []
        player_hp = expected_service._stats_with_effects(
            player_base,
            player_effects,
            player_stacks,
        ).final_hp
        skill_result = expected_service._use_player_skill(
            ground_zero,
            player_base,
            enemy,
            player_hp,
            enemy.final_hp,
            player_effects,
            [],
            player_stack_effects=player_stacks,
            enemy_stack_effects=[],
            skill_damage_multiplier=EXPLORE_SKILL_DAMAGE_MULTIPLIER,
        )
        active_stats = expected_service._stats_with_effects(
            player_base,
            player_effects,
            player_stacks,
        )
        active_effects = expected_service._effects_with_stacks(
            player_effects,
            player_stacks,
        )
        expected_heal = expected_service._life_steal_heal_segments(
            active_stats,
            active_effects,
            skill_result.hit_damages,
            active_stats.final_hp,
        )
        aggregate_heal = expected_service._life_steal_heal(
            active_stats,
            active_effects,
            sum(skill_result.hit_damages),
            active_stats.final_hp,
        )
        self.assertGreater(expected_heal, aggregate_heal)

        report = self.service(77)._simulate_battle(
            profile,
            "LifeStealTarget",
            replace(enemy, max_hp=skill_result.damage + 1),
        )
        ground_zero_log = next(line for line in report.log if "그라운드 제로" in line)
        self.assertIn(f"{expected_heal} 흡수", ground_zero_log)

        basic = expected_service._basic_attack(
            active_stats,
            max(1, player_hp - skill_result.self_hp_loss + expected_heal),
            enemy,
            enemy.final_hp,
            active_effects,
        )
        stack_basic_heal = expected_service._life_steal_heal_segments(
            active_stats,
            active_effects,
            basic.life_steal_segments,
            active_stats.final_hp,
        )
        base_effects = expected_service._permanent_effects(profile)
        base_stats = expected_service._stats_with_effects(player_base, base_effects, [])
        base_basic_heal = expected_service._life_steal_heal_segments(
            base_stats,
            base_effects,
            basic.life_steal_segments,
            base_stats.final_hp,
        )
        self.assertGreater(stack_basic_heal, base_basic_heal)

    def test_passive_and_axe_form_are_seeded_only_for_sarasa_chain(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(10, "Sarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"

        stacks = service.initial_player_stack_effects(profile)
        self.assertEqual(
            [(stack.template_id, stack.stacks, stack.persistent) for stack in stacks],
            [
                ("sarasa_fury", 0, True),
                ("sarasa_astral_form", 1, True),
            ],
        )
        self.assertIn(
            "sarasa_astro_divergence",
            {skill.id for skill in service.unlocked_special_skills(profile)},
        )

        profile.job_id = "hero"
        self.assertEqual(service.initial_player_stack_effects(profile), [])
        self.assertNotIn(
            "sarasa_astro_divergence",
            {skill.id for skill in service.unlocked_special_skills(profile)},
        )

    def test_post_cost_hp_variant_uses_the_exact_35_percent_boundary(self) -> None:
        service = self.service()
        player = CombatStats(base_atk=100, max_hp=1_000)
        reverse_flow = SKILL_BY_ID["sarasa_reverse_flow"]
        faultline = SKILL_BY_ID["sarasa_faultline"]

        exact = service.resolve_skill_variant(
            reverse_flow,
            service._self_hp_after_cost(reverse_flow.self_hp_cost, 530, 1_000),
            1_000,
        )
        above = service.resolve_skill_variant(
            reverse_flow,
            service._self_hp_after_cost(reverse_flow.self_hp_cost, 531, 1_000),
            1_000,
        )
        self.assertEqual(sum(effect.value for effect in exact.player_stat_effects if effect.stat == "enmity"), 0.06)
        self.assertEqual(sum(effect.value for effect in above.player_stat_effects if effect.stat == "enmity"), 0.04)
        self.assertEqual(service.resolve_skill_variant(faultline, 350, player.final_hp).hits, 4)
        self.assertEqual(service.resolve_skill_variant(faultline, 351, player.final_hp).hits, 3)

    def test_blood_path_cools_fury_by_net_two_or_three(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(11, "Cooler")
        profile.level = 50
        profile.job_id = "sarasa_4"
        player = CombatStats(base_atk=100, max_hp=1_000)
        enemy = CombatStats(base_atk=1, max_hp=100_000)
        skill = SKILL_BY_ID["sarasa_blood_path"]

        for hp, expected in ((1_000, 3), (350, 2)):
            with self.subTest(hp=hp):
                stacks = service.initial_player_stack_effects(profile)
                next(stack for stack in stacks if stack.template_id == "sarasa_fury").stacks = 5
                service._use_player_skill(
                    skill,
                    service._stats_with_effects(player, [], stacks),
                    enemy,
                    hp,
                    enemy.final_hp,
                    [],
                    [],
                    player_stack_effects=stacks,
                    enemy_stack_effects=[],
                )
                service.apply_player_stack_event(
                    stacks,
                    [],
                    objective="ability",
                    amount=1,
                    current_hp=hp,
                    max_hp=player.final_hp,
                )
                self.assertEqual(service._active_stack_count(stacks, "sarasa_fury"), expected)
                if hp == 350:
                    extra = service.apply_player_turn_end(
                        profile,
                        stacks,
                        [],
                        current_hp=350,
                        max_hp=1_000,
                    )
                    self.assertEqual(service._active_stack_count(stacks, "sarasa_fury"), 3)
                    self.assertEqual(extra, 1, "cooling below 격앙 must restore low-HP acceleration")

    def test_triple_attacks_add_one_fury_each_even_with_double_strike(self) -> None:
        service = self.service(44)
        profile = PlayerProfile.create(12, "Triple")
        profile.level = 50
        profile.job_id = "sarasa_4"
        stacks = service.initial_player_stack_effects(profile)
        effects = []
        player = CombatStats(base_atk=100, max_hp=1_000, triple_attack_rate=1.0)
        enemy = CombatStats(base_atk=1, max_hp=100_000)
        service._use_player_skill(
            SKILL_BY_ID["sarasa_berserk_forge"],
            player,
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        attack = service._basic_attack(
            service._stats_with_effects(player, effects, stacks),
            350,
            enemy,
            enemy.final_hp,
            service._effects_with_stacks(effects, stacks),
        )
        self.assertEqual(attack.triple_attacks, 2)
        service.apply_player_stack_event(
            stacks,
            [],
            objective="triple_attack",
            amount=attack.triple_attacks,
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual(service._active_stack_count(stacks, "sarasa_fury"), 2)

    def test_turn_end_gain_precedes_fury_limit_cooldown_decision(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(13, "Boundary")
        profile.level = 50
        profile.job_id = "sarasa_4"

        high_stacks = service.initial_player_stack_effects(profile)
        high_fury = next(stack for stack in high_stacks if stack.template_id == "sarasa_fury")
        high_fury.stacks = 3
        self.assertEqual(
            service.apply_player_turn_end(
                profile,
                high_stacks,
                [],
                current_hp=351,
                max_hp=1_000,
            ),
            0,
        )
        self.assertEqual(high_fury.stacks, 3)

        stacks = service.initial_player_stack_effects(profile)
        fury = next(stack for stack in stacks if stack.template_id == "sarasa_fury")
        fury.stacks = 3
        extra = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual((fury.stacks, extra), (4, 1))
        cooldowns = {"sarasa_faultline": 6, "genesis_creation_ion": 6}
        service._tick_player_cooldowns(profile, cooldowns, extra_job_reduction=extra)
        self.assertEqual(cooldowns, {"sarasa_faultline": 4, "genesis_creation_ion": 5})

        fury.stacks = 4
        extra = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual((fury.stacks, extra), (5, 0), "entering 격앙 must stop acceleration immediately")

        before = fury.stacks
        self.assertEqual(
            service.apply_player_turn_end(
                profile,
                stacks,
                [],
                current_hp=0,
                max_hp=1_000,
            ),
            0,
        )
        self.assertEqual(fury.stacks, before)

    def test_interactive_recast_adds_fury_once_per_successful_input(self) -> None:
        service = self.service()
        profile = service.get_profile(16, "Input")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = [
            "sarasa_ground_zero",
            "sarasa_three_tigers_blessing",
            "sarasa_faultline",
        ]
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            BOSS_BY_ID["guardian_angel_slime_hard"],
            profile.user_id,
            profile.display_name,
            practice=True,
        )
        self.assertIsNotNone(session, message)
        assert session is not None
        self.assertTrue(engine._start_boss_session(session, profile.user_id)[0])
        participant = session.participants[profile.user_id]

        for skill_id, expected_fury in (
            ("sarasa_ground_zero", 1),
            ("sarasa_three_tigers_blessing", 2),
            ("sarasa_faultline", 3),
        ):
            ok, message = engine._boss_use_ability(
                session,
                profile.user_id,
                profile.display_name,
                skill_id,
            )
            self.assertTrue(ok, message)
            self.assertEqual(
                service._active_stack_count(participant.player_stack_effects, "sarasa_fury"),
                expected_fury,
            )
            if skill_id == "sarasa_ground_zero":
                self.assertEqual(participant.ability_uses_left[skill_id], 0)
                ok, _message = engine._boss_use_ability(
                    session,
                    profile.user_id,
                    profile.display_name,
                    skill_id,
                )
                self.assertFalse(ok)
                self.assertEqual(
                    service._active_stack_count(
                        participant.player_stack_effects,
                        "sarasa_fury",
                    ),
                    expected_fury,
                )
        assert participant.last_damage_detail is not None
        self.assertEqual(len(participant.last_damage_detail.hit_damages), 8)

    def test_interactive_turn_end_uses_post_counter_hp_and_skips_death(self) -> None:
        service = self.service()
        profile = service.get_profile(18, "CounterBoundary")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_faultline"]
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            BOSS_BY_ID["guardian_angel_slime_hard"],
            profile.user_id,
            profile.display_name,
            practice=True,
        )
        self.assertIsNotNone(session, message)
        assert session is not None
        self.assertTrue(engine._start_boss_session(session, profile.user_id)[0])
        participant = session.participants[profile.user_id]

        target_hp = max(1, int(participant.max_hp * 0.35))
        participant.hp = target_hp + 50
        participant.ability_cooldowns["sarasa_faultline"] = 6
        outcomes = iter((
            AttackOutcome(),
            AttackOutcome(damage=50, hits=1, hit_damages=[50]),
        ))
        original_basic_attack = service._basic_attack
        service._basic_attack = lambda *_args, **_kwargs: next(outcomes)
        try:
            ok, message = engine._boss_attack(
                session,
                profile.user_id,
                profile.display_name,
            )
        finally:
            service._basic_attack = original_basic_attack
        self.assertTrue(ok, message)
        self.assertEqual(participant.hp, target_hp)
        self.assertEqual(service._active_stack_count(participant.player_stack_effects, "sarasa_fury"), 1)
        self.assertEqual(participant.ability_cooldowns["sarasa_faultline"], 4)

        fury_before_death = service._active_stack_count(participant.player_stack_effects, "sarasa_fury")
        participant.hp = 10
        participant.alive = True
        participant.ability_cooldowns["sarasa_faultline"] = 6
        outcomes = iter((
            AttackOutcome(),
            AttackOutcome(damage=10, hits=1, hit_damages=[10]),
        ))
        service._basic_attack = lambda *_args, **_kwargs: next(outcomes)
        try:
            ok, message = engine._boss_attack(
                session,
                profile.user_id,
                profile.display_name,
            )
        finally:
            service._basic_attack = original_basic_attack
        self.assertTrue(ok, message)
        self.assertFalse(participant.alive)
        self.assertEqual(
            service._active_stack_count(participant.player_stack_effects, "sarasa_fury"),
            fury_before_death,
        )
        self.assertEqual(participant.ability_cooldowns["sarasa_faultline"], 6)

    def test_exploration_and_balance_simulator_emit_the_same_player_events(self) -> None:
        profile = PlayerProfile.create(17, "Parity")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.triple_attack_rate = 1.0
        profile.equipped_skill_ids = ["sarasa_faultline"]

        service = self.service()
        explore_events: list[tuple[str, int]] = []
        original_explore_event = service.apply_player_stack_event

        def record_explore_event(player_stacks, opponent_stacks=None, **kwargs):
            explore_events.append((kwargs["objective"], kwargs.get("amount", 0)))
            return original_explore_event(player_stacks, opponent_stacks, **kwargs)

        service.apply_player_stack_event = record_explore_event
        service._simulate_battle(
            profile,
            "ParityTarget",
            CombatStats(base_atk=1, max_hp=100_000_000, defense=0.9),
        )

        simulator = BalanceSimulator(
            SimConfig(
                level=50,
                turns=2,
                stars=0,
                enemy_defense=0.9,
                enemy_damage_cut=0,
                enemy_mitigation=0,
                enemy_level=50,
                enemy_hp=100_000_000,
            )
        )
        simulator_events: list[tuple[str, int]] = []
        original_simulator_event = simulator.service.apply_player_stack_event

        def record_simulator_event(player_stacks, opponent_stacks=None, **kwargs):
            simulator_events.append((kwargs["objective"], kwargs.get("amount", 0)))
            return original_simulator_event(player_stacks, opponent_stacks, **kwargs)

        simulator.service.apply_player_stack_event = record_simulator_event
        simulator.simulate_profile(profile, [SKILL_BY_ID["sarasa_faultline"]])

        for events in (explore_events, simulator_events):
            objectives = [objective for objective, _amount in events]
            self.assertIn("ability", objectives)
            self.assertIn(("triple_attack", 1), events)
            self.assertIn("turn_end", objectives)
            self.assertLess(objectives.index("ability"), objectives.index("triple_attack"))
            self.assertLess(objectives.index("triple_attack"), objectives.index("turn_end"))

    def test_astro_recast_uses_previous_form_and_cycles_once_per_input(self) -> None:
        service = self.service(71)
        profile = PlayerProfile.create(14, "Astral")
        profile.level = 50
        profile.job_id = "sarasa_4"
        stacks = service.initial_player_stack_effects(profile)
        effects = []
        player = CombatStats(base_atk=100, max_hp=1_000, skill_damage=0.2, enmity=0.5)
        enemy = CombatStats(base_atk=1, max_hp=1_000_000)

        service._use_player_skill(
            SKILL_BY_ID["sarasa_three_tigers_blessing"],
            service._stats_with_effects(player, effects, stacks),
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        astro = SKILL_BY_ID["sarasa_astro_divergence"]
        axe_result = service._use_player_skill(
            astro,
            service._stats_with_effects(player, effects, stacks),
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        self.assertEqual((axe_result.activations, len(axe_result.hit_damages)), (2, 6))
        self.assertEqual(service._active_stack_count(stacks, "sarasa_astral_form"), 2)

        sword_result = service._use_player_skill(
            astro,
            service._stats_with_effects(player, effects, stacks),
            enemy,
            350,
            enemy.final_hp,
            effects,
            [],
            player_stack_effects=stacks,
            enemy_stack_effects=[],
        )
        self.assertGreater(sword_result.damage, axe_result.damage)
        self.assertEqual(service._active_stack_count(stacks, "sarasa_astral_form"), 1)

    def test_stack_status_exposes_signed_fury_penalties(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(15, "Status")
        profile.level = 50
        profile.job_id = "sarasa_4"
        stacks = service.initial_player_stack_effects(profile)
        cog = RPGCog.__new__(RPGCog)
        cog.service = service

        idle_text = cog._stack_effects_text(stacks)
        self.assertIn("분노 lv.0/5", idle_text)
        self.assertIn("실제 트리플 어택", idle_text)
        self.assertIn("HP 35% 이하 생존 턴 종료마다 +1", idle_text)
        next(stack for stack in stacks if stack.template_id == "sarasa_fury").stacks = 5
        danger_text = cog._stack_effects_text(stacks)
        self.assertIn("방어 감소 30.0%", danger_text)
        self.assertIn("피격 데미지 증가 12.0%", danger_text)
        self.assertIn("격앙 · 저HP 쿨타임 가속 중지", danger_text)

    def test_balance_simulation_is_repeatable_for_the_same_loadout(self) -> None:
        simulator = BalanceSimulator(
            SimConfig(
                level=50,
                turns=20,
                stars=10,
                enemy_defense=0.85,
                enemy_damage_cut=0,
                enemy_mitigation=0,
                enemy_level=50,
                enemy_hp=100_000_000,
            )
        )
        profile = self.geared_sarasa()
        skills = (
            SKILL_BY_ID["sarasa_ground_zero"],
            SKILL_BY_ID["sarasa_berserk_forge"],
            SKILL_BY_ID["sarasa_three_tigers_blessing"],
        )
        first = simulator.simulate_profile(profile, skills)
        second = simulator.simulate_profile(profile, skills)
        self.assertEqual(first, second)

    def test_interactive_boss_last_breath_reduces_but_does_not_nullify_counter(self) -> None:
        service = self.service()
        profile = service.get_profile(3, "BossTester")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_ground_zero"]

        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            BOSS_BY_ID["guardian_angel_slime_hard"],
            profile.user_id,
            profile.display_name,
            practice=True,
        )
        self.assertIsNotNone(session, message)
        assert session is not None
        ok, message = engine._start_boss_session(session, profile.user_id)
        self.assertTrue(ok, message)
        participant = session.participants[profile.user_id]
        initial_hp = participant.hp

        ok, message = engine._boss_use_ability(
            session,
            profile.user_id,
            profile.display_name,
            "sarasa_ground_zero",
        )
        self.assertTrue(ok, message)
        self.assertTrue(any(f"HP {initial_hp - 1} 소모" in line for line in session.log))
        self.assertGreater(participant.hp, 1, "Ground Zero damage should immediately feed its temporary drain")
        self.assertEqual(
            service._active_stack_count(participant.player_stack_effects, "sarasa_tiger_soul"),
            1,
        )
        protected_stats = service._stats_with_effects(
            service.profile_stats(profile),
            participant.player_effects,
            participant.player_stack_effects,
        )
        self.assertFalse(protected_stats.invulnerable)
        self.assertGreater(protected_stats.damage_cut, service.profile_stats(profile).damage_cut)

        hp_before_counter = participant.hp
        ok, message = engine._boss_attack(session, profile.user_id, profile.display_name)
        self.assertTrue(ok, message)
        self.assertLess(participant.hp, hp_before_counter)
        self.assertEqual(
            service._active_stack_count(participant.player_stack_effects, "sarasa_tiger_soul"),
            0,
        )
        after_stats = service._stats_with_effects(
            service.profile_stats(profile),
            participant.player_effects,
            participant.player_stack_effects,
        )
        self.assertFalse(after_stats.invulnerable)


if __name__ == "__main__":
    unittest.main()
