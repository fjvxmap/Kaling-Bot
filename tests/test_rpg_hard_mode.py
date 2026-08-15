from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    BOSSES_BY_BASE_ID,
    CONTENT,
    ITEM_BY_ID,
    STACK_EFFECT_BY_ID,
    _hard_boss_raw,
)
from bot.services.rpg.manager import RPGService
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

    def test_warning_overrides_apply_without_mutating_normal_mode(self) -> None:
        raw = next(row for row in CONTENT["bosses"] if row["id"] == "guardian_angel_slime")
        raw_requirement = raw["warnings"][0]["objectives"][0]["required"]
        normal = BOSS_BY_ID["guardian_angel_slime"]
        hard = BOSS_BY_ID["guardian_angel_slime_hard"]

        self.assertEqual(normal.warning_by_id["guardian_jump"].objectives[0].required, raw_requirement)
        self.assertEqual(hard.warning_by_id["guardian_jump"].objectives[0].required, 600)
        self.assertEqual(hard.warning_by_id["guardian_jump"].pattern.damage_multiplier, 12)

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
            "guardian_angel_slime_hard": (50_000, 34, 0.25, 0),
            "lotus_hard": (68_000, 30, 0.45, 0),
            "demian_hard": (82_000, 32, 0.70, 0),
            "lucid_hard": (105_000, 28, 0.45, 0),
            "dusk_hard": (65_000, 1, 50, 30),
            "verus_hilla_hard": (120_000, 48, 0.60, 10),
            "dunkel_hard": (140_000, 48, 1.0, 0),
            "black_mage_hard": (155_000, 42, 0.85, 8),
            "beelzebub_hard": (180_000, 60, 0.75, 0),
            "lucilius_hard": (205_000, 50, 0.65, 0),
            "first_adversary_hard": (250_000, 60, 0.3, 0),
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

    def test_hard_demian_uses_slower_stigma_without_changing_normal(self) -> None:
        normal = BOSS_BY_ID["demian"]
        hard = BOSS_BY_ID["demian_hard"]
        self.assertEqual(normal.stack_effects[0].stack_effect_id, "demian_stigma")
        self.assertEqual(hard.stack_effects[0].stack_effect_id, "demian_stigma_hard")
        self.assertEqual(STACK_EFFECT_BY_ID["demian_stigma"].conditions[0].required, 400)
        self.assertEqual(STACK_EFFECT_BY_ID["demian_stigma_hard"].conditions[0].required, 2000)


if __name__ == "__main__":
    unittest.main()
