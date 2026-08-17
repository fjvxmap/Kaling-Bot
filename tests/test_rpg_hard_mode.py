from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from bot.cogs.rpg import BossParticipant, BossSession, RPGCog
from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    BOSSES_BY_BASE_ID,
    CONTENT,
    ITEM_BY_ID,
    STACK_EFFECT_BY_ID,
    _hard_boss_raw,
)
from bot.services.rpg.manager import ActiveStackEffect, RPGService
from bot.services.rpg.models import PlayerProfile
from bot.services.rpg.store import RPGStore


class HardBossTests(unittest.TestCase):
    def service(self) -> RPGService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return RPGService(store=RPGStore(Path(temp_dir.name) / "rpg_state.json"))

    def test_every_boss_family_has_normal_and_hard_variants(self) -> None:
        self.assertTrue(BOSSES_BY_BASE_ID)
        for base_id, variants in BOSSES_BY_BASE_ID.items():
            with self.subTest(base_id=base_id):
                self.assertEqual({boss.difficulty for boss in variants}, {"normal", "hard"})
                normal = next(boss for boss in variants if boss.difficulty == "normal")
                hard = next(boss for boss in variants if boss.difficulty == "hard")
                self.assertEqual(normal.id, base_id)
                self.assertEqual(hard.id, f"{base_id}_hard")
                self.assertEqual(normal.weekly_group_id, hard.weekly_group_id)
                self.assertGreater(hard.stats.get("max_hp", 0), 0)

    def test_hard_modes_reuse_the_exact_normal_description(self) -> None:
        raw_bosses = {str(row["id"]): row for row in CONTENT["bosses"]}
        for base_id, variants in BOSSES_BY_BASE_ID.items():
            normal = next(boss for boss in variants if boss.difficulty == "normal")
            hard = next(boss for boss in variants if boss.difficulty == "hard")
            with self.subTest(base_id=base_id):
                self.assertEqual(hard.description, normal.description)
                self.assertNotIn("description", raw_bosses[base_id]["hard_mode"])

    def test_normal_bosses_keep_only_twilight_mark_as_equipment_drop(self) -> None:
        normal_item_ids = {
            drop.template_id
            for boss in BOSSES
            if boss.difficulty == "normal"
            for drop in boss.rewards.item_drops
            if drop.template_id
        }
        hard_item_ids = {
            drop.template_id
            for boss in BOSSES
            if boss.difficulty == "hard"
            for drop in boss.rewards.item_drops
            if drop.template_id
        }

        self.assertEqual(normal_item_ids, {"twilight_mark"})
        self.assertNotIn("twilight_mark", hard_item_ids)
        self.assertTrue(hard_item_ids)
        self.assertTrue(hard_item_ids.issubset(ITEM_BY_ID))

    def test_gold_brick_only_drops_from_hard_bosses(self) -> None:
        normal_materials = {
            drop.id
            for boss in BOSSES
            if boss.difficulty == "normal"
            for drop in boss.rewards.material_drops
        }
        hard_materials = {
            drop.id
            for boss in BOSSES
            if boss.difficulty == "hard"
            for drop in boss.rewards.material_drops
        }

        self.assertNotIn("gold_brick", normal_materials)
        self.assertIn("gold_brick", hard_materials)

    def test_normal_and_hard_share_one_weekly_start(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        variants = next(iter(BOSSES_BY_BASE_ID.values()))
        normal = next(boss for boss in variants if boss.difficulty == "normal")
        hard = next(boss for boss in variants if boss.difficulty == "hard")

        with patch("bot.services.rpg.manager.BOSS_WEEKLY_REWARD_LIMIT_ENABLED", True):
            week_key = service.current_week_key()
            self.assertEqual(service.boss_start_remaining(profile, normal.id), 1)
            self.assertTrue(service._consume_boss_start_for_profile(profile, hard.id, week_key))
            self.assertEqual(service.boss_start_remaining(profile, normal.id), 0)
            self.assertEqual(service.boss_start_remaining(profile, hard.id), 0)
            self.assertFalse(service._consume_boss_start_for_profile(profile, normal.id, week_key))

    def test_hard_solo_clear_also_unlocks_the_base_boss_history(self) -> None:
        service = self.service()
        variants = next(iter(BOSSES_BY_BASE_ID.values()))
        normal = next(boss for boss in variants if boss.difficulty == "normal")
        hard = next(boss for boss in variants if boss.difficulty == "hard")

        service.grant_boss_reward(1, "Tester", hard.id, reward_role="owner")
        profile = service.get_profile(1, "Tester")

        self.assertIn(hard.id, profile.cleared_boss_ids)
        self.assertIn(normal.id, profile.cleared_boss_ids)
        self.assertIn(hard.id, profile.solo_cleared_boss_ids)
        self.assertIn(normal.id, profile.solo_cleared_boss_ids)

    def test_hard_bosses_use_explicit_per_warning_designs(self) -> None:
        raw_bosses = {str(row["id"]): row for row in CONTENT["bosses"]}
        for base_id, raw in raw_bosses.items():
            hard_config = raw.get("hard_mode", {})
            if not hard_config.get("enabled"):
                continue
            with self.subTest(base_id=base_id):
                self.assertNotIn("pattern_damage_multiplier", hard_config)
                self.assertNotIn("plain_damage_multiplier", hard_config)
                self.assertNotIn("objective_multiplier", hard_config)
                overrides = hard_config.get("warning_overrides", {})
                normal_warning_ids = {
                    str(warning["id"])
                    for warning in raw.get("warnings", [])
                }
                self.assertEqual(set(overrides), normal_warning_ids)
                self.assertEqual(
                    set(BOSS_BY_ID[f"{base_id}_hard"].warning_by_id),
                    normal_warning_ids,
                )
                self.assertTrue(hard_config.get("balance_notes"))

    def test_hard_offense_never_regresses_below_normal(self) -> None:
        for base_id, variants in BOSSES_BY_BASE_ID.items():
            normal = next(boss for boss in variants if boss.difficulty == "normal")
            hard = next(boss for boss in variants if boss.difficulty == "hard")
            for stat in ("base_atk", "triple_attack_rate", "double_attack_rate"):
                with self.subTest(base_id=base_id, stat=stat):
                    self.assertGreaterEqual(
                        hard.stats.get(stat, 0),
                        normal.stats.get(stat, 0),
                    )
            for warning_id, normal_warning in normal.warning_by_id.items():
                hard_warning = hard.warning_by_id[warning_id]
                if normal_warning.pattern is not None and hard_warning.pattern is not None:
                    with self.subTest(base_id=base_id, warning=warning_id):
                        self.assertGreaterEqual(
                            hard_warning.pattern.damage_multiplier,
                            normal_warning.pattern.damage_multiplier,
                        )
                        self.assertGreaterEqual(
                            hard_warning.pattern.damage_multiplier * hard_warning.pattern.hits,
                            normal_warning.pattern.damage_multiplier * normal_warning.pattern.hits,
                        )
                for index, (normal_variant, hard_variant) in enumerate(zip(
                    normal_warning.failure_variants,
                    hard_warning.failure_variants,
                )):
                    with self.subTest(base_id=base_id, warning=warning_id, variant=index):
                        self.assertGreaterEqual(
                            hard_variant.pattern.damage_multiplier,
                            normal_variant.pattern.damage_multiplier,
                        )
                        self.assertGreaterEqual(
                            hard_variant.pattern.damage_multiplier * hard_variant.pattern.hits,
                            normal_variant.pattern.damage_multiplier * normal_variant.pattern.hits,
                        )

    def test_hard_recurring_and_terminal_warnings_have_runtime_paths(self) -> None:
        recurring = {
            "guardian_angel_slime_hard": {
                "guardian_jump", "guardian_bonk", "guardian_laser",
            },
            "lotus_hard": {
                "tracking_lasers", "levitation_beam", "laser_web", "small_mechanical_arms",
            },
            "demian_hard": {
                "binding_hand", "dive", "dark_thrust", "sword_of_destruction",
                "corrupted_world_tree",
            },
            "lucid_hard": {
                "fairy_dust", "illusion_dragon", "illusion_bloom", "rend_reverie",
                "nightmare_rush",
            },
            "dusk_hard": {"tentacle_attack", "laser"},
            "verus_hilla_hard": {
                "red_thread", "fragment", "manifestation_of_desire", "altar",
                "soul_harvest", "bone_wave_a", "bone_wave_b", "the_end",
            },
            "dunkel_hard": {"swipe", "dive", "charge", "attack_up"},
            "black_mage_hard": set(BOSS_BY_ID["black_mage_hard"].warning_by_id),
            "beelzebub_hard": {"unisonic", "black_flies", "just_execution"},
            "lucilius_hard": {
                "phosphorus", "iblis", "axion", "orbital_blackness", "paradise_lost",
            },
            "first_adversary_hard": set(
                BOSS_BY_ID["first_adversary_hard"].warning_by_id
            ),
        }
        terminal_or_phase_once = {
            "lucid_hard": {"dimension_rend"},
            "dunkel_hard": {"fma"},
            "beelzebub_hard": {
                "chaoscaliber", "karma", "langelaan_field", "black_spear", "chaos_legion",
            },
            "lucilius_hard": {"axion_apocalypse", "gopherwood_ark", "the_end"},
        }
        for boss_id, expected in recurring.items():
            boss = BOSS_BY_ID[boss_id]
            ct_ids = {
                warning_id
                for rule in boss.ct_warnings
                for warning_id in rule.warning_ids
            }
            conditional_ids = {
                warning.id for warning in boss.warnings if warning.activation_conditions
            }
            linked_ids = {
                linked_id
                for warning in boss.warnings
                for linked_id in (warning.success_warning_id, warning.failure_warning_id)
                if linked_id
            }
            with self.subTest(boss=boss_id):
                self.assertTrue(expected.issubset(ct_ids | conditional_ids | linked_ids))

        for boss_id, expected in terminal_or_phase_once.items():
            boss = BOSS_BY_ID[boss_id]
            hp_ids = {warning.warning_id for warning in boss.hp_warnings}
            ct_ids = {
                warning_id
                for rule in boss.ct_warnings
                for warning_id in rule.warning_ids
            }
            with self.subTest(boss=boss_id):
                self.assertTrue(expected.issubset(hp_ids))
                self.assertTrue(expected.isdisjoint(ct_ids))

    def test_warning_overrides_apply_without_mutating_normal_mode(self) -> None:
        raw = next(row for row in CONTENT["bosses"] if row["id"] == "guardian_angel_slime")
        raw_requirement = raw["warnings"][0]["objectives"][0]["required"]
        normal = BOSS_BY_ID["guardian_angel_slime"]
        hard = BOSS_BY_ID["guardian_angel_slime_hard"]

        self.assertEqual(normal.warning_by_id["guardian_jump"].objectives[0].required, raw_requirement)
        self.assertEqual(hard.warning_by_id["guardian_jump"].objectives[0].required, 600)
        self.assertEqual(hard.warning_by_id["guardian_jump"].pattern.damage_multiplier, 10)

    def test_unknown_hard_warning_override_is_rejected(self) -> None:
        raw = deepcopy(next(row for row in CONTENT["bosses"] if row["id"] == "guardian_angel_slime"))
        raw["hard_mode"]["warning_overrides"] = {"missing_warning": {"turns": 2}}

        with self.assertRaisesRegex(ValueError, "missing_warning"):
            _hard_boss_raw(raw)

    def test_hard_hp_ladder_and_signature_mechanics_are_preserved(self) -> None:
        hard_bosses = [boss for boss in BOSSES if boss.difficulty == "hard"]
        hard_hp = [boss.stats["max_hp"] for boss in hard_bosses]
        self.assertGreaterEqual(max(hard_hp) / min(hard_hp), 5.0)
        expected_stats = {
            "guardian_angel_slime_hard": (2_400_000, 25, 0.25, 0),
            "lotus_hard": (15_000_000, 12, 0.45, 0),
            "demian_hard": (5_500_000, 15, 0.70, 0),
            "lucid_hard": (6_500_000, 10, 0.45, 0),
            "dusk_hard": (3_800_000, 1, 50, 30),
            "verus_hilla_hard": (6_600_000, 36, 0.60, 15),
            "dunkel_hard": (8_000_000, 40, 1.0, 0),
            "black_mage_hard": (10_500_000, 42, 0.85, 8),
            "beelzebub_hard": (9_000_000, 60, 0.75, 0),
            "lucilius_hard": (14_000_000, 45, 0.65, 0),
            "first_adversary_hard": (40_000_000, 75, 0.3, 0),
        }
        for boss_id, expected in expected_stats.items():
            stats = BOSS_BY_ID[boss_id].stats
            actual = (
                stats["max_hp"],
                stats["base_atk"],
                stats.get("defense", 0),
                stats.get("dmg_mitigation", 0),
            )
            with self.subTest(boss=boss_id):
                self.assertEqual(actual, expected)

        dusk = BOSS_BY_ID["dusk_hard"]
        self.assertEqual(dusk.warning_by_id["tentacle_attack"].objectives[0].required, 99)
        self.assertEqual(dusk.warning_by_id["laser"].turns, 2)
        hilla = BOSS_BY_ID["verus_hilla_hard"]
        self.assertEqual(hilla.warning_by_id["soul_harvest"].objectives[0].required, 99_999)
        self.assertEqual(hilla.warning_by_id["the_end"].objectives[0].min_damage, 9_999)
        lucilius = BOSS_BY_ID["lucilius_hard"]
        opener = next(effect for effect in lucilius.hp_effects if effect.threshold == 1.0)
        self.assertEqual(opener.pattern.plain_damage.mode, "target_max_hp_ratio")
        self.assertEqual(opener.pattern.plain_damage.value, 0.5)
        normal_opener = next(
            effect for effect in BOSS_BY_ID["lucilius"].hp_effects if effect.threshold == 1.0
        )
        self.assertEqual(normal_opener.pattern.plain_damage.mode, "flat")
        self.assertEqual(normal_opener.pattern.plain_damage.value, 600)

        normal_chaos = BOSS_BY_ID["first_adversary"].warning_by_id["element_of_chaos"]
        hard_chaos = BOSS_BY_ID["first_adversary_hard"].warning_by_id["element_of_chaos"]
        self.assertIn("triple_attack", {objective.objective for objective in normal_chaos.objectives})
        self.assertNotIn("triple_attack", {objective.objective for objective in hard_chaos.objectives})
        self.assertIn(
            ("ability", 2),
            {(objective.objective, objective.required) for objective in hard_chaos.objectives},
        )
        first = BOSS_BY_ID["first_adversary_hard"]
        spatial = first.warning_by_id["spatial_slash"].objectives[0]
        evolve = first.warning_by_id["evolve"].objectives[0]
        self.assertEqual((spatial.required, spatial.min_damage), (4, 200))
        self.assertEqual((evolve.required, evolve.min_damage), (8, 150))

        black_mage_laser = BOSS_BY_ID["black_mage_hard"].warning_by_id[
            "enhanced_destruction_laser"
        ]
        self.assertIn(
            ("ability_damage", 1200),
            {(objective.objective, objective.required) for objective in black_mage_laser.objectives},
        )
        self.assertEqual(
            BOSS_BY_ID["beelzebub_hard"].warning_by_id["chaoscaliber"].objectives[0].required,
            20,
        )
        self.assertEqual(
            BOSS_BY_ID["lucilius_hard"].warning_by_id["axion_apocalypse"].objectives[0].required,
            20,
        )

    def test_failure_variant_stack_requirements_are_reachable(self) -> None:
        for boss in BOSSES:
            for warning in boss.warnings:
                for variant in warning.failure_variants:
                    for condition in variant.conditions:
                        stack = STACK_EFFECT_BY_ID[condition.stack_effect_id]
                        with self.subTest(boss=boss.id, warning=warning.id, stack=stack.id):
                            self.assertLessEqual(condition.min_stacks, stack.max_stacks)

    def test_every_hard_boss_has_an_authored_non_stat_mechanic(self) -> None:
        expected_hard_stacks = {
            "guardian_angel_slime_hard": {"guardian_resilience_hard"},
            "lotus_hard": {"annihilation_hard"},
            "demian_hard": {"demian_stigma_hard"},
            "lucid_hard": {"phantasmal_waltz_hard"},
            "dusk_hard": {"opened_eyes_hard"},
            "verus_hilla_hard": {
                "verus_hilla_skulls_hard",
                "verus_hilla_red_thread_hard",
            },
            "dunkel_hard": {"dunkel_elite_pressure_hard"},
            "beelzebub_hard": {"trance_hard"},
            "lucilius_hard": {"evangelists_blade_hard"},
            "first_adversary_hard": {"adversary_determination_hard"},
        }
        for boss_id, stack_ids in expected_hard_stacks.items():
            boss = BOSS_BY_ID[boss_id]
            with self.subTest(boss=boss_id):
                self.assertEqual(
                    {effect.stack_effect_id for effect in boss.stack_effects},
                    stack_ids,
                )

        black_mage = BOSS_BY_ID["black_mage_hard"]
        hard_curse_ids = {
            action.stack_effect_id
            for warning in black_mage.warnings
            if warning.pattern is not None
            for action in warning.pattern.effect_actions
            if action.stack_effect_id
        }
        self.assertIn("black_mage_creation_curse_hard", hard_curse_ids)
        self.assertIn("black_mage_destruction_curse_hard", hard_curse_ids)

    def test_hard_stack_cadence_and_phase_rules_are_bespoke(self) -> None:
        guardian = STACK_EFFECT_BY_ID["guardian_resilience_hard"]
        self.assertEqual(
            [(row.objective, row.operation, row.value) for row in guardian.conditions],
            [("warning_failure", "increase", 1), ("warning_success", "decrease", 1)],
        )
        self.assertEqual(BOSS_BY_ID["guardian_angel_slime_hard"].ct_gauge[0].max, 4)

        lotus = BOSS_BY_ID["lotus_hard"]
        self.assertEqual([effect.threshold for effect in lotus.hp_effects], [0.7, 0.3])
        self.assertEqual(STACK_EFFECT_BY_ID["annihilation_hard"].conditions[0].required, 4)
        self.assertEqual(lotus.ct_gauge[0].max, 2)

        lucid = BOSS_BY_ID["lucid_hard"]
        self.assertEqual([effect.threshold for effect in lucid.hp_effects], [0.85, 0.6, 0.35])
        self.assertEqual(lucid.stack_effects[0].initial_stacks, 3)
        self.assertEqual(lucid.ct_gauge[0].max, 2)
        lucid_stack = STACK_EFFECT_BY_ID["phantasmal_waltz_hard"]
        self.assertEqual(lucid_stack.conditions[0].value, 4)
        self.assertEqual((lucid_stack.conditions[1].required, lucid_stack.conditions[1].value), (6, 1))

        dusk = BOSS_BY_ID["dusk_hard"]
        self.assertEqual(STACK_EFFECT_BY_ID["opened_eyes_hard"].max_stacks, 2)
        tentacle_turn = next(
            condition.multiple
            for condition in dusk.warning_by_id["tentacle_attack"].activation_conditions
            if condition.kind == "turn_multiple"
        )
        self.assertEqual(tentacle_turn, 5)
        self.assertFalse(
            any(
                condition.kind == "turn_multiple"
                for condition in dusk.warning_by_id["laser"].activation_conditions
            )
        )

        hilla = BOSS_BY_ID["verus_hilla_hard"]
        red_thread_action = hilla.warning_by_id["red_thread"].pattern.effect_actions[0]
        self.assertEqual((red_thread_action.stack_effect_id, red_thread_action.value), ("verus_hilla_red_thread_hard", 2))
        the_end_compare = next(
            condition.compare_stack_effect_id
            for condition in hilla.warning_by_id["the_end"].activation_conditions
            if condition.kind == "stack_compare"
        )
        self.assertEqual(the_end_compare, "verus_hilla_red_thread_hard")
        harvest_turn = next(
            condition.multiple
            for condition in hilla.warning_by_id["soul_harvest"].activation_conditions
            if condition.kind == "turn_multiple"
        )
        altar_turn = next(
            condition.multiple
            for condition in hilla.warning_by_id["altar"].activation_conditions
            if condition.kind == "turn_multiple"
        )
        self.assertEqual((harvest_turn, altar_turn), (14, 6))

        dunkel = BOSS_BY_ID["dunkel_hard"]
        self.assertEqual([effect.threshold for effect in dunkel.hp_effects], [0.75, 0.5, 0.25])
        self.assertEqual(dunkel.ct_gauge[0].max, 3)

    def test_late_hard_bosses_accelerate_their_signature_systems(self) -> None:
        black_mage = BOSS_BY_ID["black_mage_hard"]
        self.assertEqual(black_mage.ct_gauge[0].max, 3)
        expected_cycles = {
            "red_lightning": 5,
            "creation_authority": 6,
            "godlike_authority": 5,
        }
        for warning_id, expected in expected_cycles.items():
            actual = next(
                condition.multiple
                for condition in black_mage.warning_by_id[warning_id].activation_conditions
                if condition.kind == "turn_multiple"
            )
            self.assertEqual(actual, expected)
        creation = STACK_EFFECT_BY_ID["black_mage_creation_curse_hard"]
        self.assertEqual(creation.reactions[0].plain_damage.value, 0.45)
        self.assertEqual(
            creation.reactions[0].with_stack_effect_id,
            "black_mage_destruction_curse_hard",
        )

        trance = STACK_EFFECT_BY_ID["trance_hard"]
        self.assertIn(
            ("hits", "increase", 18),
            {(row.objective, row.operation, row.required) for row in trance.conditions},
        )
        self.assertEqual(
            [(rule.above, rule.max) for rule in BOSS_BY_ID["beelzebub_hard"].ct_gauge],
            [(0.5, 2), (0.0, 1)],
        )
        self.assertEqual(
            [effect.threshold for effect in BOSS_BY_ID["beelzebub_hard"].hp_effects],
            [0.75, 0.5, 0.25],
        )

        lucilius = BOSS_BY_ID["lucilius_hard"]
        self.assertEqual([effect.threshold for effect in lucilius.hp_effects], [1.0, 0.75, 0.5, 0.25])
        self.assertEqual(
            [(rule.above, rule.max) for rule in lucilius.ct_gauge],
            [(0.75, 3), (0.0, 2)],
        )

        adversary = BOSS_BY_ID["first_adversary_hard"]
        self.assertEqual(adversary.stack_effects[0].initial_stacks, 3)
        for warning_id in ("cycle_of_power_phase_1", "cycle_of_power_phase_2_3"):
            cycle = next(
                condition.multiple
                for condition in adversary.warning_by_id[warning_id].activation_conditions
                if condition.kind == "turn_multiple"
            )
            self.assertEqual(cycle, 9)
        pincer = next(
            condition.multiple
            for condition in adversary.warning_by_id["pincer_phantom"].activation_conditions
            if condition.kind == "turn_multiple"
        )
        self.assertEqual(pincer, 5)
        self.assertEqual(
            [(rule.above, rule.max) for rule in adversary.ct_gauge],
            [(0.0, 2)],
        )

    def test_first_adversary_forced_cycle_uses_post_failure_stack_variant(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        profile.level = 56
        profile.job_id = "hero"
        service._profiles[profile.user_id] = profile
        boss = BOSS_BY_ID["first_adversary_hard"]
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session = BossSession(id=1, boss=boss, owner_id=profile.user_id, practice=True)
        session.started = True
        stats = service.profile_stats(profile)
        participant = BossParticipant(
            user_id=profile.user_id,
            display_name=profile.display_name,
            level=profile.level,
            hp=stats.final_hp,
            max_hp=stats.final_hp,
            boss_stack_effects=[
                ActiveStackEffect("adversary_determination_hard", 3, persistent=True)
            ],
        )
        participant.pending_warning = engine._direct_warning(
            session,
            0,
            boss.warning_by_id["cycle_of_power_phase_1"],
        )
        session.participants[profile.user_id] = participant

        ok, _message = engine._boss_guard(session, profile.user_id, profile.display_name)

        self.assertTrue(ok)
        self.assertTrue(participant.alive)
        self.assertEqual(participant.hp, stats.final_hp - int(stats.final_hp * 0.8))
        determination = next(
            effect
            for effect in participant.boss_stack_effects
            if effect.template_id == "adversary_determination_hard"
        )
        self.assertEqual(determination.stacks, 3)
        self.assertTrue(any("의지 붕괴" in line for line in session.log))

        scattering = engine._direct_warning(
            session,
            1,
            boss.warning_by_id["scattering_arrows"],
        )
        determination.stacks = 5
        service._apply_stack_conditions(
            participant.boss_stack_effects,
            objective="warning_failure",
            amount=1,
        )
        scattering_pattern = engine._warning_failure_pattern(scattering, participant)
        self.assertEqual(determination.stacks, 3)
        self.assertEqual(scattering_pattern.hits, 7)

    def test_hard_hilla_soul_harvest_consumes_threads_and_skulls(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        profile.level = 50
        profile.job_id = "hero"
        service._profiles[profile.user_id] = profile
        boss = BOSS_BY_ID["verus_hilla_hard"]
        harvest = boss.warning_by_id["soul_harvest"]
        decrease = next(
            action
            for action in harvest.pattern.effect_actions
            if action.action == "stack_decrease"
        )
        self.assertEqual(decrease.stack_effect_id, "verus_hilla_skulls_hard")
        self.assertEqual(
            decrease.value_from_stack_effect_id,
            "verus_hilla_red_thread_hard",
        )

        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        session = BossSession(id=1, boss=boss, owner_id=profile.user_id, practice=True)
        session.started = True
        stats = service.profile_stats(profile)
        participant = BossParticipant(
            user_id=profile.user_id,
            display_name=profile.display_name,
            level=profile.level,
            hp=stats.final_hp,
            max_hp=stats.final_hp,
            boss_stack_effects=[
                ActiveStackEffect("verus_hilla_skulls_hard", 5, persistent=True),
                ActiveStackEffect("verus_hilla_red_thread_hard", 2, persistent=True),
            ],
        )
        participant.pending_warning = engine._direct_warning(session, 0, harvest)
        session.participants[profile.user_id] = participant

        ok, _message = engine._boss_guard(
            session,
            profile.user_id,
            profile.display_name,
        )

        self.assertTrue(ok)
        stacks = {
            stack.template_id: stack.stacks
            for stack in participant.boss_stack_effects
        }
        self.assertEqual(stacks.get("verus_hilla_skulls_hard"), 3)
        self.assertEqual(stacks.get("verus_hilla_red_thread_hard"), 0)

    def test_hard_stack_rules_execute_at_the_authored_cadence(self) -> None:
        service = self.service()

        guardian = [ActiveStackEffect("guardian_resilience_hard", 0, persistent=True)]
        for objective in ("warning_failure", "warning_failure", "warning_success"):
            service._apply_stack_conditions(guardian, objective=objective, amount=1)
        self.assertEqual(guardian[0].stacks, 1)

        annihilation = [ActiveStackEffect("annihilation_hard", 0, persistent=True)]
        service._apply_stack_conditions(
            annihilation,
            objective="hits",
            actor_is_holder=True,
            hit_damages=[1, 1, 1],
        )
        self.assertEqual(annihilation[0].stacks, 0)
        service._apply_stack_conditions(
            annihilation,
            objective="hits",
            actor_is_holder=True,
            hit_damages=[1],
        )
        self.assertEqual(annihilation[0].stacks, 1)
        service._apply_stack_conditions(
            annihilation,
            objective="received_damage",
            amount=1200,
            actor_is_holder=True,
        )
        self.assertEqual(annihilation[0].stacks, 0)

        stigma = [ActiveStackEffect("demian_stigma_hard", 0, persistent=True)]
        service._apply_stack_conditions(
            stigma,
            objective="damage",
            amount=1199,
            actor_is_holder=False,
        )
        self.assertEqual(stigma[0].stacks, 0)
        service._apply_stack_conditions(
            stigma,
            objective="damage",
            amount=1,
            actor_is_holder=False,
        )
        service._apply_stack_conditions(stigma, objective="warning_failure", amount=1)
        service._apply_stack_conditions(stigma, objective="warning_success", amount=1)
        self.assertEqual(stigma[0].stacks, 1)

        trance = [ActiveStackEffect("trance_hard", 0, persistent=True)]
        service._apply_stack_conditions(
            trance,
            objective="hits",
            actor_is_holder=True,
            hit_damages=[1] * 17,
        )
        self.assertEqual(trance[0].stacks, 0)
        service._apply_stack_conditions(
            trance,
            objective="hits",
            actor_is_holder=True,
            hit_damages=[1],
        )
        self.assertEqual(trance[0].stacks, 1)

    def test_hard_demian_uses_faster_stigma_without_changing_normal(self) -> None:
        normal = BOSS_BY_ID["demian"]
        hard = BOSS_BY_ID["demian_hard"]
        self.assertEqual(normal.stack_effects[0].stack_effect_id, "demian_stigma")
        self.assertEqual(hard.stack_effects[0].stack_effect_id, "demian_stigma_hard")
        self.assertEqual(STACK_EFFECT_BY_ID["demian_stigma"].conditions[0].required, 400)
        hard_stigma = STACK_EFFECT_BY_ID["demian_stigma_hard"]
        self.assertEqual(hard_stigma.conditions[0].required, 1200)
        normal_defense_penalties = [
            next(effect.value for effect in tier.stat_effects if effect.stat == "defense")
            for tier in STACK_EFFECT_BY_ID["demian_stigma"].tiers
        ]
        hard_defense_penalties = [
            next(effect.value for effect in tier.stat_effects if effect.stat == "defense")
            for tier in hard_stigma.tiers
        ]
        self.assertEqual(normal_defense_penalties[-1], -1.25)
        self.assertEqual(hard_defense_penalties, [-0.1, -0.15, -0.2, -0.25, -0.3, -0.4, -0.5])
        self.assertIn(
            ("warning_failure", "increase", 1),
            {(row.objective, row.operation, row.value) for row in hard_stigma.conditions},
        )
        self.assertEqual([effect.threshold for effect in hard.hp_effects], [0.9, 0.65, 0.4])


if __name__ == "__main__":
    unittest.main()
