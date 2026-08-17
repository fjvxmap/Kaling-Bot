from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    DAILY_EXPLORES,
    DUNGEONS,
    EXPLORE_GOLD_MULTIPLIER,
    ITEM_BY_ID,
    POTENTIAL_OPTION_BY_ID,
    REWARD_WIN_MULTIPLIER_MAX,
    REWARD_WIN_MULTIPLIER_MIN,
    SKILLS,
    star_multiplier,
)
from tools.rpg_balance.simulator import (
    HARD_BOSS_STAGE_STARS,
    BalanceSimulator,
    SimConfig,
    stage_legal_item_ids,
    stage_legal_job_id,
)


class BalancePolicyTests(unittest.TestCase):
    def test_stage_legal_hard_profiles_never_use_current_or_future_drops(self) -> None:
        ordered_ids = list(HARD_BOSS_STAGE_STARS)
        self.assertEqual(
            [HARD_BOSS_STAGE_STARS[boss_id] for boss_id in ordered_ids],
            [3, 3, 3, 4, 4, 5, 5, 6, 7, 7, 8],
        )
        guardian_drop = "guardian_angel_ring"
        lotus_drop = "loose_control_machine_mark"
        self.assertNotIn(guardian_drop, stage_legal_item_ids(ordered_ids[0]))
        self.assertIn(guardian_drop, stage_legal_item_ids(ordered_ids[1]))
        self.assertNotIn(lotus_drop, stage_legal_item_ids(ordered_ids[1]))
        self.assertIn(lotus_drop, stage_legal_item_ids(ordered_ids[2]))
        self.assertIn("twilight_mark", stage_legal_item_ids(ordered_ids[0]))
        self.assertEqual(stage_legal_job_id("hero", 45), "crusader")
        self.assertEqual(stage_legal_job_id("sarasa_4", 48), "sarasa_3")
        self.assertEqual(stage_legal_job_id("hero", 50), "hero")

    def test_starforce_stat_growth_uses_the_original_curve(self) -> None:
        self.assertEqual(
            [star_multiplier(stars) for stars in (0, 1, 3, 5, 8, 10)],
            [1.0, 1.3, 2.08, 3.04, 4.93, 6.49],
        )

    def test_weekly_hard_boss_gold_outweighs_late_exploration(self) -> None:
        dungeon = max(DUNGEONS, key=lambda row: row.level_req)
        total_weight = sum(max(1, enemy.weight) for enemy in dungeon.enemies)
        expected_enemy_gold = sum(
            enemy.gold * max(1, enemy.weight)
            for enemy in dungeon.enemies
        ) / total_weight
        average_reward_roll = (
            REWARD_WIN_MULTIPLIER_MIN + REWARD_WIN_MULTIPLIER_MAX
        ) / 2
        weekly_explore_gold = (
            expected_enemy_gold
            * EXPLORE_GOLD_MULTIPLIER
            * average_reward_roll
            * DAILY_EXPLORES
            * 7
        )
        weekly_hard_boss_gold = sum(
            boss.gold for boss in BOSSES if boss.difficulty == "hard"
        )

        self.assertLess(weekly_explore_gold, weekly_hard_boss_gold * 0.4)

    def test_legendary_potential_values_stay_within_post_balance_caps(self) -> None:
        caps = {
            "base_atk": 4.0,
            "max_hp": 54.0,
            "hp_bonus": 0.06,
            "atk": 0.06,
            "defense": 0.09,
            "defense_ignore": 0.045,
            "dmg_amplification": 0.022,
            "dmg_supplement": 4.0,
            "skill_damage": 0.06,
            "skill_dmg_supplement": 6.0,
            "critical_rate": 0.0675,
            "critical_damage": 0.045,
            "triple_attack_rate": 0.035,
            "double_attack_rate": 0.055,
            "life_steal": 0.013,
            "healing_bonus": 0.09,
            "damage_cut": 0.02,
            "dmg_mitigation": 3.0,
            "life_steal_cap": 0.005,
            "heal_cap_bonus": 0.06,
        }
        for option in POTENTIAL_OPTION_BY_ID.values():
            if option.stat not in caps:
                continue
            with self.subTest(option=option.id):
                self.assertLessEqual(option.values.get("legendary", 0.0), caps[option.stat])

    def test_signature_weapon_stats_are_restored(self) -> None:
        expected_stats = {
            "eden": {"atk": 0.28, "strength": 0.14},
            "clockwork_blade_kumogakure": {
                "atk": 0.24,
                "critical_rate": 0.06,
                "triple_attack_rate": 0.16,
            },
            "aetherial_maverick": {
                "atk": 0.05,
                "defense_ignore": 0.06,
                "skill_damage": 0.1,
                "skill_dmg_supplement": 30,
            },
            "harmonia": {
                "atk": 0.4,
                "dmg_amplification": 0.04,
                "dmg_supplement": 20,
            },
            "genesis_badge": {
                "base_atk": 75,
                "garrison": 0.8,
                "dmg_mitigation": -25,
            },
        }
        for item_id, stats in expected_stats.items():
            with self.subTest(item=item_id):
                self.assertEqual(ITEM_BY_ID[item_id].stats, stats)

        self.assertEqual(
            ITEM_BY_ID["clockwork_blade_kumogakure"].effects.bonus_damage[0].ratio,
            0.1,
        )
        self.assertEqual(
            ITEM_BY_ID["genesis_badge"].effects.final_damage[0].ratio,
            0.08,
        )
        self.assertEqual(
            ITEM_BY_ID["aetherial_maverick"].fixed_stats,
            frozenset({"defense_ignore"}),
        )
        self.assertEqual(
            ITEM_BY_ID["harmonia"].fixed_stats,
            frozenset({"atk", "dmg_amplification"}),
        )

    def test_special_ability_raw_damage_is_bounded(self) -> None:
        special_skills = [skill for skill in SKILLS if skill.special]
        self.assertTrue(special_skills)
        for skill in special_skills:
            with self.subTest(skill=skill.id):
                self.assertLessEqual(skill.damage_multiplier * skill.hits, 2.1)
                self.assertGreaterEqual(skill.cooldown, 5)

    def test_balance_pilot_attacks_progressable_warnings_but_guards_sentinels(self) -> None:
        def warning(objective: str, required: int, *, min_damage: int = 0):
            return SimpleNamespace(
                objectives=[
                    SimpleNamespace(
                        objective=objective,
                        required=required,
                        progress=0,
                        min_damage=min_damage,
                    )
                ]
            )

        self.assertTrue(
            BalanceSimulator._normal_attack_can_progress_warning(warning("damage", 2_500))
        )
        self.assertTrue(
            BalanceSimulator._normal_attack_can_progress_warning(warning("hits", 16))
        )
        self.assertFalse(
            BalanceSimulator._normal_attack_can_progress_warning(warning("debuff", 1))
        )
        self.assertFalse(
            BalanceSimulator._normal_attack_can_progress_warning(
                warning("ability_damage", 1_200)
            )
        )
        self.assertFalse(
            BalanceSimulator._normal_attack_can_progress_warning(warning("hits", 99))
        )
        self.assertFalse(
            BalanceSimulator._normal_attack_can_progress_warning(warning("damage", 99_999))
        )
        self.assertFalse(
            BalanceSimulator._normal_attack_can_progress_warning(
                warning("hits", 99, min_damage=9_999)
            )
        )

    def test_warning_adapted_pilot_reserves_cooldowns_before_ct(self) -> None:
        engine = SimpleNamespace(
            _boss_has_ct_system=lambda _session: True,
            _current_ct_max=lambda _session: 3,
        )
        session = SimpleNamespace()
        participant = SimpleNamespace(
            pending_warning=None,
            queued_warnings=[],
            ct=2,
        )
        self.assertTrue(
            BalanceSimulator._should_reserve_for_warning(engine, session, participant)
        )
        participant.ct = 1
        self.assertTrue(
            BalanceSimulator._should_reserve_for_warning(engine, session, participant)
        )
        participant.queued_warnings.append(SimpleNamespace())
        self.assertTrue(
            BalanceSimulator._should_reserve_for_warning(engine, session, participant)
        )

    def test_balance_simulator_includes_universal_warning_utilities(self) -> None:
        simulator = BalanceSimulator(
            SimConfig(50, 50, 0, 0.0, 0.0, 0.0, 50, 1_000)
        )
        self.assertIn("miserable_mist", {
            skill.id for skill in simulator._available_skills("archmage_fp")
        })
        self.assertIn("skill", {
            skill.id for skill in simulator._available_skills("len_4")
        })

    def test_all_final_jobs_have_warning_capable_hard_boss_rotations(self) -> None:
        final_jobs = (
            "bowmaster", "marksman", "hero", "paladin", "archmage_fp",
            "archmage_il", "bishop", "len_4", "sarasa_4",
        )
        for requested_job_id in final_jobs:
            for boss_id, stars in HARD_BOSS_STAGE_STARS.items():
                boss = BOSS_BY_ID[boss_id]
                effective_job_id = stage_legal_job_id(requested_job_id, boss.level_req)
                simulator = BalanceSimulator(SimConfig(
                    boss.level_req,
                    50,
                    stars,
                    boss.stats.get("defense", 0),
                    boss.stats.get("damage_cut", 0),
                    boss.stats.get("dmg_mitigation", 0),
                    boss.level_req,
                    int(boss.stats["max_hp"]),
                ))
                item_ids = stage_legal_item_ids(boss_id)[:4]
                with self.subTest(job=requested_job_id, boss=boss_id):
                    self.assertTrue(simulator._warning_capable_skill_combos(
                        effective_job_id,
                        item_ids,
                        6,
                        boss_id,
                    ))

    def test_immortal_durability_trial_preserves_damage_driven_stacks(self) -> None:
        simulator = BalanceSimulator(SimConfig(56, 50, 10, 0, 0, 0, 56, 1))
        profile = simulator._profile(
            "hero",
            ("hrunting", "immortal_legacy", "genesis_badge", "eden"),
        )
        profile.equipped_skill_ids = [
            "raging_blow", "intrepid_slash", "combo_attack", "combo_synergy",
            "magic_crash",
        ]
        profile.equipped_special_skill_id = "banahogg"
        demian = simulator.simulate_boss_trial(
            profile,
            "demian_hard",
            seed=20260817,
            max_turns=20,
            warning_adapted=True,
            immortal_player=True,
        )
        first = simulator.simulate_boss_trial(
            profile,
            "first_adversary_hard",
            seed=20260817,
            max_turns=20,
            warning_adapted=True,
            immortal_player=True,
        )

        self.assertGreater(demian.player_hp, 0)
        self.assertGreater(dict(demian.boss_stacks)["demian_stigma_hard"], 0)
        self.assertGreater(first.player_hp, 0)
        self.assertLessEqual(first.turns, 20)
        self.assertTrue(first.won or first.turns == 20)


if __name__ == "__main__":
    unittest.main()
