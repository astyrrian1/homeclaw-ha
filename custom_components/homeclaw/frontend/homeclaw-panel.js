const VIEWS = [
  ["now", "Now"],
  ["journal", "Journal"],
  ["evidence", "Evidence"],
  ["insights", "Insights"],
  ["cognition", "Cognition"],
  ["memory", "Memory"],
  ["intentions", "Intentions"],
  ["review", "Review"],
  ["settings", "Settings"],
  ["operations", "Operations"],
];

class HomeclawPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._view = "now";
    this._data = null;
    this._error = null;
    this._loading = false;
  }

  set hass(value) {
    this._hass = value;
    if (!this._data && !this._loading) this._load();
  }

  set narrow(value) {
    this._narrow = value;
  }

  set route(value) {
    this._route = value;
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    this.render();
    this._timer = window.setInterval(() => this._load(), 10000);
  }

  disconnectedCallback() {
    window.clearInterval(this._timer);
  }

  async _load() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      this._data = await this._hass.callWS({ type: "homeclaw/panel_data" });
      this._error = null;
    } catch (error) {
      this._error = String(error?.message || error);
    } finally {
      this._loading = false;
      this.render();
    }
  }

  _select(view) {
    this._view = view;
    this.render();
  }

  render() {
    if (!this.shadowRoot) return;
    const data = this._data || {};
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <main>
        <header>
          <div><p class="eyebrow">LOCAL HOUSE INTELLIGENCE</p><h1>Homeclaw</h1></div>
          <div class="health ${data.ready ? "ok" : "bad"}">${data.ready ? "Ready" : "Unavailable"}</div>
        </header>
        <nav>${VIEWS.map(([id, label]) => `<button data-view="${id}" class="${id === this._view ? "active" : ""}">${label}</button>`).join("")}</nav>
        ${this._error ? `<div class="error">${escapeHtml(this._error)}</div>` : ""}
        ${this._renderView(data)}
        <footer>Read-only shared household view · refreshes every 10 seconds</footer>
      </main>`;
    this.shadowRoot.querySelectorAll("button[data-view]").forEach((button) => {
      button.addEventListener("click", () => this._select(button.dataset.view));
    });
  }

  _renderView(data) {
    const views = {
      now: () => this._now(data),
      journal: () => listSection("House Journal", data.journal_entries, journalItem),
      evidence: () => listSection("Recent evidence", data.timeline, genericItem),
      insights: () => `${listSection("Insights and proposals", data.events, genericItem)}${listSection("Numeric forecasts", data.forecasts, genericItem)}`,
      cognition: () => `${listSection("Cognition Packs", data.cognition_programs, programItem)}${listSection("Recent runs", data.cognition_runs, genericItem)}`,
      memory: () => listSection("Approved household memory", data.memory_claims, memoryItem),
      intentions: () => `${listSection("Standing intentions", data.standing_intents, genericItem)}${listSection("Scheduled reminders", data.scheduled_jobs, genericItem)}`,
      review: () => `${listSection("Pending memory review", data.memory_candidates, genericItem)}${listSection("Procedural proposals", data.procedural_proposals, genericItem)}`,
      settings: () => listSection("Resident profiles", data.resident_profiles, genericItem),
      operations: () => `${this._operations(data)}${listSection("Controlled experiments", data.experiments, genericItem)}`,
    };
    return (views[this._view] || views.now)();
  }

  _now(data) {
    const signals = data.world?.signals || [];
    const sourceHealth = data.world?.source_health || {};
    return `
      <section class="metrics">
        ${metric("Authority", data.authority_mode || "unknown")}
        ${metric("Inference", data.inference_available ? "available" : "paused")}
        ${metric("Open insights", data.open_insights ?? 0)}
        ${metric("Pending proposals", data.pending_proposals ?? 0)}
        ${metric("Active episode", data.active_episode || "none")}
        ${metric("Decision latency", data.decision_latency == null ? "—" : `${data.decision_latency} s`)}
      </section>
      ${listSection("Current conditions", signals, signalItem)}
      ${listSection("Source health", Object.entries(sourceHealth).map(([source, value]) => ({ source, value })), genericItem)}`;
  }

  _operations(data) {
    return `
      <section class="metrics">
        ${metric("Observations", data.observation_count ?? 0)}
        ${metric("Episodes", data.episode_count ?? 0)}
        ${metric("Shadow precision", data.shadow_precision == null ? "—" : data.shadow_precision)}
        ${metric("Catalog mapped", data.catalog_coverage?.mapped ?? "—")}
        ${metric("Catalog unknown", data.catalog_coverage?.unmapped ?? "—")}
        ${metric("Last decision", formatTime(data.last_decision))}
      </section>
      ${listSection("Situation threads", data.journal_clusters, genericItem)}`;
  }
}

function metric(label, value) {
  return `<article class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function listSection(title, items, formatter) {
  const values = Array.isArray(items) ? items : [];
  return `<section><h2>${escapeHtml(title)}</h2><div class="list">${values.length ? values.map(formatter).join("") : '<p class="empty">Nothing to show.</p>'}</div></section>`;
}

function signalItem(item) {
  const title = item.subject || item.entity_id || item.signal || "Signal";
  const value = item.value ?? item.state ?? "unknown";
  return row(title, `${value}${item.unit ? ` ${item.unit}` : ""}`, item.quality || item.source);
}

function journalItem(item) {
  return row(item.title || item.kind || item.level || "Journal note", item.body || item.conclusion || item.summary || "", `${item.room || "house"} · ${formatTime(item.created_at || item.occurred_at)}`);
}

function programItem(item) {
  return row(item.program_id || item.id || "Pack", `${item.mode || "audit"} · ${item.sensitivity || "normal"}`, item.version || item.last_evaluated_at);
}

function memoryItem(item) {
  return row(`${item.subject || "House"} · ${item.predicate || "memory"}`, stringify(item.value), `${item.status || "active"} · confidence ${item.confidence ?? "—"}`);
}

function genericItem(item) {
  const title = item.title || item.assessment || item.description || item.record_type || item.kind || item.type || item.source || item.id || "Record";
  const body = item.body || item.summary || item.conclusion || item.expected_outcome || item.value || item.status || "";
  const meta = item.occurred_at || item.created_at || item.started_at || item.updated_at || item.quality || "";
  return row(title, stringify(body), formatTime(meta));
}

function row(title, body, meta) {
  return `<article class="row"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(body)}</p></div><small>${escapeHtml(meta)}</small></article>`;
}

function stringify(value) {
  if (value == null) return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const STYLE = `
  :host { display:block; min-height:100%; background:var(--primary-background-color); color:var(--primary-text-color); }
  main { box-sizing:border-box; max-width:1280px; margin:0 auto; padding:24px; font-family:var(--paper-font-body1_-_font-family, system-ui, sans-serif); }
  header { display:flex; align-items:center; justify-content:space-between; gap:16px; }
  h1 { margin:0; font-size:2.2rem; letter-spacing:-.04em; }
  .eyebrow { margin:0 0 4px; color:var(--secondary-text-color); font-size:.72rem; letter-spacing:.13em; }
  .health { padding:7px 12px; border-radius:999px; font-weight:700; background:#5f6368; color:white; }
  .health.ok { background:#257a4d; } .health.bad { background:#a33636; }
  nav { display:flex; gap:6px; overflow:auto; margin:24px 0; padding-bottom:6px; }
  button { border:1px solid var(--divider-color); border-radius:999px; background:var(--card-background-color); color:var(--primary-text-color); padding:8px 13px; cursor:pointer; white-space:nowrap; }
  button.active { background:var(--primary-color); border-color:var(--primary-color); color:var(--text-primary-color, white); }
  section { margin:20px 0; } h2 { font-size:1.05rem; margin:0 0 10px; }
  .metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(165px,1fr)); gap:10px; }
  .metric, .row { border:1px solid var(--divider-color); background:var(--card-background-color); border-radius:14px; box-shadow:var(--ha-card-box-shadow, none); }
  .metric { padding:15px; } .metric span { display:block; color:var(--secondary-text-color); font-size:.78rem; margin-bottom:7px; } .metric strong { font-size:1.15rem; }
  .list { display:grid; gap:8px; }
  .row { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; padding:13px 15px; }
  .row p { margin:5px 0 0; color:var(--secondary-text-color); line-height:1.4; white-space:pre-wrap; }
  .row small { color:var(--secondary-text-color); white-space:nowrap; }
  .empty { color:var(--secondary-text-color); }
  .error { background:#a33636; color:white; border-radius:10px; padding:10px 13px; }
  footer { color:var(--secondary-text-color); font-size:.75rem; margin:30px 0 12px; text-align:center; }
  @media (max-width:600px) { main { padding:16px; } .row { display:block; } .row small { display:block; margin-top:8px; white-space:normal; } }
`;

customElements.define("homeclaw-panel", HomeclawPanel);
