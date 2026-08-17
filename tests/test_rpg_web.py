from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from random import Random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kaling_web.settings")

import django

django.setup()

from django.test import Client, override_settings

from bot.services.rpg.data import LIBERATION
from bot.services.rpg.manager import RPGService
from bot.services.rpg.models import ItemInstance
from bot.services.rpg.store import RPGStore
from rpg_web import runtime as runtime_module
from rpg_web.runtime import WebRPGRuntime


class RPGWebTests(unittest.TestCase):
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
        state_path = Path(self.temp_dir.name) / "rpg_state.json"
        service = RPGService(RPGStore(state_path), Random(7))
        self.runtime = WebRPGRuntime(service)
        self.previous_runtime = runtime_module._runtime
        runtime_module._runtime = self.runtime
        self.client = Client()
        session = self.client.session
        session["discord_user"] = {
            "id": "9001",
            "username": "web_tester",
            "global_name": "웹 테스터",
        }
        session.save()

    def tearDown(self) -> None:
        runtime_module._runtime = self.previous_runtime
        self.temp_dir.cleanup()
        self.settings_override.disable()

    def post_action(self, action_type: str, **payload):
        return self.client.post(
            "/api/action/",
            data=json.dumps({"type": action_type, **payload}),
            content_type="application/json",
        )

    def test_root_is_rpg_and_bootstrap_contains_hard_modes(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Kaling RPG", response.content)
        self.assertNotIn(b"Weekly availability", response.content)

        response = self.client.get("/api/bootstrap/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["profile"]["user_id"], "9001")
        self.assertTrue(payload["content"]["bosses"])
        self.assertTrue(all(
            {variant["difficulty"] for variant in boss["variants"]} == {"normal", "hard"}
            for boss in payload["content"]["bosses"]
        ))
        lotus = next(boss for boss in payload["content"]["bosses"] if boss["base_id"] == "lotus")
        normal = next(row for row in lotus["variants"] if row["difficulty"] == "normal")
        hard = next(row for row in lotus["variants"] if row["difficulty"] == "hard")
        self.assertEqual(hard["description"], normal["description"])
        self.assertFalse(any("해방 전 하드 솔로" in reward for reward in normal["rewards"]))
        self.assertTrue(any("해방 전 하드 솔로 확정 1개" in reward for reward in hard["rewards"]))

    def test_explore_and_practice_boss_use_shared_service(self) -> None:
        dungeon_id = self.runtime.engine.service.dungeons()[0].id
        response = self.post_action("explore", dungeon_id=dungeon_id, count=1)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["result"]["runs"]), 1)

        boss = next(boss for boss in self.runtime.engine.service.bosses() if boss.difficulty == "normal")
        response = self.post_action("boss_create", boss_id=boss.id, practice=True)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["boss_session"]["started"])
        session_id = payload["boss_session"]["id"]

        response = self.post_action("boss_start")
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["boss_session"]["started"])
        self.assertEqual(payload["boss_session"]["participant"]["turn"], 1)
        self.assertEqual(payload["boss_session"]["id"], session_id)

        response = self.post_action("boss_attack")
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["boss_session"]["id"], session_id)

        session = self.runtime.active_session(9001)
        self.assertIsNotNone(session)
        session.log.extend(f"고정 로그 {index}" for index in range(20))
        response = self.client.get("/api/bootstrap/")
        payload = response.json()
        self.assertEqual(payload["boss_session"]["log"], session.log[-16:])
        self.assertEqual(payload["boss_session"]["log_start_index"], len(session.log) - 16)

    def test_hard_boss_initial_stack_is_exposed_to_web_client(self) -> None:
        response = self.post_action(
            "boss_create",
            boss_id="first_adversary_hard",
            practice=True,
        )
        self.assertTrue(response.json()["ok"])

        response = self.post_action("boss_start")
        payload = response.json()

        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["boss_session"]["participant"]["boss_stacks"],
            "대적의 의지 (하드) lv.3",
        )

    def test_genesis_weapon_skill_uses_its_own_web_slot_and_blocks_a_turn(self) -> None:
        service = self.runtime.engine.service
        profile = service.get_profile(9001, "웹 테스터")
        profile.job_id = "hero"
        profile.cleared_boss_ids.append(LIBERATION.boss_id)
        claim = service.claim_genesis_weapon(9001, "웹 테스터")
        self.assertTrue(claim.ok)
        for stage in LIBERATION.stages:
            profile.materials.update(stage.materials)
            self.assertTrue(service.advance_genesis_liberation(9001, "웹 테스터").ok)
        self.assertTrue(service.equip_item(9001, "웹 테스터", claim.item.uid).ok)

        bootstrap = self.client.get("/api/bootstrap/").json()
        genesis_skill = bootstrap["profile"]["genesis_weapon_skill"]
        self.assertTrue(genesis_skill["unlocked"])
        self.assertTrue(genesis_skill["active"])
        self.assertEqual(genesis_skill["name"], "창조의 아이온")
        self.assertIn("무적", genesis_skill["summary"])

        response = self.post_action(
            "boss_create",
            boss_id="guardian_angel_slime",
            practice=True,
        )
        self.assertTrue(response.json()["ok"])
        started = self.post_action("boss_start").json()
        self.assertTrue(started["ok"])
        self.assertIn("genesis_creation_ion", {skill["id"] for skill in started["boss_session"]["skills"]})
        before_hp = started["boss_session"]["participant"]["hp"]

        activated = self.post_action("boss_ability", skill_id="genesis_creation_ion").json()
        self.assertTrue(activated["ok"])
        self.assertIn("무적", activated["boss_session"]["participant"]["player_effects"])
        advanced = self.post_action("boss_attack").json()
        self.assertTrue(advanced["ok"])
        self.assertEqual(advanced["boss_session"]["participant"]["hp"], before_hp)

    def test_waiting_boss_cancel_returns_to_selection(self) -> None:
        boss = next(
            boss
            for boss in self.runtime.engine.service.bosses()
            if boss.difficulty == "normal"
        )
        response = self.post_action("boss_create", boss_id=boss.id, practice=True)
        self.assertTrue(response.json()["ok"])

        response = self.post_action("boss_cancel")
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["boss_session"])
        self.assertIsNone(self.runtime.active_session(9001))

    def test_enhance_response_includes_cost_odds_balance_and_next_preview(self) -> None:
        service = self.runtime.engine.service
        profile = service.get_profile(9001, "웹 테스터")
        item = ItemInstance(uid=1, template_id="wooden_sword")
        profile.inventory = [item]
        profile.next_item_uid = 2
        profile.gold = 10_000
        service._save()

        preview = service.enhancement_preview(9001, "웹 테스터", item.uid, "gold")
        self.assertTrue(preview.ok)

        response = self.post_action("enhance", item_uid=item.uid, method_id="gold")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        result = payload["result"]
        self.assertEqual(result["item_uid"], item.uid)
        self.assertEqual(result["cost"], preview.cost)
        self.assertEqual(
            result["odds"],
            {
                "success": preview.odds[0],
                "fail": preview.odds[1],
                "destroy": preview.odds[2],
            },
        )
        self.assertEqual(result["material_cost_rows"], [])
        self.assertEqual(result["remaining_gold"], 10_000 - preview.cost)
        self.assertEqual(payload["profile"]["gold"], result["remaining_gold"])

        next_preview = result["next_preview"]
        self.assertIsNotNone(next_preview)
        self.assertEqual(next_preview["item_uid"], item.uid)
        self.assertEqual(next_preview["before_stars"], result["after_stars"])
        self.assertEqual(next_preview["method_id"], "gold")
        self.assertEqual(set(next_preview["odds"]), {"success", "fail", "destroy"})

    def test_restore_response_does_not_include_next_enhancement_preview(self) -> None:
        service = self.runtime.engine.service
        profile = service.get_profile(9001, "웹 테스터")
        trace = ItemInstance(
            uid=1,
            template_id="wooden_sword",
            stars=4,
            destroyed=True,
        )
        spare = ItemInstance(uid=2, template_id="wooden_sword")
        profile.inventory = [trace, spare]
        profile.next_item_uid = 3
        profile.gold = 10_000
        service._save()

        preview = service.restore_preview(9001, "웹 테스터", trace.uid, spare.uid)
        self.assertTrue(preview.ok)

        response = self.post_action("restore", item_uid=trace.uid, spare_uid=spare.uid)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])

        result = payload["result"]
        self.assertEqual(result["item_uid"], trace.uid)
        self.assertEqual(result["cost"], preview.cost)
        self.assertEqual(result["remaining_gold"], 10_000 - preview.cost)
        self.assertEqual(payload["profile"]["gold"], result["remaining_gold"])
        self.assertIsNone(result["next_preview"])


if __name__ == "__main__":
    unittest.main()
