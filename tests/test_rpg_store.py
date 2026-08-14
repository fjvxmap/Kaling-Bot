from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bot.services.rpg.data import ITEM_BY_ID
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import ItemInstance, PlayerProfile
from bot.services.rpg.store import RPGStore


class RPGStoreConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "rpg_state.json"
        initial = PlayerProfile.create(1, "Tester")
        RPGStore(self.path).save_profiles({1: initial})

    def test_independent_process_snapshots_merge_unrelated_profile_changes(self) -> None:
        left_store = RPGStore(self.path)
        right_store = RPGStore(self.path)
        left = left_store.load_profiles()
        right = right_store.load_profiles()

        left[1].gold += 500
        left_store.save_profiles(left)
        right[1].exp += 75
        right_store.save_profiles(right)

        merged = RPGStore(self.path).load_profiles()[1]
        self.assertEqual(merged.gold, PlayerProfile.create(1, "Tester").gold + 500)
        self.assertEqual(merged.exp, 75)

    def test_concurrent_numeric_changes_are_combined_as_deltas(self) -> None:
        left_store = RPGStore(self.path)
        right_store = RPGStore(self.path)
        left = left_store.load_profiles()
        right = right_store.load_profiles()

        left[1].gold += 200
        right[1].gold -= 30
        left_store.save_profiles(left)
        right_store.save_profiles(right)

        merged = RPGStore(self.path).load_profiles()[1]
        self.assertEqual(merged.gold, PlayerProfile.create(1, "Tester").gold + 170)

    def test_inventory_additions_with_distinct_uids_are_preserved(self) -> None:
        left_store = RPGStore(self.path)
        right_store = RPGStore(self.path)
        left = left_store.load_profiles()
        right = right_store.load_profiles()

        left[1].inventory.append(ItemInstance(uid=10, template_id="wooden_sword"))
        right[1].inventory.append(ItemInstance(uid=20, template_id="wooden_staff"))
        left_store.save_profiles(left)
        right_store.save_profiles(right)

        merged = RPGStore(self.path).load_profiles()[1]
        self.assertEqual({item.uid for item in merged.inventory}, {10, 20})

    def test_services_allocate_collision_resistant_item_uids(self) -> None:
        left_service = RPGService(RPGStore(self.path))
        right_service = RPGService(RPGStore(self.path))
        left_profile = left_service.get_profile(1, "Tester")
        right_profile = right_service.get_profile(1, "Tester")
        template_ids = list(ITEM_BY_ID)[:2]

        left_item = left_service._grant_item(left_profile, template_ids[0])
        right_item = right_service._grant_item(right_profile, template_ids[1])
        self.assertIsNotNone(left_item)
        self.assertIsNotNone(right_item)
        self.assertNotEqual(left_item.uid, right_item.uid)
        left_service._save()
        right_service._save()

        merged = RPGStore(self.path).load_profiles()[1]
        self.assertEqual(
            {item.uid for item in merged.inventory},
            {left_item.uid, right_item.uid},
        )


if __name__ == "__main__":
    unittest.main()
