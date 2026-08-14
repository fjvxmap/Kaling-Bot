from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from bot.cogs.rpg import BossSession, RPGCog
from bot.services.rpg.manager import PotentialCandidate, RPGService
from bot.services.rpg.models import PotentialLine


@dataclass
class PendingPotential:
    item_uid: int
    before_grade: str
    before_lines: list[PotentialLine]
    candidates: list[PotentialCandidate]
    required_grade: str = ""


class WebRPGRuntime:
    def __init__(self, service: RPGService | None = None) -> None:
        self.lock = RLock()
        self.engine = RPGCog.__new__(RPGCog)
        self.engine.bot = None
        self.engine.service = service or RPGService()
        self.engine.boss_sessions = {}
        self.engine._boss_damage_detail_messages = {}
        self.engine._next_boss_session_id = 1
        self.pending_potentials: dict[int, PendingPotential] = {}

    def active_session(self, user_id: int) -> BossSession | None:
        return self.engine._active_boss_session_for_user(user_id)


_runtime: WebRPGRuntime | None = None
_runtime_lock = RLock()


def get_runtime() -> WebRPGRuntime:
    global _runtime
    if _runtime is None:
        with _runtime_lock:
            if _runtime is None:
                _runtime = WebRPGRuntime()
    return _runtime
