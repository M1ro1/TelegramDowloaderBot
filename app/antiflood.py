import time


class AntiFloodGuard:
    def __init__(self, max_requests: int, time_window: float, mute_duration: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.mute_duration = mute_duration
        self.user_requests = {}
        self.muted_users = {}

    def is_rate_limited(self, user_id: int) -> bool:
        current_time = time.time()

        if user_id in self.muted_users:
            if current_time < self.muted_users[user_id]:
                return True
            del self.muted_users[user_id]

        if user_id not in self.user_requests:
            self.user_requests[user_id] = []

        self.user_requests[user_id] = [
            t for t in self.user_requests[user_id] if current_time - t < self.time_window
        ]

        if len(self.user_requests[user_id]) >= self.max_requests:
            self.muted_users[user_id] = current_time + self.mute_duration
            self.user_requests[user_id] = []
            return True

        self.user_requests[user_id].append(current_time)
        return False

