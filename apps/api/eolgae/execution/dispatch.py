"""Publish actor messages without importing execution code into the API."""
from dataclasses import dataclass
from functools import lru_cache

from eolgae.config import settings


@lru_cache(maxsize=1)
def _broker():
    from dramatiq.brokers.redis import RedisBroker
    return RedisBroker(url=settings.valkey_url)


@dataclass
class QueuedOperation:
    actor_name: str

    def send(self, deployment_id: str):
        if not settings.direct_execution_enabled:
            raise RuntimeError("Direct execution is disabled")
        from dramatiq import Message
        return _broker().enqueue(Message(
            queue_name="apply", actor_name=self.actor_name,
            args=(deployment_id,), kwargs={}, options={},
        ))


run_plan = QueuedOperation("run_plan")
run_apply = QueuedOperation("run_apply")
run_destroy = QueuedOperation("run_destroy")
