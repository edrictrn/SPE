"""Queueing event contracts, compatible with Dev1 event ordering."""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class QueueEvent:
    timestamp: float
    event_type: str
    customer_id: int
    source_station: str = "station"
    destination_station: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    sender_id: int = 0
    receiver_id: int = 0


EXTERNAL_ARRIVAL = "EXTERNAL_ARRIVAL"
TRANSFER_ARRIVAL = "TRANSFER_ARRIVAL"
SERVICE_COMPLETE = "SERVICE_COMPLETE"
