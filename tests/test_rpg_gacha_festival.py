from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from random import Random
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kaling_web.settings")

import django

django.setup()

from bot.services.rpg.data import (
    GACHA_POOLS,
    GachaEntry,
    GachaFestival,
    GachaFestivalOverride,
    GachaPool,
    _gacha_entry,
    _gacha_festival_override,
    _validate_gacha_entry,
    _validate_gacha_festival_contracts,
    _validate_gacha_festival_override,
    gacha_candidate_rarity,
    gacha_chance_percent,
    gacha_percent_weight,
)
from bot.services.rpg.manager import RPGService
from bot.services.rpg.store import RPGStore
from rpg_web.runtime import WebRPGRuntime
from rpg_web.views import _content_payload
from tools.rpg_admin.app import (
    normalize_gacha as normalize_admin_gacha,
    validate_gacha_festival_contracts as validate_admin_gacha_festival_contracts,
    validate_gacha_festival_override as validate_admin_gacha_festival_override,
)


class GachaFestivalChanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        state_path = Path(self.temp_dir.name) / "rpg_state.json"
        self.service = RPGService(RPGStore(state_path), Random(7))
        self.runtime = WebRPGRuntime(self.service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def pool(entries: list[GachaEntry]) -> GachaPool:
        return GachaPool("edge", "Edge", "", "crystal", 1, 1, entries)

    @staticmethod
    def festival(*overrides: GachaFestivalOverride) -> GachaFestival:
        return GachaFestival("edge-fes", "Edge Fes", overrides=list(overrides))

    def test_festival_chances_are_percent_points_in_every_pool_weight_unit(self) -> None:
        self.assertEqual(gacha_chance_percent(1), 1)
        self.assertEqual(gacha_chance_percent(6), 6)
        self.assertEqual(gacha_chance_percent(0.25), 0.25)

        self.assertEqual(gacha_percent_weight(6, 100), 6)
        self.assertAlmostEqual(gacha_percent_weight(6, 1), 0.06)
        self.assertEqual(gacha_percent_weight(6, 200), 12)

    def test_chance_normalization_handles_zero_invalid_and_bounds(self) -> None:
        self.assertEqual(gacha_chance_percent(0), 0)
        self.assertEqual(gacha_chance_percent(-1), 0)
        self.assertEqual(gacha_chance_percent(float("nan")), 0)
        self.assertEqual(gacha_chance_percent(150), 100)
        self.assertEqual(gacha_percent_weight(6, 0), 0)
        self.assertEqual(gacha_percent_weight(6, float("inf")), 0)

    def test_discord_and_web_festival_info_show_the_same_percent_points(self) -> None:
        pool = GACHA_POOLS[0]
        festival = GachaFestival(
            id="test-fes",
            name="Test Fes",
            overrides=[
                GachaFestivalOverride("item_rarity", "unique", 6),
                GachaFestivalOverride("item", "harmonia", 1),
            ],
        )
        self.assertEqual(
            self.runtime.engine._gacha_festival_override_text(festival.overrides[0], pool),
            "유니크 장비 6.00%",
        )
        self.assertEqual(
            self.runtime.engine._gacha_festival_override_text(festival.overrides[1], pool),
            "하르모니아 1.00%",
        )

        profile = self.service.get_profile(1, "Tester")
        with patch.object(self.service, "active_gacha_festival", return_value=festival):
            payload = _content_payload(self.runtime, profile)
        rows = payload["festival"]["overrides"]
        self.assertEqual(rows[0]["chance_percent"], 6)
        self.assertEqual(rows[1]["chance_percent"], 1)
        self.assertIn(pool.id, rows[0]["pool_ids"])
        self.assertIn(pool.id, rows[1]["pool_ids"])

        app_js = (ROOT / "web/rpg_web/static/rpg_web/app.js").read_text(encoding="utf-8")
        self.assertNotIn("(row.chance * 100).toFixed(2)", app_js)
        self.assertIn("percentPoints(chance)", app_js)

        direct_unique_pool = self.pool([
            GachaEntry("item", 50, item_ids=("harmonia",)),
            GachaEntry("item", 50, item_ids=("steel_sword",)),
        ])
        self.assertTrue(
            self.runtime.engine._gacha_festival_override_applies(
                festival.overrides[0],
                direct_unique_pool,
            )
        )

    def test_draw_math_honors_percent_points_for_ratio_and_weight_pools(self) -> None:
        festival = GachaFestival(
            id="test-fes",
            name="Test Fes",
            overrides=[
                GachaFestivalOverride("item_rarity", "unique", 6),
                GachaFestivalOverride("item", "harmonia", 1),
            ],
        )
        base_pool = GACHA_POOLS[0]
        for scale in (0.01, 1, 2):
            with self.subTest(pool_weight_scale=scale):
                pool = replace(
                    base_pool,
                    id=f"scaled-{scale}",
                    entries=[
                        replace(entry, chance=entry.chance * scale)
                        for entry in base_pool.entries
                    ],
                )
                with patch.object(self.service, "active_gacha_festival", return_value=festival):
                    options = self.service._effective_gacha_options(pool)

                total_weight = sum(option.chance for option in options)
                unique_weight = sum(
                    option.chance for option in options if option.entry.rarity == "unique"
                )
                harmonia_weight = sum(
                    option.chance for option in options if option.candidate_ids == ("harmonia",)
                )
                self.assertAlmostEqual(total_weight, 100 * scale)
                self.assertAlmostEqual(unique_weight / total_weight * 100, 6)
                self.assertAlmostEqual(harmonia_weight / total_weight * 100, 1)

    def test_duplicate_candidate_occurrences_aggregate_without_losing_entry_semantics(self) -> None:
        pool = self.pool([
            GachaEntry("item", 10, item_ids=("harmonia", "eden"), stars=1),
            GachaEntry("item", 10, item_ids=("harmonia", "blutgang"), stars=7),
            GachaEntry("item_rarity", 20, rarity="unique", stars=3),
            GachaEntry("item_rarity", 20, rarity="unique", stars=5),
            GachaEntry("item", 40, item_ids=("steel_sword",), stars=0),
        ])
        festival = self.festival(
            GachaFestivalOverride("item_rarity", "unique", 20),
            GachaFestivalOverride("item", "harmonia", 4),
        )
        self.assertEqual(_validate_gacha_festival_contracts(festival, [pool]), [])

        with patch.object(self.service, "active_gacha_festival", return_value=festival):
            options = self.service._effective_gacha_options(pool)
        total = sum(option.chance for option in options)
        harmonia = [option for option in options if option.candidate_ids == ("harmonia",)]
        unique = [
            option
            for option in options
            if gacha_candidate_rarity(option.entry, option.candidate_ids[0]) == "unique"
        ]

        self.assertAlmostEqual(total, 100)
        self.assertAlmostEqual(sum(option.chance for option in harmonia), 4)
        self.assertAlmostEqual(sum(option.chance for option in unique), 20)
        self.assertEqual({option.entry.stars for option in harmonia}, {1, 3, 5, 7})

        base_occurrence_weights = {
            id(entry): entry.chance / len(self.service._gacha_candidates(entry))
            for entry in pool.entries
        }
        allocation_ratios = {
            round(option.chance / base_occurrence_weights[id(option.entry)], 12)
            for option in harmonia
        }
        self.assertEqual(len(allocation_ratios), 1)

        material_pool = self.pool([
            GachaEntry(
                "material",
                25,
                material_ids=("crystal",),
                material_amounts={"crystal": 100},
            ),
            GachaEntry(
                "material",
                15,
                material_ids=("crystal",),
                material_amounts={"crystal": 250},
            ),
            GachaEntry("item", 60, item_ids=("steel_sword",)),
        ])
        material_festival = self.festival(
            GachaFestivalOverride("material", "crystal", 10),
        )
        with patch.object(self.service, "active_gacha_festival", return_value=material_festival):
            material_options = self.service._effective_gacha_options(material_pool)
        crystal_options = [
            option for option in material_options if option.candidate_ids == ("crystal",)
        ]
        self.assertAlmostEqual(sum(option.chance for option in crystal_options), 10)
        self.assertEqual(
            {option.entry.material_amounts["crystal"] for option in crystal_options},
            {100, 250},
        )

    def test_core_validation_rejects_impossible_festival_contracts(self) -> None:
        unique_and_rare = self.pool([
            GachaEntry("item", 50, item_ids=("harmonia", "eden")),
            GachaEntry("item", 50, item_ids=("steel_sword",)),
        ])
        cases = {
            "duplicate override": self.festival(
                GachaFestivalOverride("item", "harmonia", 4),
                GachaFestivalOverride("item", "harmonia", 5),
            ),
            "exact chances exceed": self.festival(
                GachaFestivalOverride("item_rarity", "unique", 6),
                GachaFestivalOverride("item", "harmonia", 4),
                GachaFestivalOverride("item", "eden", 4),
            ),
            "fixed chances exceed 100": self.festival(
                GachaFestivalOverride("item", "harmonia", 80),
                GachaFestivalOverride("item", "steel_sword", 30),
            ),
            "fixes every candidate but totals less than 100": self.festival(
                GachaFestivalOverride("item", "harmonia", 30),
                GachaFestivalOverride("item", "eden", 30),
                GachaFestivalOverride("item", "steel_sword", 30),
            ),
            "applies to no pool candidate": self.festival(
                GachaFestivalOverride("item", "blutgang", 5),
            ),
        }
        for expected, festival in cases.items():
            with self.subTest(expected=expected):
                errors = _validate_gacha_festival_contracts(festival, [unique_and_rare])
                self.assertTrue(any(expected in error for error in errors), errors)

        no_rarity_remainder = self.pool([
            GachaEntry("item", 50, item_ids=("harmonia",)),
            GachaEntry("item", 50, item_ids=("steel_sword",)),
        ])
        errors = _validate_gacha_festival_contracts(
            self.festival(
                GachaFestivalOverride("item_rarity", "unique", 6),
                GachaFestivalOverride("item", "harmonia", 4),
            ),
            [no_rarity_remainder],
        )
        self.assertTrue(any("has no remaining candidate" in error for error in errors), errors)

    def test_core_validation_rejects_non_finite_or_out_of_range_chances(self) -> None:
        for chance in (float("nan"), float("inf"), -0.01, 100.01):
            with self.subTest(chance=chance):
                errors = _validate_gacha_festival_override(
                    GachaFestivalOverride("item", "harmonia", chance),
                    "override",
                )
                self.assertTrue(any("between 0 and 100" in error for error in errors), errors)

        errors = _validate_gacha_entry(
            GachaEntry("item", float("nan"), item_ids=("harmonia",)),
            "entry",
        )
        self.assertTrue(any("finite and greater than 0" in error for error in errors), errors)
        errors = _validate_gacha_entry(GachaEntry("item", 1, item_ids=()), "entry")
        self.assertTrue(any("no eligible candidates" in error for error in errors), errors)
        errors = _validate_gacha_entry(
            _gacha_entry({"type": "item", "item_ids": ["harmonia"], "chance": "invalid"}),
            "entry",
        )
        self.assertTrue(any("finite and greater than 0" in error for error in errors), errors)
        errors = _validate_gacha_festival_override(
            _gacha_festival_override({"type": "item", "target_id": "harmonia", "chance": "invalid"}),
            "override",
        )
        self.assertTrue(any("between 0 and 100" in error for error in errors), errors)

    def test_admin_validator_matches_core_festival_contract_bounds(self) -> None:
        item_rows = {
            "harmonia": {"id": "harmonia", "rarity": "unique"},
            "eden": {"id": "eden", "rarity": "unique"},
            "steel_sword": {"id": "steel_sword", "rarity": "rare"},
        }
        pool = {
            "id": "edge",
            "entries": [
                {"type": "item", "item_ids": ["harmonia", "eden"], "chance": 50},
                {"type": "item", "item_ids": ["steel_sword"], "chance": 50},
            ],
        }
        festival = {
            "id": "edge-fes",
            "overrides": [
                {"type": "item_rarity", "target_id": "unique", "chance": 6},
                {"type": "item", "target_id": "harmonia", "chance": 4},
                {"type": "item", "target_id": "eden", "chance": 4},
            ],
        }
        errors: list[str] = []
        validate_admin_gacha_festival_contracts(
            festival,
            [pool],
            item_rows,
            {},
            "gacha festival edge-fes",
            errors,
        )
        self.assertTrue(any("exact chances exceed" in error for error in errors), errors)

        errors = []
        validate_admin_gacha_festival_override(
            {"type": "item", "target_id": "harmonia", "chance": 101},
            set(item_rows),
            set(),
            {"rare", "unique"},
            set(),
            "override",
            errors,
        )
        self.assertTrue(any("between 0 and 100" in error for error in errors), errors)

        raw_gacha = {
            "pools": [],
            "festivals": [{
                "id": "invalid",
                "overrides": [{"type": "item", "target_id": "harmonia", "chance": -1}],
            }],
        }
        normalize_admin_gacha(raw_gacha)
        self.assertEqual(raw_gacha["festivals"][0]["overrides"][0]["chance"], -1)


if __name__ == "__main__":
    unittest.main()
