from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class ItemInstance:
    uid: int
    template_id: str
    stars: int = 0
    destroyed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemInstance":
        return cls(
            uid=int(data.get("uid", 0)),
            template_id=str(data.get("template_id", "")),
            stars=max(0, int(data.get("stars", 0))),
            destroyed=bool(data.get("destroyed", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerProfile:
    version: int = 1
    user_id: int = 0
    display_name: str = "Player"
    job_id: str = "novice"
    level: int = 1
    exp: int = 0
    gold: int = 130
    stat_points: int = 0
    base_atk_points: int = 0
    max_hp_points: int = 0
    defense_points: int = 0
    base_atk: int = 12
    max_hp: int = 120
    atk: float = 0.0
    defense: float = 0.08
    garrison: float = 0.0
    strength: float = 0.0
    enmity: float = 0.0
    damage_cut: float = 0.0
    dmg_mitigation: float = 0.0
    dmg_amplification: float = 0.0
    hp_bonus: float = 0.0
    daily_date: str = ""
    daily_explores_used: int = 0
    weekly_boss_clears: dict[str, str] = field(default_factory=dict)
    boss_clear_count: int = 0
    dungeon_clear_count: int = 0
    inventory: list[ItemInstance] = field(default_factory=list)
    next_item_uid: int = 1

    @classmethod
    def create(cls, user_id: int, display_name: str) -> "PlayerProfile":
        return cls(user_id=user_id, display_name=display_name or "Player")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerProfile":
        known = {field.name for field in fields(cls)}
        profile = cls()
        for key, value in data.items():
            if key not in known:
                continue
            if key == "inventory" and isinstance(value, list):
                profile.inventory = [
                    ItemInstance.from_dict(item)
                    for item in value
                    if isinstance(item, dict)
                ]
            elif key == "weekly_boss_clears" and isinstance(value, dict):
                profile.weekly_boss_clears = {
                    str(boss_id): str(week_key)
                    for boss_id, week_key in value.items()
                }
            else:
                setattr(profile, key, value)
        profile.version = 1
        profile.user_id = int(profile.user_id)
        profile.level = max(1, int(profile.level))
        profile.job_id = str(profile.job_id or "novice")
        profile.exp = max(0, int(profile.exp))
        profile.gold = max(0, int(profile.gold))
        profile.stat_points = max(0, int(profile.stat_points))
        profile.daily_explores_used = max(0, int(profile.daily_explores_used))
        profile.next_item_uid = max(1, int(profile.next_item_uid))
        return profile

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["inventory"] = [item.to_dict() for item in self.inventory]
        return data


@dataclass
class CombatStats:
    base_atk: int
    max_hp: int
    hp_bonus: float = 0.0
    atk: float = 0.0
    defense: float = 0.0
    garrison: float = 0.0
    strength: float = 0.0
    enmity: float = 0.0
    damage_cut: float = 0.0
    dmg_mitigation: float = 0.0
    dmg_amplification: float = 0.0

    @property
    def final_hp(self) -> int:
        return max(1, int(self.max_hp * (1 + self.hp_bonus)))

    def copy(self) -> "CombatStats":
        return CombatStats(**asdict(self))
