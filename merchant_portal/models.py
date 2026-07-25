"""Domain models for the merchant self-serve trial → subscription portal.

Plain dataclasses/enums kept intentionally lightweight so the prototype has no
ORM or database dependency — everything is serialised to a small JSON file by
``store.py``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Lifecycle states for a merchant's subscription to a value-added service."""

    TRIAL = "trial"        # free trial running, no charge
    ACTIVE = "active"      # trial ended, now a paid subscription
    CANCELLED = "cancelled"  # merchant opted out (never billed if cancelled in trial)


@dataclass
class Service:
    """A value-added service offered in the acquiring platform catalog."""

    id: str
    name: str
    category: str
    description: str
    emoji: str
    trial_days: int
    monthly_price: float  # flat monthly fee charged once the trial converts

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Subscription:
    """A merchant's subscription to a single service.

    All timestamps are ISO-8601 strings (or ``None``) so the whole object is
    trivially JSON serialisable.
    """

    id: str
    service_id: str
    status: SubscriptionStatus = SubscriptionStatus.TRIAL
    started_at: str | None = None       # when the free trial began
    trial_ends_at: str | None = None    # when the trial converts to paid
    converted_at: str | None = None     # when it auto-converted to ACTIVE
    cancelled_at: str | None = None     # when the merchant cancelled
    next_bill_date: str | None = None   # next monthly charge date once ACTIVE

    def to_dict(self) -> dict:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Subscription":
        return cls(
            id=data["id"],
            service_id=data["service_id"],
            status=SubscriptionStatus(data.get("status", "trial")),
            started_at=data.get("started_at"),
            trial_ends_at=data.get("trial_ends_at"),
            converted_at=data.get("converted_at"),
            cancelled_at=data.get("cancelled_at"),
            next_bill_date=data.get("next_bill_date"),
        )
