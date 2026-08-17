from __future__ import annotations

import unittest
from dataclasses import replace
from random import Random
from unittest.mock import patch

from bot.cogs.rpg import RPGCog
from bot.services.rpg.data import (
    BOSS_BY_ID,
    JOB_BY_ID,
    SKILL_BY_ID,
    STACK_EFFECT_BY_ID,
    SelfHpCost,
)
from bot.services.rpg.manager import ActiveStackEffect, AttackOutcome, RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile, PotentialLine
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
        return self.add_endgame_gear(profile)

    def add_endgame_gear(self, profile: PlayerProfile) -> PlayerProfile:
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
        self.assertIsNone(
            berserk_forge.hp_variants[0].player_effects.double_strike,
            "저체력 강화도 기본 공격 행동 수를 늘려서는 안 된다",
        )
        self.assertTrue(berserk_forge.hp_variants[0].player_effects.final_damage)
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
        self.assertLessEqual(last_breath_mods["life_steal"], 0.005)
        self.assertNotIn("life_steal_cap", last_breath_mods)

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
        for skill_id in (
            "sarasa_faultline",
            "sarasa_fracture_line",
            "sarasa_vorpal_rage",
        ):
            skill = SKILL_BY_ID[skill_id]
            low_hp = skill.hp_variants[0]
            high_total = skill.damage_multiplier * skill.hits
            low_total = low_hp.damage_multiplier * low_hp.hits
            with self.subTest(low_hp_damage=skill_id):
                self.assertGreater(low_total, high_total * 1.08)
                self.assertLess(low_total, high_total * 1.12)
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

    def test_discord_ability_panel_separates_passive_and_omits_status_prose(self) -> None:
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
        passive_text = "\n".join(
            field.value for field in embed.fields if field.name.startswith("직업 패시브")
        )

        self.assertIn("괴력난신", passive_text)
        self.assertIn("잔명", available_text)
        self.assertNotIn("피해를 무효화하지", available_text)
        self.assertNotIn("무적이 아니다", available_text)
        self.assertIn("삼인의 축복", available_text)
        self.assertIn("HP 35% 이하", available_text)
        self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))

    def test_ground_zero_pays_cost_once_without_an_ability_recast(self) -> None:
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
        self.assertEqual(recast_result.activations, 1)
        self.assertEqual(recast_result.self_hp_loss, 349)
        self.assertEqual(len(recast_result.hit_damages), ground_zero.hits)

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

    def test_ground_zero_and_native_attack_chain_stays_in_low_hp_range(self) -> None:
        service = self.service(77)
        profile = service.get_profile(99, "LowHpChain")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = [
            "sarasa_ground_zero",
            "sarasa_three_tigers_blessing",
            "sarasa_faultline",
            "sarasa_fracture_line",
            "sarasa_vorpal_rage",
        ]
        profile.equipped_special_skill_id = "sarasa_astro_divergence"
        self.add_endgame_gear(profile)
        for item in profile.inventory:
            item.potential_grade = "legendary"
            item.potential_lines = [
                PotentialLine("potential_life_steal", "legendary"),
                PotentialLine("potential_life_steal_cap", "legendary"),
                PotentialLine("potential_healing_bonus", "legendary"),
            ]
        potential_stats = service.profile_stats(profile)
        self.assertGreater(potential_stats.life_steal, 0.05)
        self.assertGreater(potential_stats.life_steal_cap, 0.02)

        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            BOSS_BY_ID["first_adversary_hard"],
            profile.user_id,
            profile.display_name,
            practice=True,
        )
        self.assertIsNotNone(session, message)
        assert session is not None
        self.assertTrue(engine._start_boss_session(session, profile.user_id)[0])
        participant = session.participants[profile.user_id]

        for skill_id in (
            *profile.equipped_skill_ids,
            profile.equipped_special_skill_id,
        ):
            ok, message = engine._boss_use_ability(
                session,
                profile.user_id,
                profile.display_name,
                skill_id,
            )
            self.assertTrue(ok, message)
            self.assertLessEqual(
                participant.hp,
                int(participant.max_hp * 0.35),
                f"{skill_id} 사용 직후 잠재 흡수만으로 저체력 조건을 해제하면 안 된다",
            )

        self.assertLessEqual(
            participant.hp,
            int(participant.max_hp * 0.35),
            "그라운드 제로 뒤의 사라사 연계가 흡수만으로 저체력 조건을 해제하면 안 된다",
        )

    def test_ability_life_steal_cap_is_shared_without_capping_basic_attacks(self) -> None:
        service = self.service(78)
        profile = service.get_profile(101, "LifeStealCap")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_ground_zero"]
        self.add_endgame_gear(profile)
        for item in profile.inventory:
            item.potential_grade = "legendary"
            item.potential_lines = [
                PotentialLine("potential_life_steal", "legendary"),
                PotentialLine("potential_life_steal_cap", "legendary"),
                PotentialLine("potential_healing_bonus", "legendary"),
            ]

        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session, message = engine._create_boss_session(
            BOSS_BY_ID["first_adversary_hard"],
            profile.user_id,
            profile.display_name,
            practice=True,
        )
        self.assertIsNotNone(session, message)
        assert session is not None
        self.assertTrue(engine._start_boss_session(session, profile.user_id)[0])
        participant = session.participants[profile.user_id]
        stats = service._stats_with_effects(
            service.profile_stats(profile),
            participant.player_effects,
            participant.player_stack_effects,
        )
        segments = [100_000, 100_000]

        participant.hp = 1
        basic_heal = engine._apply_participant_life_steal(
            participant,
            stats,
            sum(segments),
            segments,
        )
        participant.hp = 1
        ability_heal = engine._apply_participant_life_steal(
            participant,
            stats,
            sum(segments),
            segments,
            ability_profile=profile,
        )
        expected_cap = int(stats.final_hp * 0.05)
        self.assertEqual(ability_heal, expected_cap)
        self.assertGreater(basic_heal, ability_heal)

        explore_service = self.service(79)
        explore_profile = explore_service.get_profile(102, "ExploreCap")
        explore_profile.level = 50
        explore_profile.job_id = "sarasa_4"
        explore_profile.equipped_skill_ids = ["sarasa_ground_zero"]
        explore_max_hp = explore_service.profile_stats(explore_profile).final_hp
        with patch.object(
            explore_service,
            "_life_steal_heal_segments",
            return_value=99_999,
        ):
            report = explore_service._simulate_battle(
                explore_profile,
                "CapTarget",
                CombatStats(base_atk=1, max_hp=1),
            )
        self.assertEqual(report.player_hp, 1 + int(explore_max_hp * 0.05))

        simulator = BalanceSimulator(
            SimConfig(
                level=50,
                turns=1,
                stars=0,
                enemy_defense=0,
                enemy_damage_cut=0,
                enemy_mitigation=0,
                enemy_level=50,
                enemy_hp=100_000_000,
            )
        )
        simulated_profile = simulator._profile("sarasa_4", ())
        original_cap = simulator.service.cap_ability_life_steal
        with (
            patch.object(
                simulator.service,
                "_life_steal_heal_segments",
                return_value=99_999,
            ) as heal_mock,
            patch.object(
                simulator.service,
                "cap_ability_life_steal",
                wraps=original_cap,
            ) as cap_mock,
        ):
            simulator.simulate_profile(
                simulated_profile,
                [SKILL_BY_ID["sarasa_ground_zero"]],
            )
        self.assertGreaterEqual(heal_mock.call_count, 2, "어빌리티와 기본 공격 흡수를 모두 계산해야 한다")
        self.assertEqual(cap_mock.call_count, 1, "어빌리티 흡수에만 패시브 상한을 적용해야 한다")

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
                ("sarasa_kotoryubi", 0, True),
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

    def test_passive_fury_cools_without_equipping_blood_path(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(11, "Cooler")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = [
            "sarasa_ground_zero",
            "sarasa_three_tigers_blessing",
            "sarasa_vorpal_rage",
            "sarasa_fracture_line",
            "sarasa_faultline",
        ]
        self.assertNotIn("sarasa_blood_path", profile.equipped_skill_ids)
        stacks = service.initial_player_stack_effects(profile)
        fury = next(stack for stack in stacks if stack.template_id == "sarasa_fury")

        for _skill_id in profile.equipped_skill_ids:
            service.apply_player_stack_event(stacks, [], objective="ability", amount=1)
        self.assertEqual(fury.stacks, 5)

        service.apply_player_stack_event(stacks, [], objective="guard", amount=1)
        self.assertEqual(fury.stacks, 3)

        extra = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=1_000,
            max_hp=1_000,
        )
        self.assertEqual((fury.stacks, extra), (2, 0))

        fury.stacks = 5
        extra = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual((fury.stacks, extra), (2, 1))

    def test_triple_attack_adds_one_fury_without_extra_basic_actions(self) -> None:
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
        self.assertEqual(attack.actions, 1)
        self.assertEqual(attack.triple_attacks, 1)
        service.apply_player_stack_event(
            stacks,
            [],
            objective="triple_attack",
            amount=attack.triple_attacks,
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual(service._active_stack_count(stacks, "sarasa_fury"), 1)

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
        self.assertEqual(high_fury.stacks, 2)

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
        self.assertEqual((fury.stacks, extra), (4, 0))
        cooldowns = {"sarasa_faultline": 6, "genesis_creation_ion": 6}
        service._tick_player_cooldowns(profile, cooldowns, extra_job_reduction=extra)
        self.assertEqual(cooldowns, {"sarasa_faultline": 5, "genesis_creation_ion": 5})

        fury.stacks = 5
        extra = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )
        self.assertEqual(
            (fury.stacks, extra),
            (2, 1),
            "격앙에서 저체력 턴을 버티면 패시브만으로 진정되고 가속이 돌아와야 한다",
        )

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

    def test_five_equipped_abilities_add_fury_once_per_successful_input(self) -> None:
        service = self.service()
        profile = service.get_profile(16, "Input")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = [
            "sarasa_ground_zero",
            "sarasa_three_tigers_blessing",
            "sarasa_vorpal_rage",
            "sarasa_fracture_line",
            "sarasa_faultline",
        ]
        self.assertNotIn("sarasa_blood_path", profile.equipped_skill_ids)
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
            ("sarasa_vorpal_rage", 3),
            ("sarasa_fracture_line", 4),
            ("sarasa_faultline", 5),
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
        self.assertEqual(len(participant.last_damage_detail.hit_damages), 4)

    def test_sarasa_skills_never_create_more_than_two_actions(self) -> None:
        service = self.service(45)
        profile = self.geared_sarasa()
        player_base = service.profile_stats(profile)
        enemy = CombatStats(base_atk=1, max_hp=1_000_000)
        low_hp = max(1, int(player_base.final_hp * 0.35))
        sarasa_skills = [
            skill
            for skill in SKILL_BY_ID.values()
            if any(job_id.startswith("sarasa_") for job_id in skill.job_ids)
        ]

        for skill in sarasa_skills:
            with self.subTest(skill=skill.id):
                self.assertIsNone(skill.player_effects.double_strike)
                self.assertTrue(
                    all(variant.player_effects.double_strike is None for variant in skill.hp_variants)
                )
                effects = service._permanent_effects(profile)
                stacks = service.initial_player_stack_effects(profile)
                result = service._use_player_skill(
                    skill,
                    service._stats_with_effects(player_base, effects, stacks),
                    enemy,
                    low_hp,
                    enemy.final_hp,
                    effects,
                    [],
                    player_stack_effects=stacks,
                    enemy_stack_effects=[],
                )
                self.assertEqual(
                    result.activations,
                    1,
                    "사라사 고유 어빌리티는 다른 어빌리티를 연쇄 재발동하면 안 된다",
                )

                attack_hp = max(1, low_hp - result.self_hp_loss)
                attack = service._basic_attack(
                    service._stats_with_effects(player_base, effects, stacks),
                    attack_hp,
                    enemy,
                    enemy.final_hp,
                    service._effects_with_stacks(effects, stacks),
                )
                self.assertLessEqual(attack.actions, 2)

        naked = PlayerProfile.create(103, "NakedSarasa")
        naked.level = 50
        naked.job_id = "sarasa_4"
        naked_base = service.profile_stats(naked)
        naked_effects = service._permanent_effects(naked)
        naked_stacks = service.initial_player_stack_effects(naked)
        next(stack for stack in naked_stacks if stack.template_id == "sarasa_fury").stacks = 5
        naked_attack = service._basic_attack(
            service._stats_with_effects(naked_base, naked_effects, naked_stacks),
            max(1, int(naked_base.final_hp * 0.35)),
            enemy,
            enemy.final_hp,
            service._effects_with_stacks(naked_effects, naked_stacks),
        )
        self.assertEqual(naked_attack.actions, 1)

        geared_effects = service._permanent_effects(profile)
        geared_stacks = service.initial_player_stack_effects(profile)
        geared_attack = service._basic_attack(
            service._stats_with_effects(player_base, geared_effects, geared_stacks),
            low_hp,
            enemy,
            enemy.final_hp,
            service._effects_with_stacks(geared_effects, geared_stacks),
        )
        self.assertEqual(geared_attack.actions, 2)

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
        self.assertEqual(participant.ability_cooldowns["sarasa_faultline"], 5)

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

    def test_astro_uses_previous_form_and_cycles_once_per_input(self) -> None:
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
        self.assertEqual((axe_result.activations, len(axe_result.hit_damages)), (1, 3))
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

    def test_stack_status_contains_only_resources_and_actual_signed_stats(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(15, "Status")
        profile.level = 50
        profile.job_id = "sarasa_4"
        stacks = service.initial_player_stack_effects(profile)
        cog = RPGCog.__new__(RPGCog)
        cog.service = service

        idle_text = cog._stack_effects_text(stacks)
        self.assertIn("분노 lv.0/5", idle_text)
        self.assertIn("방어 +8.0%", idle_text)
        self.assertIn("견수 +20.0%", idle_text)
        next(stack for stack in stacks if stack.template_id == "sarasa_fury").stacks = 5
        danger_text = cog._stack_effects_text(stacks)
        self.assertIn("방어 감소 20.0%", danger_text)
        self.assertIn("피격 데미지 증가 8.0%", danger_text)
        self.assertIn("배수 +5.0%", danger_text)
        tiger_text = cog._stack_effects_text(
            [*stacks, ActiveStackEffect("sarasa_tiger_soul", 1, turns=1)]
        )
        self.assertIn(
            "잔명 lv.1/1 · 견수 +75.0%, 피격 데미지 감소 +35.0%, 생명력 흡수 +0.5% · 1턴",
            tiger_text,
        )
        for prose in (
            "실제 트리플 어택",
            "턴 종료",
            "무적이 아니다",
            "피해를 무효화",
            "저HP 쿨타임",
        ):
            with self.subTest(prose=prose):
                self.assertNotIn(prose, idle_text)
                self.assertNotIn(prose, danger_text)
                self.assertNotIn(prose, tiger_text)

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

    def test_endgame_sarasa_is_weaker_above_threshold_and_stronger_below_it(self) -> None:
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
        sarasa_items = (
            "hrunting",
            "immortal_legacy",
            "magic_eyepatch",
            "genesis_badge",
        )
        high_profile = simulator._profile("sarasa_4", sarasa_items)
        high_skills = tuple(
            SKILL_BY_ID[skill_id]
            for skill_id in (
                "miserable_mist",
                "sarasa_faultline",
                "sarasa_fracture_line",
                "sarasa_vorpal_rage",
                "sarasa_berserk_forge",
            )
        )
        low_profile = simulator._profile("sarasa_4", sarasa_items)
        low_skills = tuple(
            SKILL_BY_ID[skill_id]
            for skill_id in (
                "miserable_mist",
                "sarasa_faultline",
                "sarasa_reverse_flow",
                "sarasa_berserk_forge",
                "sarasa_ground_zero",
                "sarasa_astro_divergence",
            )
        )
        benchmark_profile = simulator._profile(
            "bowmaster",
            ("hraesvelgr", "immortal_legacy", "magic_eyepatch", "genesis_badge"),
        )
        benchmark_skills = tuple(
            SKILL_BY_ID[skill_id]
            for skill_id in (
                "hurricane",
                "wind_arrow",
                "arrow_blow",
                "arrow_blaster",
                "miserable_mist",
                "sei_colpi",
            )
        )
        middle_profile = simulator._profile(
            "archmage_fp",
            ("ereshkigal", "immortal_legacy", "magic_eyepatch", "genesis_badge"),
        )
        middle_skills = tuple(
            SKILL_BY_ID[skill_id]
            for skill_id in (
                "flame_sweep",
                "explosion",
                "poison_mist",
                "poison_breath",
                "flame_orb",
                "high_chaser",
            )
        )

        high = simulator.simulate_profile(high_profile, high_skills).dpt
        low = simulator.simulate_profile(low_profile, low_skills).dpt
        benchmark = simulator.simulate_profile(benchmark_profile, benchmark_skills).dpt
        middle = simulator.simulate_profile(middle_profile, middle_skills).dpt

        self.assertGreater(high, middle * 0.90)
        self.assertLess(high, middle)
        self.assertGreater(low, benchmark * 1.03)
        self.assertLess(low, benchmark * 1.15)
        self.assertGreater(low, high * 1.25)
        self.assertLess(low, high * 1.50)

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
