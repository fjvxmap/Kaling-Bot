from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.services.rpg.data import (
    BOSSES,
    DAILY_EXPLORES,
    DUNGEONS,
    EXPLORE_GOLD_MULTIPLIER,
    POTENTIAL_OPTION_BY_ID,
    REWARD_WIN_MULTIPLIER_MAX,
    REWARD_WIN_MULTIPLIER_MIN,
    SKILLS,
)
from tools.rpg_balance.simulator import BalanceSimulator


class BalancePolicyTests(unittest.TestCase):
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
            "dmg_supplement": 5.0,
            "skill_damage": 0.06,
            "skill_dmg_supplement": 8.0,
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


if __name__ == "__main__":
    unittest.main()
