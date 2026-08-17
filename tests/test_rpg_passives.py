from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from random import Random
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kaling_web.settings")

import django

django.setup()

from django.test import Client, override_settings

from bot.cogs.rpg import RPGCog
from bot.services.rpg.data import (
    CONTENT,
    JOB_BY_ID,
    PASSIVE_BY_ID,
    PASSIVES,
    InitialStackEffect,
    LowHpCooldownRule,
    STACK_EFFECT_BY_ID,
)
from bot.services.rpg.manager import ActiveStackEffect, RPGService
from bot.services.rpg.models import ItemInstance, PlayerProfile
from bot.services.rpg.store import RPGStore
from rpg_web import runtime as runtime_module
from rpg_web.runtime import WebRPGRuntime


class _MemoryStore:
    def load_profiles(self) -> dict[int, PlayerProfile]:
        return {}

    def save_profiles(self, profiles: dict[int, PlayerProfile]) -> None:
        return None


class JobPassiveTests(unittest.TestCase):
    def service(self) -> RPGService:
        return RPGService(store=_MemoryStore(), rng=Random(17))

    def test_passive_unlocks_from_job_chain_without_using_an_ability_slot(self) -> None:
        service = self.service()
        profile = service.get_profile(1, "Sarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_ground_zero"]

        passive_ids = [passive.id for passive in service.unlocked_passives(profile)]

        self.assertIn("sarasa_kaikiryanshin", passive_ids)
        self.assertEqual(
            [skill.id for skill in service.equipped_skills(profile)],
            ["sarasa_ground_zero"],
        )
        self.assertTrue(set(passive_ids).isdisjoint(profile.equipped_skill_ids))

        service.set_equipped_skills(
            profile.user_id,
            profile.display_name,
            [
                "sarasa_ground_zero",
                "sarasa_three_tigers_blessing",
                "sarasa_vorpal_rage",
                "sarasa_fracture_line",
                "sarasa_faultline",
                "sarasa_berserk_forge",
            ],
        )
        self.assertEqual(len(profile.equipped_skill_ids), 5)
        self.assertEqual(len(service.unlocked_passives(profile)), 3)

    def test_passive_seeds_fury_alongside_legacy_job_stack(self) -> None:
        service = self.service()
        profile = service.get_profile(2, "Sarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"

        stacks = {
            stack.template_id: stack.stacks
            for stack in service.initial_player_stack_effects(profile)
        }

        self.assertEqual(stacks["sarasa_fury"], 0)
        self.assertEqual(stacks["sarasa_kotoryubi"], 0)
        self.assertEqual(stacks["sarasa_astral_form"], 1)

    def test_low_hp_survival_activates_visible_offensive_passive(self) -> None:
        service = self.service()
        profile = service.get_profile(23, "LowHpPassive")
        profile.level = 50
        profile.job_id = "sarasa_4"
        stacks = service.initial_player_stack_effects(profile)

        service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )

        self.assertEqual(service._active_stack_count(stacks, "sarasa_kotoryubi"), 1)
        stats = service._stats_with_effects(service.profile_stats(profile), [], stacks)
        self.assertAlmostEqual(stats.triple_attack_rate - service.profile_stats(profile).triple_attack_rate, 0.15)
        effects = service._effects_with_stacks([], stacks)
        self.assertAlmostEqual(
            sum(
                bonus.ratio
                for effect in effects
                for bonus in effect.special.bonus_damage
            ),
            0.05,
        )

        cog = RPGCog.__new__(RPGCog)
        cog.service = service
        status = cog._stack_effects_text(stacks)
        self.assertIn("호두용미 lv.1/1", status)
        self.assertIn("트리플 어택 확률 +15.0%", status)
        self.assertIn("추격 5%", status)

        service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=351,
            max_hp=1_000,
        )
        self.assertEqual(service._active_stack_count(stacks, "sarasa_kotoryubi"), 0)

        service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=0,
            max_hp=1_000,
        )
        self.assertEqual(
            service._active_stack_count(stacks, "sarasa_kotoryubi"),
            0,
            "사망한 턴에는 저체력 생존 패시브가 발동하면 안 된다",
        )

    def test_passive_owns_fury_rules_and_per_ability_life_steal_cap(self) -> None:
        service = self.service()
        profile = service.get_profile(22, "PassiveOwner")
        profile.level = 50
        profile.job_id = "sarasa_4"
        passive = PASSIVE_BY_ID["sarasa_kaikiryanshin"]

        self.assertEqual(
            [rule.condition.objective for rule in passive.stack_rules],
            ["ability", "triple_attack", "guard", "turn_end", "turn_end", "turn_end"],
        )
        raw_fury = next(
            effect for effect in CONTENT["stack_effects"] if effect.get("id") == "sarasa_fury"
        )
        self.assertEqual(raw_fury.get("conditions"), [])
        self.assertEqual(
            len(STACK_EFFECT_BY_ID["sarasa_fury"].conditions),
            len(passive.stack_rules),
        )
        self.assertEqual(passive.ability_life_steal_cap, 0.05)
        self.assertEqual(service.cap_ability_life_steal(profile, 999, 1_000), 50)

        profile.job_id = "hero"
        self.assertEqual(service.cap_ability_life_steal(profile, 999, 1_000), 999)

    def test_passive_owns_low_hp_cooldown_rule(self) -> None:
        service = self.service()
        profile = service.get_profile(3, "Sarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"
        passive = PASSIVE_BY_ID["sarasa_kaikiryanshin"]
        stacks = [ActiveStackEffect("sarasa_fury", 5, persistent=True)]

        extra_ticks = service.apply_player_turn_end(
            profile,
            stacks,
            [],
            current_hp=350,
            max_hp=1_000,
        )

        self.assertGreater(passive.low_hp_cooldown.reduction, 0)
        self.assertEqual(extra_ticks, passive.low_hp_cooldown.reduction)
        self.assertEqual(stacks[0].stacks, 2)

        stacks[0].stacks = 4
        self.assertEqual(
            service.apply_player_turn_end(
                profile,
                stacks,
                [],
                current_hp=350,
                max_hp=1_000,
            ),
            0,
            "추가 쿨타임 감소는 격앙을 버텨 진정시킨 턴에만 발동해야 한다",
        )

    def test_passive_compresses_extreme_enmity_without_changing_raw_starforce(self) -> None:
        service = self.service()
        sarasa = service.get_profile(31, "Curve")
        sarasa.level = 50
        sarasa.job_id = "sarasa_4"
        sarasa.inventory = [ItemInstance(uid=1, template_id="hrunting", stars=10)]
        sarasa.equipped_item_uids = [1]

        stats = service.profile_stats(sarasa)
        self.assertGreater(stats.enmity, 4.5, "흐룬팅의 원본 스타포스 성장량은 유지해야 한다")
        effective = service._effective_enmity(stats)
        self.assertGreater(effective, 1.0)
        self.assertLess(effective, 1.1)

        buffed = replace(stats, enmity=stats.enmity + 0.05)
        self.assertAlmostEqual(
            service._effective_enmity(buffed),
            effective + 0.05,
            places=9,
            msg="전투 중 분노·어빌리티로 얻은 배수는 기본 배수 압축 뒤에 온전히 더해져야 한다",
        )
        full = service._outgoing_damage(stats, stats.final_hp)
        low = service._outgoing_damage(stats, int(stats.final_hp * 0.35))
        self.assertGreater(low, full * 1.18)
        self.assertLess(low, full * 1.25)

        hero = PlayerProfile.from_dict(sarasa.to_dict())
        hero.job_id = "hero"
        hero_stats = service.profile_stats(hero)
        self.assertEqual(hero_stats.enmity_soft_cap, -1.0)
        self.assertEqual(service._effective_enmity(hero_stats), hero_stats.enmity)

    def test_legacy_job_stack_and_cooldown_fields_remain_compatible(self) -> None:
        service = self.service()
        profile = service.get_profile(30, "Legacy")
        profile.level = 3
        profile.job_id = "sarasa_1"
        legacy_job = replace(
            JOB_BY_ID["sarasa_1"],
            initial_stack_effects=(InitialStackEffect("sarasa_fury", 2),),
            low_hp_cooldown=LowHpCooldownRule(max_hp_ratio=0.35, reduction=1),
        )
        jobs = {**JOB_BY_ID, "sarasa_1": legacy_job}

        with (
            patch("bot.services.rpg.manager.PASSIVES", []),
            patch("bot.services.rpg.manager.JOB_BY_ID", jobs),
        ):
            stacks = service.initial_player_stack_effects(profile)
            extra_ticks = service.apply_player_turn_end(
                profile,
                stacks,
                [],
                current_hp=350,
                max_hp=1_000,
            )

        self.assertEqual(stacks[0].template_id, "sarasa_fury")
        self.assertEqual(extra_ticks, 1)

    def test_discord_lists_passives_separately_from_slots(self) -> None:
        service = self.service()
        profile = service.get_profile(4, "Sarasa")
        profile.level = 50
        profile.job_id = "sarasa_4"
        profile.equipped_skill_ids = ["sarasa_ground_zero"]
        cog = RPGCog.__new__(RPGCog)
        cog.service = service

        embed = cog._ability_embed(profile)
        passive_field = next(
            field for field in embed.fields if field.name.startswith("직업 패시브")
        )
        equipped_field = next(
            field for field in embed.fields if field.name.startswith("장착 어빌리티")
        )

        self.assertIn("괴력난신", passive_field.value)
        self.assertIn("자동 적용", embed.description)
        self.assertIn("1/", equipped_field.name)
        self.assertNotIn("괴력난신", equipped_field.value)
        self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))

        profile_embed = cog._profile_embed(profile)
        profile_passives = "\n".join(
            field.value for field in profile_embed.fields if field.name.startswith("직업 패시브")
        )
        self.assertIn("괴력난신", profile_passives)
        self.assertIn("호두용미", profile_passives)
        self.assertIn("가드하면 즉시 2단계", profile_passives)


class JobPassiveWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings_override = override_settings(
            ALLOWED_HOSTS=["testserver"],
            STORAGES={
                "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            },
        )
        self.settings_override.enable()
        self.temp_dir = tempfile.TemporaryDirectory()
        service = RPGService(
            RPGStore(Path(self.temp_dir.name) / "rpg_state.json"),
            Random(29),
        )
        self.runtime = WebRPGRuntime(service)
        self.previous_runtime = runtime_module._runtime
        runtime_module._runtime = self.runtime
        self.client = Client()
        session = self.client.session
        session["discord_user"] = {
            "id": "9101",
            "username": "passive_tester",
            "global_name": "패시브 테스터",
        }
        session.save()

    def tearDown(self) -> None:
        runtime_module._runtime = self.previous_runtime
        self.temp_dir.cleanup()
        self.settings_override.disable()

    def test_bootstrap_exposes_passive_catalog_and_unlocks_separately(self) -> None:
        profile = self.runtime.engine.service.get_profile(9101, "패시브 테스터")
        profile.level = 50
        profile.job_id = "sarasa_4"

        payload = self.client.get("/api/bootstrap/").json()
        passive = next(
            row
            for row in payload["content"]["passives"]
            if row["id"] == "sarasa_kaikiryanshin"
        )

        self.assertTrue(payload["ok"])
        self.assertIn(
            "sarasa_kaikiryanshin",
            payload["profile"]["unlocked_passive_ids"],
        )
        self.assertEqual(passive["name"], "괴력난신")
        self.assertTrue(passive["description"])
        self.assertEqual(len(payload["content"]["passives"]), len(PASSIVES))

    def test_web_ability_page_has_a_slotless_passive_section(self) -> None:
        app_source = (
            Path(__file__).resolve().parents[1]
            / "web/rpg_web/static/rpg_web/app.js"
        ).read_text(encoding="utf-8")

        self.assertIn("<h2>직업 패시브</h2>", app_source)
        self.assertIn("슬롯 없이 자동 적용", app_source)
        self.assertIn("state.profile.unlocked_passive_ids", app_source)
        self.assertIn("function unlockedPassiveRows", app_source)
        self.assertIn("profile-passives", app_source)
        self.assertIn("passiveRows(passives)", app_source)
