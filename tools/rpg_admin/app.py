from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "bot" / "services" / "rpg" / "content"
STATIC_DIR = Path(__file__).with_name("static")
BACKUP_DIR = ROOT / ".rpg_content_backups"

SIMPLE_FILES = {
    "settings": "settings.json",
    "stats": "stats.json",
    "rarities": "rarities.json",
    "level_curve": "level_curve.json",
    "player": "player.json",
    "stat_allocation": "stat_allocation.json",
    "enhancement": "enhancement.json",
    "drop_rarity_weights": "drop_rarity_weights.json",
    "items": "items.json",
    "jobs": "jobs.json",
    "skills": "skills.json",
    "materials": "materials.json",
    "crafting_recipes": "crafting_recipes.json",
}

ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_content() -> dict[str, Any]:
    content = {
        key: read_json(CONTENT_DIR / filename)
        for key, filename in SIMPLE_FILES.items()
    }
    content["dungeons"] = read_split_dir(CONTENT_DIR / "dungeons")
    content["bosses"] = read_split_dir(CONTENT_DIR / "bosses")
    return content


def read_split_dir(path: Path) -> list[dict[str, Any]]:
    rows = [read_json(file) for file in sorted(path.glob("*.json"))]
    return sorted(rows, key=lambda row: (int(row.get("sort_order", 9999)), str(row.get("id", ""))))


def save_content(content: dict[str, Any]) -> Path:
    errors = validate_content(content)
    if errors:
        raise ValueError("\n".join(errors))

    backup_path = backup_content()
    for key, filename in SIMPLE_FILES.items():
        write_json(CONTENT_DIR / filename, content.get(key, [] if key in list_keys() else {}))
    write_split_dir(CONTENT_DIR / "dungeons", content.get("dungeons", []))
    write_split_dir(CONTENT_DIR / "bosses", content.get("bosses", []))
    return backup_path


def list_keys() -> set[str]:
    return {"items", "jobs", "skills", "materials", "crafting_recipes"}


def backup_content() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = BACKUP_DIR / timestamp
    suffix = 2
    while destination.exists():
        destination = BACKUP_DIR / f"{timestamp}_{suffix}"
        suffix += 1
    if CONTENT_DIR.exists():
        shutil.copytree(CONTENT_DIR, destination)
    return destination


def write_split_dir(path: Path, rows: list[dict[str, Any]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    desired = set()
    for index, row in enumerate(rows, start=1):
        row_id = str(row["id"])
        row.setdefault("sort_order", index * 10)
        desired.add(f"{row_id}.json")
        write_json(path / f"{row_id}.json", row)
    for file in path.glob("*.json"):
        if file.name not in desired:
            file.unlink()


def validate_content(content: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rarities = set(content.get("rarities", {}).get("order", []))
    items = ensure_unique_ids(content.get("items", []), "item", errors)
    materials = ensure_unique_ids(content.get("materials", []), "material", errors)
    jobs = ensure_unique_ids(content.get("jobs", []), "job", errors)
    skills = ensure_unique_ids(content.get("skills", []), "skill", errors)
    recipes = ensure_unique_ids(content.get("crafting_recipes", []), "crafting recipe", errors)
    dungeons = ensure_unique_ids(content.get("dungeons", []), "dungeon", errors)
    bosses = ensure_unique_ids(content.get("bosses", []), "boss", errors)

    for item in content.get("items", []):
        check_rarity(item.get("rarity"), rarities, f"item {item.get('id')}", errors)
    for material in content.get("materials", []):
        check_rarity(material.get("rarity"), rarities, f"material {material.get('id')}", errors)
    for job in content.get("jobs", []):
        parent_id = str(job.get("parent_id", ""))
        if parent_id and parent_id not in jobs:
            errors.append(f"job {job.get('id')} parent not found: {parent_id}")
    for skill in content.get("skills", []):
        for job_id in skill.get("job_ids", []):
            if job_id not in jobs:
                errors.append(f"skill {skill.get('id')} job not found: {job_id}")
    for recipe in content.get("crafting_recipes", []):
        if recipe.get("result_item_id") not in items:
            errors.append(f"recipe {recipe.get('id')} result item not found: {recipe.get('result_item_id')}")
        for material_id in recipe.get("materials", {}):
            if material_id not in materials:
                errors.append(f"recipe {recipe.get('id')} material not found: {material_id}")
    for dungeon in content.get("dungeons", []):
        enemy_ids = ensure_unique_ids(dungeon.get("enemies", []), f"dungeon {dungeon.get('id')} enemy", errors)
        if not enemy_ids:
            errors.append(f"dungeon {dungeon.get('id')} has no enemies")
        for enemy in dungeon.get("enemies", []):
            validate_reward(enemy.get("rewards", {}), items, materials, rarities, f"enemy {enemy.get('id')} rewards", errors)
            validate_reward(enemy.get("consolation_rewards", {}), items, materials, rarities, f"enemy {enemy.get('id')} consolation", errors)
    for boss in content.get("bosses", []):
        pattern_ids = ensure_unique_ids(boss.get("patterns", []), f"boss {boss.get('id')} pattern", errors)
        for warning in boss.get("hp_warnings", []):
            if warning.get("pattern_id") not in pattern_ids:
                errors.append(f"boss {boss.get('id')} hp warning pattern not found: {warning.get('pattern_id')}")
        for warning in boss.get("ct", {}).get("warnings_by_hp", []):
            if warning.get("pattern_id") not in pattern_ids:
                errors.append(f"boss {boss.get('id')} ct warning pattern not found: {warning.get('pattern_id')}")
        validate_reward(boss.get("rewards", {}), items, materials, rarities, f"boss {boss.get('id')} rewards", errors)

    for label, ids in (("skills", skills), ("recipes", recipes), ("dungeons", dungeons), ("bosses", bosses)):
        if not ids:
            errors.append(f"no {label} configured")
    return errors


def ensure_unique_ids(rows: Any, label: str, errors: list[str]) -> set[str]:
    if not isinstance(rows, list):
        errors.append(f"{label} list is not an array")
        return set()
    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("id", ""))
        if not row_id:
            errors.append(f"{label} missing id")
            continue
        if not ID_RE.match(row_id):
            errors.append(f"{label} has invalid id: {row_id}")
        if row_id in seen:
            errors.append(f"{label} duplicate id: {row_id}")
        seen.add(row_id)
    return seen


def check_rarity(rarity: Any, rarities: set[str], label: str, errors: list[str]) -> None:
    if str(rarity) not in rarities:
        errors.append(f"{label} rarity not found: {rarity}")


def validate_reward(
    reward: dict[str, Any],
    items: set[str],
    materials: set[str],
    rarities: set[str],
    label: str,
    errors: list[str],
) -> None:
    for drop in reward.get("items", []):
        template_id = str(drop.get("template_id", drop.get("item_id", "")))
        if template_id and template_id not in items:
            errors.append(f"{label} item not found: {template_id}")
        rarity = str(drop.get("rarity", ""))
        if rarity and rarity not in rarities:
            errors.append(f"{label} rarity not found: {rarity}")
    for drop in reward.get("materials", []):
        material_id = str(drop.get("id", ""))
        if material_id not in materials:
            errors.append(f"{label} material not found: {material_id}")


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "RPGAdmin/1.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_static("index.html")
        elif path == "/api/content":
            self.send_json({"ok": True, "content": read_content()})
        elif path.startswith("/static/"):
            self.send_static(path.removeprefix("/static/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self.read_json_body()
        if path == "/api/validate":
            errors = validate_content(payload.get("content", {}))
            self.send_json({"ok": not errors, "errors": errors})
            return
        if path == "/api/save":
            content = payload.get("content", {})
            try:
                backup_path = save_content(content)
            except ValueError as exc:
                self.send_json({"ok": False, "errors": str(exc).splitlines()}, status=HTTPStatus.BAD_REQUEST)
                return
            self.send_json({"ok": True, "backup": str(backup_path.relative_to(ROOT))})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_static(self, relative_path: str) -> None:
        path = (STATIC_DIR / relative_path).resolve()
        if not str(path).startswith(str(STATIC_DIR.resolve())) or not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif path.suffix == ".js":
            content_type = "text/javascript; charset=utf-8"
        raw = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[rpg-admin] {self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local RPG content admin UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AdminHandler)
    print(f"RPG admin UI: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
