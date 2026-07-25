"""FastAPI application for the merchant self-serve trial → subscription portal.

Serves a small JSON API plus a single-page web UI (from ``static/``).

Run it with::

    uv run uvicorn merchant_portal.main:app --reload --port 8000

then open http://localhost:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import store

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Merchant Value-Added Services Portal")


# --------------------------------------------------------------------------- #
# Request bodies                                                              #
# --------------------------------------------------------------------------- #
class StartTrialBody(BaseModel):
    service_id: str


class AdvanceBody(BaseModel):
    days: int = 7


# --------------------------------------------------------------------------- #
# API routes                                                                  #
# --------------------------------------------------------------------------- #
@app.get("/api/catalog")
def catalog() -> dict:
    return {"services": store.get_catalog()}


@app.get("/api/subscriptions")
def subscriptions() -> dict:
    """Full merchant view: subscriptions, summary and demo clock."""
    return store.get_view()


@app.post("/api/subscriptions")
def create_subscription(body: StartTrialBody) -> dict:
    try:
        sub = store.start_trial(body.service_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"subscription": sub.to_dict(), "view": store.get_view()}


@app.post("/api/subscriptions/{subscription_id}/cancel")
def cancel_subscription(subscription_id: str) -> dict:
    try:
        sub = store.cancel(subscription_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"subscription": sub.to_dict(), "view": store.get_view()}


@app.get("/api/summary")
def summary() -> dict:
    return store.get_view()["summary"]


@app.post("/api/demo/advance")
def demo_advance(body: AdvanceBody) -> dict:
    store.advance_clock(body.days)
    return store.get_view()


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    store.reset()
    return store.get_view()


# --------------------------------------------------------------------------- #
# Static single-page UI                                                       #
# --------------------------------------------------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
