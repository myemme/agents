"""JSON-file-backed data store and business logic for the portal prototype.

This module is the "brain" of the prototype. It owns:

* the seed catalog of value-added services,
* the merchant's subscriptions,
* a **demo clock** offset (in days) so a reviewer can fast-forward time and
  watch a free trial auto-convert to a paid subscription in seconds, and
* the core lifecycle logic: ``start_trial``, ``cancel`` and — most importantly —
  ``run_conversions`` which turns expired trials into paid subscriptions.

There is a single implicit "demo merchant"; no authentication is needed for a
merchant-only prototype.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Service, Subscription, SubscriptionStatus

DATA_DIR = Path(__file__).parent / "data"
STORE_FILE = DATA_DIR / "store.json"

# Serialise all mutations — uvicorn may serve requests from multiple threads.
_LOCK = threading.RLock()


# --------------------------------------------------------------------------- #
# Seed catalog                                                                #
# --------------------------------------------------------------------------- #
def _seed_services() -> list[Service]:
    """The catalog of acquiring-space value-added services a merchant can try."""
    return [
        Service(
            id="fraud-shield",
            name="Fraud & Risk Shield",
            category="Risk",
            description="Real-time transaction scoring and rules to block fraud before it settles.",
            emoji="🛡️",
            trial_days=30,
            monthly_price=49.0,
        ),
        Service(
            id="analytics-dashboard",
            name="Analytics & Insights Dashboard",
            category="Insights",
            description="Live sales, settlement and customer analytics across all your terminals.",
            emoji="📊",
            trial_days=14,
            monthly_price=29.0,
        ),
        Service(
            id="chargeback-manager",
            name="Chargeback Manager",
            category="Disputes",
            description="Automated dispute alerts and one-click evidence submission to win chargebacks.",
            emoji="⚖️",
            trial_days=30,
            monthly_price=39.0,
        ),
        Service(
            id="loyalty-rewards",
            name="Loyalty & Rewards",
            category="Growth",
            description="Launch a branded points & rewards program that drives repeat customers.",
            emoji="🎁",
            trial_days=14,
            monthly_price=25.0,
        ),
        Service(
            id="smart-invoicing",
            name="Smart Invoicing",
            category="Billing",
            description="Send digital invoices with pay-by-link and automatic reconciliation.",
            emoji="🧾",
            trial_days=30,
            monthly_price=19.0,
        ),
        Service(
            id="cashflow-insights",
            name="Cashflow Advance Insights",
            category="Capital",
            description="Forecast cashflow and see pre-qualified merchant cash advance offers.",
            emoji="💵",
            trial_days=14,
            monthly_price=35.0,
        ),
    ]


def _default_state() -> dict:
    return {
        "clock_offset_days": 0,       # demo clock: simulated days added to real "now"
        "services": [s.to_dict() for s in _seed_services()],
        "subscriptions": [],          # list of Subscription dicts
    }


# --------------------------------------------------------------------------- #
# Persistence                                                                 #
# --------------------------------------------------------------------------- #
def _load() -> dict:
    if not STORE_FILE.exists():
        state = _default_state()
        _save(state)
        return state
    with STORE_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _save(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with STORE_FILE.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


# --------------------------------------------------------------------------- #
# Clock helpers                                                               #
# --------------------------------------------------------------------------- #
def _effective_now(state: dict) -> datetime:
    """Real UTC now plus the demo clock offset."""
    return datetime.now(timezone.utc) + timedelta(days=state.get("clock_offset_days", 0))


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts)


# --------------------------------------------------------------------------- #
# Core lifecycle                                                              #
# --------------------------------------------------------------------------- #
def run_conversions(state: dict) -> list[dict]:
    """Convert any expired free trials into paid subscriptions.

    This is the heart of the prototype. Called lazily before every read so the
    state a merchant sees is always current for the (possibly fast-forwarded)
    demo clock.

    Returns a list of ``{"service_id", "name", "monthly_price"}`` describing the
    subscriptions that *just* converted, so the API/UI can announce them.
    """
    now = _effective_now(state)
    services = {s["id"]: s for s in state["services"]}
    just_converted: list[dict] = []

    for sub in state["subscriptions"]:
        if sub["status"] != SubscriptionStatus.TRIAL.value:
            continue
        trial_end = _parse(sub.get("trial_ends_at"))
        if trial_end and now >= trial_end:
            svc = services.get(sub["service_id"], {})
            sub["status"] = SubscriptionStatus.ACTIVE.value
            sub["converted_at"] = now.isoformat()
            # First bill lands one month after the trial ended.
            sub["next_bill_date"] = (trial_end + timedelta(days=30)).isoformat()
            just_converted.append(
                {
                    "service_id": sub["service_id"],
                    "name": svc.get("name", sub["service_id"]),
                    "monthly_price": svc.get("monthly_price", 0.0),
                }
            )
    return just_converted


def start_trial(service_id: str) -> Subscription:
    """Begin a free trial for the given service.

    Guards against starting a trial for a service the merchant already has an
    active or trialing subscription to.
    """
    with _LOCK:
        state = _load()
        run_conversions(state)

        services = {s["id"]: s for s in state["services"]}
        if service_id not in services:
            _save(state)
            raise KeyError(f"Unknown service '{service_id}'")

        for sub in state["subscriptions"]:
            if sub["service_id"] == service_id and sub["status"] in (
                SubscriptionStatus.TRIAL.value,
                SubscriptionStatus.ACTIVE.value,
            ):
                _save(state)
                raise ValueError("You already have an active subscription for this service.")

        svc = services[service_id]
        now = _effective_now(state)
        subscription = Subscription(
            id=str(uuid.uuid4()),
            service_id=service_id,
            status=SubscriptionStatus.TRIAL,
            started_at=now.isoformat(),
            trial_ends_at=(now + timedelta(days=svc["trial_days"])).isoformat(),
        )
        state["subscriptions"].append(subscription.to_dict())
        _save(state)
        return subscription


def cancel(subscription_id: str) -> Subscription:
    """Cancel a subscription.

    Cancelling during the trial means the merchant is *never* charged; cancelling
    an active subscription stops future billing.
    """
    with _LOCK:
        state = _load()
        run_conversions(state)

        now = _effective_now(state)
        for sub in state["subscriptions"]:
            if sub["id"] == subscription_id:
                if sub["status"] == SubscriptionStatus.CANCELLED.value:
                    _save(state)
                    raise ValueError("Subscription is already cancelled.")
                sub["status"] = SubscriptionStatus.CANCELLED.value
                sub["cancelled_at"] = now.isoformat()
                sub["next_bill_date"] = None
                _save(state)
                return Subscription.from_dict(sub)
        _save(state)
        raise KeyError(f"Unknown subscription '{subscription_id}'")


# --------------------------------------------------------------------------- #
# Read / view helpers                                                         #
# --------------------------------------------------------------------------- #
def get_catalog() -> list[dict]:
    with _LOCK:
        state = _load()
        return state["services"]


def get_view() -> dict:
    """Return the full merchant view: subscriptions (enriched) + summary + clock.

    Runs conversions first and reports anything that just converted.
    """
    with _LOCK:
        state = _load()
        just_converted = run_conversions(state)
        _save(state)

        now = _effective_now(state)
        services = {s["id"]: s for s in state["services"]}

        subscriptions = []
        for sub in state["subscriptions"]:
            svc = services.get(sub["service_id"], {})
            enriched = dict(sub)
            enriched["service"] = svc
            trial_end = _parse(sub.get("trial_ends_at"))
            if sub["status"] == SubscriptionStatus.TRIAL.value and trial_end:
                enriched["trial_days_left"] = max(0, (trial_end - now).days)
            else:
                enriched["trial_days_left"] = None
            subscriptions.append(enriched)

        # Newest first.
        subscriptions.sort(key=lambda s: s.get("started_at") or "", reverse=True)

        active = [s for s in subscriptions if s["status"] == SubscriptionStatus.ACTIVE.value]
        trials = [s for s in subscriptions if s["status"] == SubscriptionStatus.TRIAL.value]
        monthly_spend = sum(s["service"].get("monthly_price", 0.0) for s in active)

        return {
            "clock": {
                "offset_days": state.get("clock_offset_days", 0),
                "simulated_date": now.date().isoformat(),
            },
            "summary": {
                "active_trials": len(trials),
                "paid_subscriptions": len(active),
                "monthly_spend": round(monthly_spend, 2),
            },
            "subscriptions": subscriptions,
            "just_converted": just_converted,
        }


# --------------------------------------------------------------------------- #
# Demo controls                                                               #
# --------------------------------------------------------------------------- #
def advance_clock(days: int) -> None:
    """Move the demo clock forward.

    Note: conversions are intentionally *not* run here — they're applied lazily
    by ``get_view`` on the next read, which lets the caller surface exactly which
    trials just converted (see ``just_converted`` in the view).
    """
    with _LOCK:
        state = _load()
        state["clock_offset_days"] = state.get("clock_offset_days", 0) + int(days)
        _save(state)


def reset() -> None:
    """Wipe all subscriptions and reset the demo clock back to real time."""
    with _LOCK:
        _save(_default_state())
