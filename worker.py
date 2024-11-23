import os
from rq import Worker, Queue, Connection
from redis import Redis
from queue_config import redis_conn

# List of queue names to monitor
QUEUE_NAMES = ['high', 'default', 'low']

def start_worker():
    try:
        with Connection(redis_conn):
            queues = [Queue(name) for name in QUEUE_NAMES]
            worker = Worker(queues)
            worker.work(with_scheduler=True)
    except Exception as e:
        print(f"Worker error: {e}")
        raise

if __name__ == '__main__':
    start_worker()