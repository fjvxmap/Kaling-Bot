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

from bot.services.rpg.manager import RPGService
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

        response = self.post_action("boss_start")
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["boss_session"]["started"])
        self.assertEqual(payload["boss_session"]["participant"]["turn"], 1)

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


if __name__ == "__main__":
    unittest.main()
