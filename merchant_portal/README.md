# Merchant Value-Added Services Portal — Prototype

A self-serve digital portal for merchants in the acquiring (payments) space. Merchants browse a
catalog of **value-added services (VAS)**, start a **free trial** with no charge, and — if they don't
cancel — the trial **automatically converts to a paid monthly subscription** when it ends.

This is a runnable prototype: a FastAPI backend holding the real trial → billing lifecycle, plus a
single-page web UI.

## The lifecycle it demonstrates

1. **Discover & self-subscribe** — pick a service and click *Start free trial*. No card, no charge.
2. **Trial running** — the subscription shows a live countdown ("12 days left"). Cancel anytime in the
   trial and you're never billed.
3. **Auto-subscribe** — when the trial period ends, the service auto-converts to an **Active** paid
   subscription at that service's flat monthly fee, and a next-bill date is set.

Because real trials run for weeks, the portal includes a **demo clock**. Use *+7 days* / *+30 days* in
the header to fast-forward and watch a trial convert to paid in seconds. *Reset demo* clears everything.

## Run it

From the repository root:

```bash
uv run uvicorn merchant_portal.main:app --reload --port 8000
```

Then open <http://localhost:8000>.

(FastAPI and uvicorn are already part of this repo's dependencies, so no extra install is needed. If
you're not using `uv`, `python -m uvicorn merchant_portal.main:app --port 8000` works in any env with
`fastapi` + `uvicorn` installed.)

## Try the flow

1. Click **Start free trial** on, say, *Fraud & Risk Shield*. It appears under **Your subscriptions**
   as a **Trial** with a countdown; the summary shows 1 active trial and $0 projected spend.
2. Click **+30 days**. The trial auto-converts to **Active**, a toast announces the paid subscription,
   and projected monthly spend updates to the flat fee.
3. Start another trial, then **Cancel** it before advancing — it becomes **Cancelled** and is never
   billed even after the clock moves forward.

## API

| Method & path                              | Purpose                                             |
| ------------------------------------------ | --------------------------------------------------- |
| `GET  /api/catalog`                        | List available value-added services                 |
| `GET  /api/subscriptions`                  | Merchant view: subscriptions + summary + demo clock |
| `POST /api/subscriptions`                  | Start a free trial `{ "service_id": "..." }`        |
| `POST /api/subscriptions/{id}/cancel`      | Cancel a trial or active subscription                |
| `GET  /api/summary`                        | Dashboard counts + projected monthly spend           |
| `POST /api/demo/advance`                   | Advance the demo clock `{ "days": 30 }`             |
| `POST /api/demo/reset`                     | Clear all subscriptions and reset the clock          |

## Layout

```
merchant_portal/
  main.py      # FastAPI app: JSON API + serves the SPA
  store.py     # JSON-file store + business logic (start_trial, cancel, run_conversions, demo clock)
  models.py    # Service & Subscription dataclasses + status enum
  static/      # index.html, styles.css, app.js
  data/        # store.json created at runtime (gitignored)
```

State persists to `merchant_portal/data/store.json`. Delete that file (or click *Reset demo*) to start
fresh.

> Prototype scope: a single implicit demo merchant (no auth), in-file JSON storage, and flat monthly
> pricing. It illustrates the trial → auto-subscribe experience rather than production billing.
