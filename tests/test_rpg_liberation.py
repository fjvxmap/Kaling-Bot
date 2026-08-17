from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from random import Random

from bot.cogs.rpg import RPGCog
from bot.services.rpg.data import (
    BOSS_BY_ID,
    ITEM_BY_ID,
    LIBERATION,
    SKILL_BY_ID,
    BossPattern,
    EffectAction,
    PlainDamage,
)
from bot.services.rpg.manager import ActiveStackEffect, LIBERATION_RESET_REVISION, RPGService
from bot.services.rpg.models import CombatStats, ItemInstance, PlayerProfile, PotentialLine
from bot.services.rpg.store import RPGStore


class LiberationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_path = Path(self.temp_dir.name) / "rpg_state.json"

    def service(self, *, seed: int = 7) -> RPGService:
        return RPGService(RPGStore(self.state_path), Random(seed))

    @staticmethod
    def trace_ids() -> set[str]:
        return {
            material_id
            for stage in LIBERATION.stages
            for material_id in stage.materials
        }

    def legacy_payload(self) -> dict:
        profile = PlayerProfile.create(1, "Legacy")
        profile.job_id = "hero"
        profile.cleared_boss_ids = [LIBERATION.boss_id]
        profile.solo_cleared_boss_ids = [LIBERATION.boss_id]
        profile.genesis_item_uid = 10
        profile.genesis_liberation_stage = 2
        profile.inventory = [
            ItemInstance(
                uid=10,
                template_id="genesis_two_handed_sword",
                stars=8,
                potential_grade="legendary",
                potential_lines=[PotentialLine("atk_percent", "legendary")],
                potential_locked=False,
            ),
            ItemInstance(uid=11, template_id="genesis_two_handed_sword", stars=8),
            ItemInstance(uid=12, template_id="wooden_sword", stars=2),
        ]
        profile.equipped_item_uids = [10, 11, 12]
        profile.next_item_uid = 13
        profile.materials = {material_id: 4 for material_id in self.trace_ids()}
        raw = profile.to_dict()
        raw.pop("liberation_reset_revision", None)
        return {"version": 1, "profiles": {"1": raw}}

    def write_legacy_payload(self) -> None:
        self.state_path.write_text(
            json.dumps(self.legacy_payload(), ensure_ascii=False),
            encoding="utf-8",
        )

    def test_startup_migration_resets_liberation_once_and_preserves_tracked_weapon(self) -> None:
        self.write_legacy_payload()

        service = self.service()
        profile = service.get_profile(1, "Legacy")
        genesis = service.genesis_item(profile)

        self.assertIsNotNone(genesis)
        self.assertEqual(genesis.uid, 10)
        self.assertEqual(genesis.template_id, "genesis_two_handed_sword")
        self.assertEqual(genesis.stars, 0)
        self.assertFalse(genesis.destroyed)
        self.assertEqual(genesis.potential_grade, "")
        self.assertEqual(genesis.potential_lines, [])
        self.assertTrue(genesis.potential_locked)
        self.assertEqual(profile.genesis_liberation_stage, 0)
        self.assertEqual(profile.liberation_reset_revision, LIBERATION_RESET_REVISION)
        self.assertEqual({item.uid for item in profile.inventory}, {10, 12})
        self.assertTrue(self.trace_ids().isdisjoint(profile.materials))
        self.assertIn(LIBERATION.boss_id, profile.cleared_boss_ids)
        self.assertIn(LIBERATION.boss_id, profile.solo_cleared_boss_ids)

        snapshot = profile.to_dict()
        restarted = self.service().get_profile(1, "Legacy")
        self.assertEqual(restarted.to_dict(), snapshot)

    def test_new_profile_starts_at_current_revision_without_reset_work(self) -> None:
        service = self.service()
        profile = service.get_profile(99, "New")

        self.assertEqual(profile.liberation_reset_revision, LIBERATION_RESET_REVISION)
        self.assertEqual(profile.genesis_item_uid, 0)
        self.assertEqual(profile.genesis_liberation_stage, -1)

    def test_startup_migration_removes_untracked_genesis_instead_of_claiming_it(self) -> None:
        payload = self.legacy_payload()
        raw = payload["profiles"]["1"]
        raw["genesis_item_uid"] = 0
        raw["genesis_liberation_stage"] = 2
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        profile = self.service().get_profile(1, "Legacy")

        self.assertEqual(profile.genesis_item_uid, 0)
        self.assertEqual(profile.genesis_liberation_stage, -1)
        self.assertFalse(any(ITEM_BY_ID[item.template_id].genesis_weapon for item in profile.inventory))
        self.assertTrue(self.trace_ids().isdisjoint(profile.materials))

    def test_concurrent_startup_snapshots_do_not_double_apply_migration_numbers(self) -> None:
        self.write_legacy_payload()
        left_store = RPGStore(self.state_path)
        right_store = RPGStore(self.state_path)
        left = left_store.load_profiles()
        right = right_store.load_profiles()
        migration_service = RPGService(
            RPGStore(Path(self.temp_dir.name) / "empty_state.json"),
            Random(3),
        )

        migration_service._cleanup_profile(left[1])
        migration_service._cleanup_profile(right[1])
        left_store.save_profiles(left)
        right_store.save_profiles(right)

        migrated = RPGStore(self.state_path).load_profiles()[1]
        genesis = next(item for item in migrated.inventory if item.uid == 10)
        self.assertEqual(migrated.liberation_reset_revision, LIBERATION_RESET_REVISION)
        self.assertEqual(migrated.genesis_liberation_stage, 0)
        self.assertEqual(genesis.stars, 0)
        self.assertTrue(self.trace_ids().isdisjoint(migrated.materials))

    def test_concurrent_trace_consumption_and_reward_preserve_both_deltas(self) -> None:
        for consume_first in (True, False):
            with self.subTest(consume_first=consume_first):
                state_path = Path(self.temp_dir.name) / f"trace-race-{consume_first}.json"
                initial = PlayerProfile.create(1, "Trace Race")
                initial.materials["lotus_liberation_trace"] = 1
                state_path.write_text(
                    json.dumps(
                        {"version": 1, "profiles": {"1": initial.to_dict()}},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                consume_store = RPGStore(state_path)
                reward_store = RPGStore(state_path)
                consume_profiles = consume_store.load_profiles()
                reward_profiles = reward_store.load_profiles()
                consume_profiles[1].materials.pop("lotus_liberation_trace")
                reward_profiles[1].materials["lotus_liberation_trace"] += 1

                if consume_first:
                    consume_store.save_profiles(consume_profiles)
                    reward_store.save_profiles(reward_profiles)
                else:
                    reward_store.save_profiles(reward_profiles)
                    consume_store.save_profiles(consume_profiles)

                final = RPGStore(state_path).load_profiles()[1]
                self.assertEqual(final.materials.get("lotus_liberation_trace"), 1)

    def test_identical_concurrent_liberation_consumption_is_idempotent(self) -> None:
        stage_two_trace_ids = tuple(LIBERATION.stages[1].materials)
        for left_first in (True, False):
            with self.subTest(left_first=left_first):
                state_path = Path(self.temp_dir.name) / f"same-stage-race-{left_first}.json"
                initial = PlayerProfile.create(1, "Same Stage Race")
                initial.job_id = "hero"
                initial.genesis_item_uid = 10
                initial.genesis_liberation_stage = 1
                initial.inventory = [
                    ItemInstance(
                        uid=10,
                        template_id="genesis_two_handed_sword",
                        stars=3,
                        potential_locked=True,
                    )
                ]
                initial.materials = {material_id: 4 for material_id in stage_two_trace_ids}
                state_path.write_text(
                    json.dumps(
                        {"version": 1, "profiles": {"1": initial.to_dict()}},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                left_store = RPGStore(state_path)
                right_store = RPGStore(state_path)
                left_profiles = left_store.load_profiles()
                right_profiles = right_store.load_profiles()
                for profiles, option_id in (
                    (left_profiles, "potential_atk"),
                    (right_profiles, "potential_defense"),
                ):
                    profile = profiles[1]
                    profile.genesis_liberation_stage = 2
                    genesis = profile.inventory[0]
                    genesis.stars = 8
                    genesis.potential_locked = False
                    genesis.potential_grade = "unique"
                    genesis.potential_lines = [
                        PotentialLine(option_id, "unique") for _ in range(3)
                    ]
                    for material_id in stage_two_trace_ids:
                        profile.materials[material_id] -= 1

                if left_first:
                    left_store.save_profiles(left_profiles)
                    right_store.save_profiles(right_profiles)
                else:
                    right_store.save_profiles(right_profiles)
                    left_store.save_profiles(left_profiles)

                final = RPGStore(state_path).load_profiles()[1]
                self.assertEqual(final.genesis_liberation_stage, 2)
                self.assertEqual(final.inventory[0].stars, 8)
                self.assertFalse(final.inventory[0].potential_locked)
                self.assertIn(
                    final.inventory[0].potential_lines[0].option_id,
                    {"potential_atk", "potential_defense"},
                )
                for material_id in stage_two_trace_ids:
                    self.assertEqual(final.materials.get(material_id), 3)

    def test_stale_startup_migration_cannot_roll_back_new_liberation_progress(self) -> None:
        self.write_legacy_payload()
        first_store = RPGStore(self.state_path)
        stale_store = RPGStore(self.state_path)
        first = first_store.load_profiles()
        stale = stale_store.load_profiles()
        migration_service = RPGService(
            RPGStore(Path(self.temp_dir.name) / "empty_state.json"),
            Random(5),
        )

        migration_service._cleanup_profile(first[1])
        migration_service._cleanup_profile(stale[1])
        first_store.save_profiles(first)

        first[1].genesis_liberation_stage = 1
        first_genesis = next(item for item in first[1].inventory if item.uid == 10)
        first_genesis.stars = 3
        first[1].materials["dusk_liberation_trace"] = 1
        first[1].gold += 321
        first_store.save_profiles(first)

        # A second process now finishes saving the reset it computed from the
        # legacy snapshot. Its stale migration must not replace newer progress.
        stale_store.save_profiles(stale)

        final = RPGStore(self.state_path).load_profiles()[1]
        final_genesis = next(item for item in final.inventory if item.uid == 10)
        self.assertEqual(final.genesis_liberation_stage, 1)
        self.assertEqual(final_genesis.stars, 3)
        self.assertEqual(final.materials.get("dusk_liberation_trace"), 1)
        self.assertEqual(final.gold, first[1].gold)

    def test_concurrent_liberation_keeps_the_complete_higher_stage_snapshot(self) -> None:
        for first_saved_stage in (1, 2):
            with self.subTest(first_saved_stage=first_saved_stage):
                state_path = Path(self.temp_dir.name) / f"stage-race-{first_saved_stage}.json"
                initial = PlayerProfile.create(1, "Liberation Race")
                initial.job_id = "hero"
                initial.genesis_item_uid = 10
                initial.genesis_liberation_stage = 0
                initial.gold = 100
                initial.exp = 0
                initial.inventory = [
                    ItemInstance(
                        uid=10,
                        template_id="genesis_two_handed_sword",
                        stars=0,
                        potential_locked=True,
                    )
                ]
                initial.next_item_uid = 11
                initial.materials = {material_id: 1 for material_id in self.trace_ids()}
                state_path.write_text(
                    json.dumps(
                        {"version": 1, "profiles": {"1": initial.to_dict()}},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                stage_one_store = RPGStore(state_path)
                stage_two_store = RPGStore(state_path)
                stage_one_profiles = stage_one_store.load_profiles()
                stage_two_profiles = stage_two_store.load_profiles()
                stage_one = stage_one_profiles[1]
                stage_two = stage_two_profiles[1]

                stage_one.genesis_liberation_stage = 1
                stage_one.gold += 500
                stage_one.inventory.append(
                    ItemInstance(uid=20, template_id="wooden_sword")
                )
                stage_one.cleared_boss_ids.append("guardian_angel_slime")
                stage_one.inventory[0].stars = 3
                for material_id in LIBERATION.stages[0].materials:
                    stage_one.materials.pop(material_id, None)

                stage_two.genesis_liberation_stage = 2
                stage_two.exp += 75
                stage_two.inventory.append(
                    ItemInstance(uid=30, template_id="bronze_sword")
                )
                stage_two.cleared_boss_ids.append("lotus")
                stage_two.inventory[0].stars = 8
                stage_two.inventory[0].potential_grade = "unique"
                stage_two.inventory[0].potential_lines = [
                    PotentialLine("potential_atk", "unique")
                    for _ in range(3)
                ]
                stage_two.inventory[0].potential_locked = False
                for material_id in self.trace_ids():
                    stage_two.materials.pop(material_id, None)

                if first_saved_stage == 1:
                    stage_one_store.save_profiles(stage_one_profiles)
                    stage_two_store.save_profiles(stage_two_profiles)
                else:
                    stage_two_store.save_profiles(stage_two_profiles)
                    stage_one_store.save_profiles(stage_one_profiles)

                final = RPGStore(state_path).load_profiles()[1]
                genesis = final.inventory[0]
                self.assertEqual(final.genesis_liberation_stage, 2)
                self.assertEqual(genesis.stars, 8)
                self.assertEqual(genesis.potential_grade, "unique")
                self.assertEqual(len(genesis.potential_lines), 3)
                self.assertFalse(genesis.potential_locked)
                self.assertTrue(self.trace_ids().isdisjoint(final.materials))
                self.assertEqual(final.gold, 600)
                self.assertEqual(final.exp, 75)
                self.assertEqual(
                    {item.uid for item in final.inventory},
                    {10, 20, 30},
                )
                self.assertEqual(
                    set(final.cleared_boss_ids),
                    {"guardian_angel_slime", "lotus"},
                )

    def test_liberation_traces_are_exactly_one_for_incomplete_hard_solo_clears(self) -> None:
        service = self.service()
        trace_id = "lotus_liberation_trace"
        normal = BOSS_BY_ID["lotus"]
        hard = BOSS_BY_ID["lotus_hard"]
        self.assertNotIn(trace_id, {drop.id for drop in normal.rewards.material_drops})
        self.assertIn(trace_id, {drop.id for drop in hard.rewards.material_drops})

        normal_reward = service.grant_boss_reward(
            1,
            "Solo",
            normal.id,
            reward_role="owner",
            solo_clear=True,
        )
        self.assertNotIn(trace_id, normal_reward.materials)

        party_reward = service.grant_boss_reward(
            2,
            "Party",
            hard.id,
            reward_role="owner",
            solo_clear=False,
        )
        self.assertNotIn(trace_id, party_reward.materials)

        solo_reward = service.grant_boss_reward(
            3,
            "Solo Hard",
            hard.id,
            reward_role="owner",
            solo_clear=True,
        )
        self.assertEqual(solo_reward.materials.get(trace_id), 1)
        self.assertEqual(service.get_profile(3, "Solo Hard").materials.get(trace_id), 1)

        complete = service.get_profile(4, "Complete")
        complete.inventory = [
            ItemInstance(uid=1, template_id="genesis_two_handed_sword", stars=8)
        ]
        complete.genesis_item_uid = 1
        complete.genesis_liberation_stage = 2
        complete_reward = service.grant_boss_reward(
            4,
            "Complete",
            hard.id,
            reward_role="owner",
            solo_clear=True,
        )
        self.assertNotIn(trace_id, complete_reward.materials)
        self.assertNotIn(trace_id, service.get_profile(4, "Complete").materials)

    def test_every_liberation_trace_is_exclusive_to_its_hard_solo_clear(self) -> None:
        expected = {
            "lotus": "lotus_liberation_trace",
            "demian": "demian_liberation_trace",
            "lucid": "lucid_liberation_trace",
            "dusk": "dusk_liberation_trace",
            "dunkel": "dunkel_liberation_trace",
            "verus_hilla": "verus_hilla_liberation_trace",
        }
        service = self.service()

        for index, (boss_id, trace_id) in enumerate(expected.items(), start=1):
            normal = BOSS_BY_ID[boss_id]
            hard = BOSS_BY_ID[f"{boss_id}_hard"]
            with self.subTest(boss=boss_id):
                self.assertNotIn(trace_id, {drop.id for drop in normal.rewards.material_drops})
                self.assertIn(trace_id, {drop.id for drop in hard.rewards.material_drops})

                solo_id = 100 + index
                solo_reward = service.grant_boss_reward(
                    solo_id,
                    f"Solo {index}",
                    hard.id,
                    reward_role="owner",
                    solo_clear=True,
                )
                self.assertEqual(solo_reward.materials.get(trace_id), 1)
                self.assertEqual(service.get_profile(solo_id, f"Solo {index}").materials.get(trace_id), 1)

                party_id = 200 + index
                party_reward = service.grant_boss_reward(
                    party_id,
                    f"Party {index}",
                    hard.id,
                    reward_role="owner",
                    solo_clear=False,
                )
                self.assertNotIn(trace_id, party_reward.materials)
                self.assertNotIn(trace_id, service.get_profile(party_id, f"Party {index}").materials)

    def test_party_cannot_become_trace_eligible_by_leaving_after_start(self) -> None:
        service = self.service()
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        boss = BOSS_BY_ID["lotus_hard"]
        trace_id = "lotus_liberation_trace"

        owner_session, message = engine._create_boss_session(boss, 10, "Owner")
        self.assertIsNotNone(owner_session, message)
        assert owner_session is not None
        self.assertTrue(engine._add_boss_participant(owner_session, 11, "Guest")[0])
        self.assertTrue(engine._start_boss_session(owner_session, 10)[0])
        self.assertFalse(owner_session.started_solo)
        self.assertTrue(engine._give_up_boss_session(owner_session, 11, "Guest")[0])
        engine._grant_boss_session_rewards(owner_session)
        owner_profile = service.get_profile(10, "Owner")
        self.assertNotIn(trace_id, owner_profile.materials)
        self.assertNotIn(boss.id, owner_profile.solo_cleared_boss_ids)
        self.assertNotIn(boss.base_boss_id, owner_profile.solo_cleared_boss_ids)

        guest_session, message = engine._create_boss_session(boss, 12, "Leaving Owner")
        self.assertIsNotNone(guest_session, message)
        assert guest_session is not None
        self.assertTrue(engine._add_boss_participant(guest_session, 13, "Remaining Guest")[0])
        self.assertTrue(engine._start_boss_session(guest_session, 12)[0])
        self.assertFalse(guest_session.started_solo)
        self.assertTrue(engine._give_up_boss_session(guest_session, 12, "Leaving Owner")[0])
        engine._grant_boss_session_rewards(guest_session)
        guest_profile = service.get_profile(13, "Remaining Guest")
        self.assertNotIn(trace_id, guest_profile.materials)
        self.assertNotIn(boss.id, guest_profile.solo_cleared_boss_ids)
        self.assertNotIn(boss.base_boss_id, guest_profile.solo_cleared_boss_ids)

    def test_skip_uses_the_party_size_snapshot_for_trace_eligibility(self) -> None:
        service = self.service()
        engine = RPGCog.__new__(RPGCog)
        engine.bot = None
        engine.service = service
        engine.boss_sessions = {}
        engine._boss_damage_detail_messages = {}
        engine._next_boss_session_id = 1
        boss = BOSS_BY_ID["lotus_hard"]
        trace_id = "lotus_liberation_trace"

        solo_profile = service.get_profile(20, "Solo Skip")
        solo_profile.solo_cleared_boss_ids.append(boss.id)
        solo_session, message = engine._create_boss_session(boss, 20, "Solo Skip")
        self.assertIsNotNone(solo_session, message)
        assert solo_session is not None
        self.assertTrue(engine._skip_boss_session(solo_session, 20)[0])
        self.assertTrue(solo_session.started_solo)
        self.assertEqual(service.get_profile(20, "Solo Skip").materials.get(trace_id), 1)

        party_owner = service.get_profile(21, "Party Skip Owner")
        party_guest = service.get_profile(22, "Party Skip Guest")
        party_owner.solo_cleared_boss_ids.append(boss.id)
        party_guest.solo_cleared_boss_ids.append(boss.id)
        party_session, message = engine._create_boss_session(boss, 21, "Party Skip Owner")
        self.assertIsNotNone(party_session, message)
        assert party_session is not None
        self.assertTrue(engine._add_boss_participant(party_session, 22, "Party Skip Guest")[0])
        self.assertTrue(engine._skip_boss_session(party_session, 21)[0])
        self.assertFalse(party_session.started_solo)
        self.assertNotIn(trace_id, service.get_profile(21, "Party Skip Owner").materials)
        self.assertNotIn(trace_id, service.get_profile(22, "Party Skip Guest").materials)

    def test_second_liberation_sets_eight_stars_and_grants_a_separate_equipment_skill(self) -> None:
        service = self.service()
        profile = service.get_profile(20, "Liberator")
        profile.job_id = "hero"
        profile.cleared_boss_ids.append(LIBERATION.boss_id)
        claimed = service.claim_genesis_weapon(20, "Liberator")
        self.assertTrue(claimed.ok)
        self.assertIsNotNone(claimed.item)
        item = claimed.item

        for stage in LIBERATION.stages:
            profile.materials.update(stage.materials)
            result = service.advance_genesis_liberation(20, "Liberator")
            self.assertTrue(result.ok)

        self.assertEqual(profile.genesis_liberation_stage, 2)
        self.assertEqual(item.stars, 8)
        self.assertIsNone(service.genesis_weapon_skill(profile))
        regular_before = list(service.equipped_skills(profile))
        special_before = service.equipped_special_skill(profile)

        equipped = service.equip_item(20, "Liberator", item.uid)
        self.assertTrue(equipped.ok)
        genesis_skill = service.genesis_weapon_skill(profile)
        self.assertIsNotNone(genesis_skill)
        self.assertEqual(genesis_skill.id, "genesis_creation_ion")
        self.assertNotIn(genesis_skill, service.unlocked_special_skills(profile))
        self.assertEqual(service.equipped_skills(profile), regular_before)
        self.assertEqual(service.equipped_special_skill(profile), special_before)
        self.assertIn(genesis_skill, service.combat_skills(profile))

    def test_creation_ion_blocks_normal_and_plain_damage_for_one_turn(self) -> None:
        service = self.service()
        skill = service.genesis_weapon_skill_template()
        self.assertIsNotNone(skill)
        player = CombatStats(base_atk=20, max_hp=500)
        enemy = CombatStats(base_atk=80, max_hp=2_000)
        player_effects = []
        enemy_effects = []

        service._use_player_skill(
            skill,
            player,
            enemy,
            500,
            2_000,
            player_effects,
            enemy_effects,
        )
        protected = service._stats_with_effects(player, player_effects)
        self.assertTrue(protected.invulnerable)
        self.assertEqual(service._basic_attack(enemy, 2_000, protected, 500, []).damage, 0)

        pattern = BossPattern(
            threshold=1.0,
            name="Invulnerability test",
            damage_multiplier=5.0,
            hits=3,
            plain_damage=PlainDamage(
                mode="target_max_hp_ratio",
                value=0.9,
            ),
        )
        self.assertEqual(
            service._use_boss_pattern(
                pattern,
                enemy,
                protected,
                2_000,
                500,
                player_effects,
                enemy_effects,
            ),
            0,
        )

        player_effects = service._tick_effects(player_effects)
        unprotected = service._stats_with_effects(player, player_effects)
        self.assertFalse(unprotected.invulnerable)
        self.assertGreater(service._basic_attack(enemy, 2_000, unprotected, 500, []).damage, 0)

    def test_invulnerability_blocks_skill_triggered_stack_reaction_damage(self) -> None:
        service = self.service()
        skill = replace(
            SKILL_BY_ID["arrow_blow"],
            damage_multiplier=0,
            hits=0,
            effect_actions=[
                EffectAction(
                    action="stack_max",
                    target="enemy",
                    stack_effect_id="black_mage_destruction_curse_hard",
                    duration=4,
                )
            ],
        )
        enemy_stacks = [
            ActiveStackEffect("black_mage_creation_curse_hard", 1, turns=4)
        ]

        result = service._use_player_skill(
            skill,
            CombatStats(base_atk=20, max_hp=500),
            CombatStats(base_atk=10, max_hp=1_000, invulnerable=True),
            500,
            1_000,
            [],
            [],
            player_stack_effects=[],
            enemy_stack_effects=enemy_stacks,
        )

        self.assertEqual(result.damage, 0)
        self.assertEqual(enemy_stacks, [], "The blocked reaction should still consume both curses")

    def test_creation_ion_protects_the_first_simulated_combat_turn(self) -> None:
        service = self.service()
        profile = service.get_profile(30, "Simulator")
        profile.job_id = "hero"
        profile.inventory = [
            ItemInstance(uid=1, template_id="genesis_two_handed_sword", stars=8)
        ]
        profile.genesis_item_uid = 1
        profile.genesis_liberation_stage = 2
        profile.equipped_item_uids = [1]

        report = service._simulate_battle(
            profile,
            "Lethal Dummy",
            CombatStats(base_atk=10_000, max_hp=1_000_000),
        )

        self.assertIn("창조의 아이온", report.skills_used)
        self.assertGreaterEqual(report.turns, 2)
        self.assertTrue(any("1T Lethal Dummy 반격: 0 피해" in line for line in report.log))

    def test_discord_ability_panel_labels_creation_ion_as_a_dedicated_slot(self) -> None:
        service = self.service()
        profile = service.get_profile(40, "Discord")
        profile.job_id = "hero"
        profile.inventory = [
            ItemInstance(uid=1, template_id="genesis_two_handed_sword", stars=8)
        ]
        profile.genesis_item_uid = 1
        profile.genesis_liberation_stage = 2
        profile.equipped_item_uids = [1]
        cog = RPGCog.__new__(RPGCog)
        cog.service = service

        embed = cog._ability_embed(profile)
        fields = {field.name: field.value for field in embed.fields}

        self.assertIn("제네시스 어빌리티 · 전용 슬롯", fields)
        self.assertIn("창조의 아이온", fields["제네시스 어빌리티 · 전용 슬롯"])
        self.assertIn("무적", fields["제네시스 어빌리티 · 전용 슬롯"])


if __name__ == "__main__":
    unittest.main()
