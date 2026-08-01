from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from random import Random

from bot.services.rpg.data import (
    ITEM_BY_ID,
    MAX_ENHANCEMENT_STARS,
    POTENTIAL_GRADES,
    POTENTIAL_OPTION_BY_ID,
    scaled_item_stats,
)
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import ItemInstance, PlayerProfile, PotentialLine
from bot.services.rpg.store import RPGStore
from tools.rpg_admin.app import normalize_potential


class SequenceRandom:
    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


class PotentialTests(unittest.TestCase):
    def service(self, rng=None) -> RPGService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        store = RPGStore(Path(temp_dir.name) / "rpg_state.json")
        return RPGService(store=store, rng=rng)

    def test_line_grades_use_fixed_first_line_and_configured_departures(self) -> None:
        rng = SequenceRandom([0.0, 0.19, 0.0, 0.99, 0.0])
        lines = self.service(rng)._roll_potential_lines("epic")

        self.assertEqual([line.grade for line in lines], ["epic", "epic", "rare"])

    def test_rare_potential_never_rolls_normal_lines(self) -> None:
        rng = SequenceRandom([0.0, 0.0, 0.0])
        lines = self.service(rng)._roll_potential_lines("rare")

        self.assertEqual([line.grade for line in lines], ["rare", "rare", "rare"])

    def test_existing_rare_normal_lines_are_migrated(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = ItemInstance(
            uid=1,
            template_id=template_id,
            potential_grade="rare",
            potential_lines=[
                PotentialLine("potential_base_atk", "rare"),
                PotentialLine("potential_max_hp", "normal"),
                PotentialLine("potential_atk", "normal"),
            ],
        )
        option_ids = [line.option_id for line in item.potential_lines]

        service._ensure_item_potential(profile, item)

        self.assertEqual([line.grade for line in item.potential_lines], ["rare"] * 3)
        self.assertEqual([line.option_id for line in item.potential_lines], option_ids)

    def test_potential_stats_do_not_scale_with_starforce(self) -> None:
        service = self.service()
        template = next(
            template
            for template in ITEM_BY_ID.values()
            if not template.genesis_weapon
            and any(key not in template.fixed_stats and value > 0 for key, value in template.stats.items())
        )
        item = ItemInstance(
            uid=1,
            template_id=template.id,
            potential_grade="legendary",
            potential_lines=[PotentialLine("potential_base_atk", "legendary") for _ in range(3)],
        )
        potential_at_zero = service.potential_stats(item)
        base_at_zero = scaled_item_stats(template.id, item.stars)

        item.stars = MAX_ENHANCEMENT_STARS

        self.assertEqual(service.potential_stats(item), potential_at_zero)
        self.assertNotEqual(scaled_item_stats(template.id, item.stars), base_at_zero)
        self.assertEqual(
            potential_at_zero["base_atk"],
            POTENTIAL_OPTION_BY_ID["potential_base_atk"].values["legendary"] * 3,
        )

    def test_damage_supplement_potential_respects_the_player_cap(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = ItemInstance(
            uid=1,
            template_id=template_id,
            potential_grade="legendary",
            potential_lines=[
                PotentialLine("potential_dmg_supplement", "legendary") for _ in range(3)
            ],
        )
        profile.inventory = [item]
        profile.equipped_item_uids = [item.uid]

        self.assertEqual(service.profile_stats(profile).dmg_supplement, 100.0)

    def test_new_items_receive_three_potential_lines(self) -> None:
        service = self.service()
        profile = PlayerProfile.create(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )

        item = service._grant_item(profile, template_id)

        self.assertIsNotNone(item)
        assert item is not None
        self.assertIn(item.potential_grade, POTENTIAL_GRADES)
        self.assertEqual(len(item.potential_lines), 3)
        self.assertEqual(item.potential_lines[0].grade, item.potential_grade)

    def test_memorial_reroll_keeps_current_potential_until_candidate_is_applied(self) -> None:
        service = self.service(Random(1234))
        profile, _ = service.start_profile(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = service._grant_item(profile, template_id)
        assert item is not None
        profile.gold = 100_000
        before_grade = item.potential_grade
        before_lines = service._copy_potential_lines(item.potential_lines)
        gold_before = profile.gold

        result = service.reroll_potential(profile.user_id, profile.display_name, item.uid)

        self.assertTrue(result.ok)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(item.potential_grade, before_grade)
        self.assertEqual(item.potential_lines, before_lines)
        self.assertEqual(profile.gold, gold_before - result.cost)

        candidate = result.candidates[0]
        applied = service.apply_potential_candidate(
            profile.user_id,
            profile.display_name,
            item.uid,
            result.before_grade,
            result.before_lines,
            candidate,
        )

        self.assertTrue(applied.ok)
        self.assertEqual(item.potential_grade, candidate.grade)
        self.assertEqual(item.potential_lines, candidate.lines)

    def test_three_rerolls_create_three_distinct_whole_option_candidates(self) -> None:
        service = self.service(Random(5678))
        profile, _ = service.start_profile(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = service._grant_item(profile, template_id)
        assert item is not None
        profile.gold = 100_000
        cost_per_roll = service.potential_reroll_cost(item)

        result = service.reroll_potential(
            profile.user_id,
            profile.display_name,
            item.uid,
            count=3,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.cost, cost_per_roll * 3)
        self.assertEqual(len(result.candidates), 3)
        signatures = {
            service._potential_signature(candidate.grade, candidate.lines)
            for candidate in result.candidates
        }
        self.assertEqual(len(signatures), 3)
        self.assertNotIn(
            service._potential_signature(result.before_grade, result.before_lines),
            signatures,
        )
        self.assertTrue(all(len(candidate.lines) == 3 for candidate in result.candidates))

    def test_stale_memorial_result_cannot_overwrite_a_newer_choice(self) -> None:
        service = self.service(Random(9012))
        profile, _ = service.start_profile(1, "Tester")
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = service._grant_item(profile, template_id)
        assert item is not None
        profile.gold = 100_000
        first = service.reroll_potential(profile.user_id, profile.display_name, item.uid)
        second = service.reroll_potential(profile.user_id, profile.display_name, item.uid)

        applied = service.apply_potential_candidate(
            profile.user_id,
            profile.display_name,
            item.uid,
            first.before_grade,
            first.before_lines,
            first.candidates[0],
        )
        stale = service.apply_potential_candidate(
            profile.user_id,
            profile.display_name,
            item.uid,
            second.before_grade,
            second.before_lines,
            second.candidates[0],
        )

        self.assertTrue(applied.ok)
        self.assertFalse(stale.ok)
        self.assertIn("이미 변경", stale.message)

    def test_potential_lines_are_rendered_vertically(self) -> None:
        service = self.service()
        template_id = next(
            template.id for template in ITEM_BY_ID.values() if not template.genesis_weapon
        )
        item = ItemInstance(
            uid=1,
            template_id=template_id,
            potential_grade="rare",
            potential_lines=[PotentialLine("potential_base_atk", "rare") for _ in range(3)],
        )

        text = service.potential_text(item)

        self.assertEqual(len(text.splitlines()), 4)
        self.assertNotIn(" · ", text)

    def test_admin_normalization_keeps_first_line_at_one_hundred_percent(self) -> None:
        potential = {
            "grades": ["rare", "epic", "unique", "legendary"],
            "line_grades": ["normal", "rare", "epic", "unique", "legendary"],
            "initial_grade_rates": {"rare": 1.0},
            "line_same_grade_rates": [0.0, 0.2, 0.05],
            "options": [],
        }

        normalize_potential(potential, {})

        self.assertEqual(potential["line_same_grade_rates"], [1.0, 0.2, 0.05])


if __name__ == "__main__":
    unittest.main()
