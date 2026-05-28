from __future__ import annotations

from typing import Dict

from .number_baseball import NumberBaseball


class NumberBaseballManager:
    def __init__(self) -> None:
        self._sessions: Dict[int, tuple[int, NumberBaseball]] = {}

    def start(self, channel_id: int, user_id: int) -> tuple[str, NumberBaseball | None]:
        current = self._sessions.get(channel_id)
        if current is not None:
            owner_id, _ = current
            if owner_id == user_id:
                return ("already_running_self", None)
            return ("already_running_other", None)

        game = NumberBaseball(digits=4)
        self._sessions[channel_id] = (user_id, game)
        return ("started", game)

    def guess(self, channel_id: int, user_id: int, content: str) -> dict[str, object] | None:
        current = self._sessions.get(channel_id)
        if current is None:
            return None
        owner_id, game = current
        if owner_id != user_id:
            return None
        if not (len(content) == 4 and content.isdigit()):
            return None
        if len(set(content)) != 4:
            return {"type": "duplicate"}

        strikes, balls = game.guess(content)
        remain = game.trials - game.attempts
        if strikes == 4:
            self._sessions.pop(channel_id, None)
            return {"type": "win", "strikes": strikes}
        if remain <= 0:
            self._sessions.pop(channel_id, None)
            return {
                "type": "lose",
                "strikes": strikes,
                "balls": balls,
                "answer": game.secret_number,
            }
        return {
            "type": "progress",
            "strikes": strikes,
            "balls": balls,
            "remain": remain,
        }

    def stop(self, channel_id: int, user_id: int) -> str | None:
        current = self._sessions.get(channel_id)
        if current is None:
            return None
        owner_id, game = current
        if owner_id != user_id:
            return None
        self._sessions.pop(channel_id, None)
        return game.secret_number
