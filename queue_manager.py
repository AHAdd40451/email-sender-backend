from collections import deque
from threading import Lock
import time

class EmailQueue:
    def __init__(self, max_size=1000):
        self.queues = {}  # Per-user queues
        self.locks = {}   # Per-user locks
        self.max_size = max_size

    def add_batch(self, user_id, batch):
        if user_id not in self.queues:
            self.queues[user_id] = deque(maxlen=self.max_size)
            self.locks[user_id] = Lock()

        with self.locks[user_id]:
            self.queues[user_id].append({
                'batch': batch,
                'timestamp': time.time()
            })

    def get_next_batch(self, user_id):
        if user_id not in self.queues:
            return None

        with self.locks[user_id]:
            return self.queues[user_id].popleft() if self.queues[user_id] else None

    def get_queue_size(self, user_id):
        return len(self.queues.get(user_id, []))