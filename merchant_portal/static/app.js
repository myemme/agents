// Merchant self-serve trial → subscription portal — front-end logic.
// Talks to the FastAPI JSON API and renders the dashboard, subscriptions and catalog.

const api = {
  async get(path) {
    const res = await fetch(path);
    if (!res.ok) throw await toError(res);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    });
    if (!res.ok) throw await toError(res);
    return res.json();
  },
};

async function toError(res) {
  let detail = res.statusText;
  try {
    const data = await res.json();
    detail = data.detail || detail;
  } catch (_) { /* ignore */ }
  return new Error(detail);
}

const money = (n) => "$" + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

// --------------------------------------------------------------------------- //
// Toasts                                                                      //
// --------------------------------------------------------------------------- //
function toast(title, body, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<div class="toast-title"></div><div class="toast-body"></div>`;
  el.querySelector(".toast-title").textContent = title;
  el.querySelector(".toast-body").textContent = body || "";
  document.getElementById("toasts").appendChild(el);
  setTimeout(() => el.remove(), 5200);
}

function announceConversions(list) {
  (list || []).forEach((c) => {
    toast("Trial converted to paid", `${c.name} is now a paid subscription at ${money(c.monthly_price)}/mo.`, "convert");
  });
}

// --------------------------------------------------------------------------- //
// State + rendering                                                           //
// --------------------------------------------------------------------------- //
let catalog = [];

async function loadCatalog() {
  const data = await api.get("/api/catalog");
  catalog = data.services;
}

async function refresh() {
  const view = await api.get("/api/subscriptions");
  render(view);
  return view;
}

function render(view) {
  // Clock
  document.getElementById("clock-date").textContent = fmtDate(view.clock.simulated_date);

  // Summary
  document.getElementById("stat-trials").textContent = view.summary.active_trials;
  document.getElementById("stat-active").textContent = view.summary.paid_subscriptions;
  document.getElementById("stat-spend").textContent = money(view.summary.monthly_spend) + "/mo";

  renderSubscriptions(view.subscriptions);
  renderCatalog(view.subscriptions);
}

function renderSubscriptions(subs) {
  const wrap = document.getElementById("subscriptions");
  const empty = document.getElementById("subs-empty");
  wrap.innerHTML = "";

  if (!subs.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  subs.forEach((s) => {
    const svc = s.service || {};
    const card = document.createElement("div");
    card.className = "card";

    let statusMeta = "";
    if (s.status === "trial") {
      const left = s.trial_days_left;
      statusMeta = `
        <div class="meta-line"><span class="countdown">${left} day${left === 1 ? "" : "s"} left</span> in free trial</div>
        <div class="meta-line">Trial ends <strong>${fmtDate(s.trial_ends_at)}</strong></div>
        <div class="meta-line">Then <strong>${money(svc.monthly_price)}/mo</strong> unless cancelled</div>`;
    } else if (s.status === "active") {
      statusMeta = `
        <div class="meta-line">Paid subscription · <strong>${money(svc.monthly_price)}/mo</strong></div>
        <div class="meta-line">Next bill <strong>${fmtDate(s.next_bill_date)}</strong></div>`;
    } else {
      statusMeta = `<div class="meta-line">Cancelled ${fmtDate(s.cancelled_at)} · never charged if cancelled in trial</div>`;
    }

    const cancelBtn = s.status === "cancelled"
      ? ""
      : `<button class="btn btn-danger" data-cancel="${s.id}">${s.status === "trial" ? "Cancel trial" : "Cancel"}</button>`;

    card.innerHTML = `
      <div class="card-head">
        <div class="card-emoji">${svc.emoji || "◈"}</div>
        <div>
          <div class="card-title">${svc.name || s.service_id}</div>
          <div class="card-cat">${svc.category || ""}</div>
        </div>
      </div>
      ${statusMeta}
      <div class="card-foot">
        <span class="badge badge-${s.status}">${s.status}</span>
        ${cancelBtn}
      </div>`;
    wrap.appendChild(card);
  });
}

function renderCatalog(subs) {
  const wrap = document.getElementById("catalog");
  wrap.innerHTML = "";
  const activeIds = new Set(
    subs.filter((s) => s.status === "trial" || s.status === "active").map((s) => s.service_id)
  );

  catalog.forEach((svc) => {
    const subscribed = activeIds.has(svc.id);
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="card-head">
        <div class="card-emoji">${svc.emoji}</div>
        <div>
          <div class="card-title">${svc.name}</div>
          <div class="card-cat">${svc.category}</div>
        </div>
      </div>
      <div class="card-desc">${svc.description}</div>
      <div class="card-price">Free for <strong>${svc.trial_days} days</strong>, then <strong>${money(svc.monthly_price)}/mo</strong></div>
      <div class="card-foot">
        <span></span>
        <button class="btn btn-primary" data-start="${svc.id}" ${subscribed ? "disabled" : ""}>
          ${subscribed ? "Subscribed" : "Start free trial"}
        </button>
      </div>`;
    wrap.appendChild(card);
  });
}

// --------------------------------------------------------------------------- //
// Actions                                                                     //
// --------------------------------------------------------------------------- //
async function startTrial(serviceId) {
  try {
    const res = await api.post("/api/subscriptions", { service_id: serviceId });
    const svc = catalog.find((s) => s.id === serviceId);
    toast("Free trial started", `${svc ? svc.name : serviceId} — free for ${svc ? svc.trial_days : ""} days.`, "success");
    render(res.view);
  } catch (err) {
    toast("Couldn't start trial", err.message, "error");
  }
}

async function cancelSub(subId) {
  try {
    const res = await api.post(`/api/subscriptions/${subId}/cancel`);
    toast("Subscription cancelled", "You won't be charged going forward.", "success");
    render(res.view);
  } catch (err) {
    toast("Couldn't cancel", err.message, "error");
  }
}

async function advance(days) {
  try {
    const view = await api.post("/api/demo/advance", { days });
    announceConversions(view.just_converted);
    render(view);
  } catch (err) {
    toast("Couldn't advance clock", err.message, "error");
  }
}

async function resetDemo() {
  try {
    const view = await api.post("/api/demo/reset");
    render(view);
    toast("Demo reset", "All subscriptions cleared and the clock is back to today.", "success");
  } catch (err) {
    toast("Couldn't reset", err.message, "error");
  }
}

// --------------------------------------------------------------------------- //
// Wiring                                                                      //
// --------------------------------------------------------------------------- //
document.addEventListener("click", (e) => {
  const start = e.target.closest("[data-start]");
  if (start) return startTrial(start.dataset.start);
  const cancel = e.target.closest("[data-cancel]");
  if (cancel) return cancelSub(cancel.dataset.cancel);
  const adv = e.target.closest("[data-advance]");
  if (adv) return advance(Number(adv.dataset.advance));
  if (e.target.closest("#reset-btn")) return resetDemo();
});

(async function init() {
  try {
    await loadCatalog();
    await refresh();
  } catch (err) {
    toast("Failed to load", err.message, "error");
  }
})();
