"""Dramatiq workers.

Apply queue, AWS polling (2차 MVP), drift detection (2차) 등 background 작업 정의.
Valkey 가 Redis 호환 broker 역할.
"""
import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

broker = RedisBroker(url=os.environ.get("VALKEY_URL", "redis://localhost:6379/0"))
dramatiq.set_broker(broker)

# Actor registration for `dramatiq eolgae.workers`.
from eolgae.workers.plan import run_apply, run_destroy, run_plan  # noqa: E402,F401
