# Compatibility shim — canonical location: src.pipeline.queue_selector
from src.pipeline.queue_selector import (  # noqa: F401
    QueueSelector,
    RoundRobinQueueSelector,
    WeightedRoundRobinQueueSelector,
)

__all__ = ["QueueSelector", "RoundRobinQueueSelector", "WeightedRoundRobinQueueSelector"]
