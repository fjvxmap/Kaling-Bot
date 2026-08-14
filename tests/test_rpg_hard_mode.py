from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.services.rpg.data import (
    BOSSES,
    BOSSES_BY_BASE_ID,
    ITEM_BY_ID,
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


if __name__ == "__main__":
    unittest.main()
