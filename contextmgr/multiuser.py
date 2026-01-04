from typing import Dict

class SessionManager:
    def __init__(self):
        self._map: Dict[str, str] = {}

    def thread_for(self, user_id: str) -> str:
        if user_id not in self._map:
            self._map[user_id] = f"u:{user_id}"
        return self._map[user_id]

