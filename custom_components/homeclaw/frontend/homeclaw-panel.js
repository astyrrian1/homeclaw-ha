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
    this._intentTemplate = "episode_completion";
    this._intentPreview = null;
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

  async _submitFeedback(targetId, kind) {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this.render();
    try {
      await this._hass.callService("homeclaw", "submit_feedback", {
        target_id: targetId,
        kind,
      });
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
  }

  async _reviewQualification(evidenceId, label, eligibility) {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this.render();
    try {
      const payload = {
        evidence_id: evidenceId,
        eligibility,
        reason: eligibility === "excluded" ? "Resident excluded this opportunity." : "Resident semantic review.",
      };
      if (label) payload.label = label;
      await this._hass.callService("homeclaw", "review_qualification_evidence", payload);
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
  }

  async _approveQualificationCampaign(campaignId) {
    if (!campaignId || this._loading) return;
    this._loading = true;
    this.render();
    try {
      await this._hass.callService("homeclaw", "approve_qualification_campaign", {
        campaign_id: campaignId,
        owner_confirmation: true,
      });
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
  }

  async _previewIntent(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const templateId = String(values.get("template_id"));
    const fields = intentFields(templateId, values);
    this._loading = true;
    this._error = null;
    this.render();
    try {
      this._intentPreview = await this._hass.callWS({
        type: "homeclaw/preview_intent",
        template_id: templateId,
        fields,
        delivery_target: String(values.get("delivery_target")),
        cooldown_seconds: Number(values.get("cooldown_seconds") || 0),
        expires_at: new Date(String(values.get("expires_at"))).toISOString(),
      });
    } catch (error) {
      this._error = String(error?.message || error);
    } finally {
      this._loading = false;
      this.render();
    }
  }

  async _confirmIntent() {
    if (!this._intentPreview || this._loading) return;
    this._loading = true;
    this.render();
    try {
      await this._hass.callService("homeclaw", "create_standing_intent", {
        template_id: this._intentPreview.template_id,
        fields: this._intentPreview.normalized_fields,
        delivery_target: this._intentPreview.delivery_target,
        cooldown_seconds: this._intentPreview.cooldown_seconds,
        expires_at: this._intentPreview.expires_at,
        preview_sha256: this._intentPreview.preview_sha256,
      });
      this._intentPreview = null;
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
  }

  async _cancelIntent(intentId) {
    if (!intentId || this._loading) return;
    this._loading = true;
    this.render();
    try {
      await this._hass.callService("homeclaw", "cancel_standing_intent", {
        intent_id: intentId,
      });
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
  }

  async _reviewMemory(candidateId, operation) {
    if (!candidateId || this._loading) return;
    this._loading = true;
    this.render();
    try {
      await this._hass.callService("homeclaw", `${operation}_memory`, {
        candidate_id: candidateId,
        owner_confirmation: true,
        reason: "Reviewed in the Homeclaw HA panel",
      });
      this._loading = false;
      await this._load();
    } catch (error) {
      this._loading = false;
      this._error = String(error?.message || error);
      this.render();
    }
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
        <footer>Shared household view · review actions use your mapped HA identity · refreshes every 10 seconds</footer>
      </main>`;
    this.shadowRoot.querySelectorAll("button[data-view]").forEach((button) => {
      button.addEventListener("click", () => this._select(button.dataset.view));
    });
    this.shadowRoot.querySelectorAll("button[data-feedback]").forEach((button) => {
      button.addEventListener("click", () =>
        this._submitFeedback(button.dataset.targetId, button.dataset.feedback),
      );
    });
    const intentForm = this.shadowRoot.querySelector("#intent-form");
    if (intentForm) intentForm.addEventListener("submit", (event) => this._previewIntent(event));
    const template = this.shadowRoot.querySelector("#intent-template");
    if (template) template.addEventListener("change", (event) => {
      this._intentTemplate = event.target.value;
      this._intentPreview = null;
      this.render();
    });
    const confirmIntent = this.shadowRoot.querySelector("#confirm-intent");
    if (confirmIntent) confirmIntent.addEventListener("click", () => this._confirmIntent());
    this.shadowRoot.querySelectorAll("button[data-cancel-intent]").forEach((button) => {
      button.addEventListener("click", () => this._cancelIntent(button.dataset.cancelIntent));
    });
    this.shadowRoot.querySelectorAll("button[data-memory-review]").forEach((button) => {
      button.addEventListener("click", () =>
        this._reviewMemory(button.dataset.candidateId, button.dataset.memoryReview),
      );
    });
    this.shadowRoot.querySelectorAll("button[data-qualification-review]").forEach((button) => {
      button.addEventListener("click", () => this._reviewQualification(
        button.dataset.evidenceId,
        button.dataset.qualificationReview || null,
        button.dataset.eligibility,
      ));
    });
    this.shadowRoot.querySelectorAll("button[data-campaign-approve]").forEach((button) => {
      button.addEventListener("click", () =>
        this._approveQualificationCampaign(button.dataset.campaignApprove),
      );
    });
  }

  _renderView(data) {
    const views = {
      now: () => this._now(data),
      journal: () => listSection("House Journal", data.journal_entries, journalItem),
      evidence: () => listSection("Recent evidence", data.timeline, genericItem),
      insights: () => `${listSection("Insights and proposals", data.events, genericItem)}${listSection("Numeric forecasts", data.forecasts, genericItem)}`,
      cognition: () => `${listSection("Cognition Packs", data.cognition_programs, programItem)}${listSection("Release certificates", data.release_certifications, certificationItem)}${listSection("Recent runs", data.cognition_runs, cognitionRunItem)}`,
      memory: () => `${listSection("Approved household memory", data.memory_claims, memoryItem)}${listSection("Candidate provenance seeds", data.memory_seeds, genericItem)}${listSection("Consolidation reviews", data.memory_reviews, genericItem)}`,
      intentions: () => this._intentions(data),
      review: () => `${listSection("Independent qualification opportunities", data.qualification_review_queue, qualificationReviewItem)}${listSection("Legacy cognition samples", (data.cognition_runs || []).filter((item) => item.qualification_eligible && !item.review_kind), cognitionRunItem)}${memoryReviewSection(data.memory_candidates)}${listSection("Procedural proposals", data.procedural_proposals, genericItem)}`,
      settings: () => listSection("Resident profiles", data.resident_profiles, genericItem),
      operations: () => `${this._operations(data)}${listSection("Automatic cognition activation", data.cognition_auto_activation?.items || [], activationItem)}${listSection("Field quality monitoring", data.qualification_campaigns, qualificationItem)}${listSection("Production checks", data.qualification_checks, qualificationItem)}${listSection("Controlled experiments", data.experiments, genericItem)}`,
    };
    return (views[this._view] || views.now)();
  }

  _now(data) {
    const signals = data.world?.signals || [];
    const sourceHealth = Array.isArray(data.world?.source_health)
      ? data.world.source_health
      : Object.entries(data.world?.source_health || {}).map(([source, value]) => ({ source, value }));
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
      ${listSection("Source health", sourceHealth, genericItem)}`;
  }

  _operations(data) {
    const activation = data.activation_funnel || {};
    const totals = activation.by_status || {};
    return `
      <section class="metrics">
        ${metric("Observations", data.observation_count ?? 0)}
        ${metric("Episodes", data.episode_count ?? 0)}
        ${metric("Shadow precision", data.shadow_precision == null ? "—" : data.shadow_precision)}
        ${metric("Catalog mapped", data.catalog_coverage?.mapped ?? "—")}
        ${metric("Catalog unknown", data.catalog_coverage?.unmapped ?? "—")}
        ${metric("Last decision", formatTime(data.last_decision))}
        ${metric("Projected audit", totals.projected_audit ?? 0)}
        ${metric("Context not ready", totals.context_not_ready ?? 0)}
        ${metric("Citation rejected", totals.citation_rejected ?? 0)}
      </section>
      ${listSection("Situation threads", data.journal_clusters, genericItem)}`;
  }

  _intentions(data) {
    const expiry = new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 16);
    return `
      <section><h2>Create a notification-only intention</h2>
        <form id="intent-form" class="intent-form">
          <label>Template<select id="intent-template" name="template_id">${intentTemplateOptions(this._intentTemplate)}</select></label>
          ${intentTemplateFields(this._intentTemplate)}
          <label>Delivery target<input name="delivery_target" value="mobile" maxlength="300" required></label>
          <label>Cooldown seconds<input name="cooldown_seconds" type="number" min="0" max="604800" value="0" required></label>
          <label>Expires<input name="expires_at" type="datetime-local" value="${expiry}" required></label>
          <button type="submit" ${this._loading ? "disabled" : ""}>Preview</button>
        </form>
        ${this._intentPreview ? `<article class="confirmation-card"><strong>Resident confirmation required</strong><p>${escapeHtml(this._intentPreview.behavior_summary)}</p><small>Notification only · expires ${formatTime(this._intentPreview.expires_at)} · hash ${escapeHtml(this._intentPreview.preview_sha256.slice(0, 12))}…</small><button id="confirm-intent">Confirm intention</button></article>` : ""}
      </section>
      ${intentListSection(data.standing_intents)}
      ${listSection("Scheduled reminders", data.scheduled_jobs, genericItem)}`;
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
  const status = String(item.status || "audit").toUpperCase();
  return row(`[${status}] ${item.title || item.kind || item.level || "Journal note"}`, item.body || item.conclusion || item.summary || "", `${item.room || "house"} · ${formatTime(item.created_at || item.occurred_at)}`);
}

function programItem(item) {
  const readiness = item.readiness?.status || "not evaluated";
  const reasons = (item.readiness?.reason_codes || []).join(", ");
  const runtime = item.runtime_state || item.mode || "audit";
  const certification = item.certification_status || "uncertified";
  return row(item.program_id || item.id || "Pack", `${runtime} · ${item.sensitivity || "normal"} · certification ${certification} · readiness ${readiness}${reasons ? ` (${reasons})` : ""}`, item.version || item.last_evaluated_at);
}

function certificationItem(item) {
  const blockers = Array.isArray(item.blockers) && item.blockers.length
    ? ` · ${item.blockers.join(", ")}`
    : "";
  return row(item.program_id || "Pack certificate", `${item.status || "unknown"}${blockers}`, item.candidate_hash ? `candidate ${item.candidate_hash.slice(0, 12)} · ${formatTime(item.certified_at || item.created_at)}` : "no candidate");
}

function activationItem(item) {
  const hold = item.manual_hold ? " · manual hold" : "";
  const fallback = item.fallback_reason ? ` · ${item.fallback_reason}` : "";
  return row(item.program_id || "Pack", `${item.runtime_state || "audit"}${hold}${fallback}`, item.certification_status || "uncertified");
}

function cognitionRunItem(item) {
  const reviewed = item.review_kind
    ? `<small>Reviewed ${escapeHtml(item.review_kind)} · ${formatTime(item.reviewed_at)}</small>`
    : item.qualification_eligible
      ? `<div class="review-actions">
          <button data-target-id="${escapeHtml(item.id)}" data-feedback="useful">Useful</button>
          <button data-target-id="${escapeHtml(item.id)}" data-feedback="noisy">Noisy</button>
          <button data-target-id="${escapeHtml(item.id)}" data-feedback="wrong_evidence">Wrong evidence</button>
          <button data-target-id="${escapeHtml(item.id)}" data-feedback="wrong_timing">Wrong timing</button>
        </div>`
      : "<small>Historical audit · not qualification eligible</small>";
  return `<article class="row review-row"><div><strong>${escapeHtml(item.program_id || "Cognition run")}</strong><p>${escapeHtml(item.assessment || "")}</p><small>${escapeHtml(item.disposition || "unknown")} · confidence ${escapeHtml(item.confidence ?? "—")} · ${formatTime(item.completed_at)}</small></div>${reviewed}</article>`;
}

function qualificationItem(item) {
  const identity = item.release_identity || {};
  const detail = item.evidence || {};
  const evidence = item.eligible_units == null
    ? stringify(detail)
    : `${item.eligible_units} eligible · precision ${item.point_precision ?? "—"} · Wilson ${item.precision_wilson90 ?? "—"} · coverage ${item.coverage_complete ? "complete" : "incomplete"}`;
  const blockers = Array.isArray(item.gate_blockers) && item.gate_blockers.length
    ? ` · blocked: ${item.gate_blockers.join(", ")}`
    : "";
  const title = item.scope || item.check_id || "Qualification check";
  const body = `${item.status || "unknown"} · ${evidence}${blockers}`;
  const meta = `${item.candidate_hash ? `candidate ${item.candidate_hash.slice(0, 12)}` : item.category || "check"} · ${identity.model_name || identity.release || identity.schema || "current release"} · ${formatTime(item.completed_at || item.created_at)}`;
  const approval = item.status === "review_ready" && item.gate_ready
    ? `<button data-campaign-approve="${escapeHtml(item.id)}">Owner approve exact gate</button>`
    : "";
  return `<article class="row"><div><strong>${escapeHtml(title)}</strong><p>${escapeHtml(body)}</p>${approval}</div><small>${escapeHtml(meta)}</small></article>`;
}

function qualificationReviewItem(item) {
  const labels = [
    ["true_positive", "TP"], ["false_positive", "FP"],
    ["true_negative", "TN"], ["false_negative", "FN"],
    ["correct_abstain", "Correct abstain"], ["incorrect_abstain", "Incorrect abstain"],
  ];
  const buttons = labels.map(([label, title]) => `<button data-evidence-id="${escapeHtml(item.id)}" data-qualification-review="${label}" data-eligibility="eligible">${title}</button>`).join("");
  return `<article class="row review-row"><div><strong>${escapeHtml(item.opportunity_kind || "Qualification opportunity")}</strong><p>${escapeHtml(item.assessment || item.terminal_outcome || "")}</p><small>${escapeHtml(item.provenance || "unknown provenance")} · ${escapeHtml(item.context_status || "unknown context")} · ${formatTime(item.occurred_at)}</small></div><div class="review-actions">${buttons}<button data-evidence-id="${escapeHtml(item.id)}" data-qualification-review="" data-eligibility="excluded">Exclude</button></div></article>`;
}

function memoryItem(item) {
  return row(`${item.subject || "House"} · ${item.predicate || "memory"}`, stringify(item.value), `${item.status || "active"} · confidence ${item.confidence ?? "—"}`);
}

function memoryReviewSection(items) {
  const values = Array.isArray(items) ? items.filter((item) => item.status === "pending") : [];
  return `<section><h2>Pending memory review</h2><div class="list">${values.length ? values.map((item) => `<article class="row review-row"><div><strong>${escapeHtml(item.subject || item.candidate_kind || "Memory candidate")}</strong><p>${escapeHtml(stringify(item.proposed_value ?? item.value ?? item.summary))}</p><small>${escapeHtml((item.gate_reasons || []).join(" · ") || "Owner decision required")}</small></div><div class="review-actions"><button data-memory-review="approve" data-candidate-id="${escapeHtml(item.id)}">Approve</button><button data-memory-review="reject" data-candidate-id="${escapeHtml(item.id)}">Reject</button></div></article>`).join("") : '<p class="empty">No memory awaits review.</p>'}</div></section>`;
}

function intentListSection(items) {
  const values = Array.isArray(items) ? items : [];
  return `<section><h2>Standing intentions</h2><div class="list">${values.length ? values.map((item) => `<article class="row review-row"><div><strong>${escapeHtml(item.description || "Standing intention")}</strong><p>${escapeHtml(item.status || "active")} · ${escapeHtml(item.delivery_target || "")}</p><small>Expires ${formatTime(item.expires_at)}</small></div>${item.status === "active" ? `<button data-cancel-intent="${escapeHtml(item.id)}">Cancel</button>` : ""}</article>`).join("") : '<p class="empty">No standing intentions. Preview one above.</p>'}</div></section>`;
}

function intentTemplateOptions(selected) {
  const options = [
    ["episode_completion", "Episode completion"],
    ["source_recovery", "Source recovery"],
    ["semantic_state_transition", "State transition"],
    ["numeric_threshold", "Numeric threshold"],
  ];
  return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function intentTemplateFields(templateId) {
  if (templateId === "source_recovery") return `<label>Source<select name="source">${["home_assistant", "frigate", "omada", "doorbell", "halo"].map((value) => `<option>${value}</option>`).join("")}</select></label>`;
  if (templateId === "semantic_state_transition") return `<label>Semantic role<select name="semantic_role">${["alarm_state", "door", "garage_door", "house_mode", "occupancy", "presence"].map((value) => `<option>${value}</option>`).join("")}</select></label><label>From<input name="from" required></label><label>To<input name="to" required></label><label>Area (optional)<input name="area"></label>`;
  if (templateId === "numeric_threshold") return `<label>Semantic role<select name="semantic_role">${["carbon_dioxide", "humidity", "pm25", "power", "temperature", "volatile_organic_compounds", "water_flow"].map((value) => `<option>${value}</option>`).join("")}</select></label><label>Operator<select name="operator">${["gt", "gte", "lt", "lte"].map((value) => `<option>${value}</option>`).join("")}</select></label><label>Value<input name="value" type="number" step="any" required></label><label>Area (optional)<input name="area"></label>`;
  return `<label>Episode type<input name="episode_type" placeholder="appliance_cycle" required></label><label>Area (optional)<input name="area"></label>`;
}

function intentFields(templateId, values) {
  const optionalArea = String(values.get("area") || "").trim();
  if (templateId === "source_recovery") return { source: String(values.get("source")) };
  if (templateId === "semantic_state_transition") return { semantic_role: String(values.get("semantic_role")), from: String(values.get("from")), to: String(values.get("to")), ...(optionalArea ? { area: optionalArea } : {}) };
  if (templateId === "numeric_threshold") return { semantic_role: String(values.get("semantic_role")), operator: String(values.get("operator")), value: Number(values.get("value")), ...(optionalArea ? { area: optionalArea } : {}) };
  return { episode_type: String(values.get("episode_type")), ...(optionalArea ? { area: optionalArea } : {}) };
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
  .review-row { align-items:center; }
  .review-actions { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px; max-width:360px; }
  .review-actions button { padding:6px 9px; font-size:.76rem; }
  .intent-form { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; padding:15px; border:1px solid var(--divider-color); border-radius:14px; background:var(--card-background-color); }
  .intent-form label { display:grid; gap:5px; color:var(--secondary-text-color); font-size:.78rem; }
  .intent-form input, .intent-form select { box-sizing:border-box; width:100%; padding:8px; border:1px solid var(--divider-color); border-radius:7px; background:var(--primary-background-color); color:var(--primary-text-color); }
  .confirmation-card { margin-top:10px; padding:15px; border:2px solid var(--warning-color,#d89b26); border-radius:14px; background:var(--card-background-color); }
  .confirmation-card small { display:block; margin:8px 0; color:var(--secondary-text-color); }
  .empty { color:var(--secondary-text-color); }
  .error { background:#a33636; color:white; border-radius:10px; padding:10px 13px; }
  footer { color:var(--secondary-text-color); font-size:.75rem; margin:30px 0 12px; text-align:center; }
  @media (max-width:600px) { main { padding:16px; } .row { display:block; } .row small { display:block; margin-top:8px; white-space:normal; } }
`;

customElements.define("homeclaw-panel", HomeclawPanel);
