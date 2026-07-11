/*
 * Algenta Decisions — Excel task pane (Build order 8).
 *
 * Talks to the CUSTOMER-hosted Decision API. Trust rules from the plan, enforced here:
 *   - Selection-only: only the user-selected range is read (never the whole workbook).
 *   - Show-exactly-what-will-be-sent: a preview lists the rows/cells before any call.
 *   - Compute in the customer's Azure; results write to NEW sheets after the preview.
 *   - Entra SSO via Office.auth.getAccessToken -> a token whose audience is the gateway API.
 *   - Approve is a separate, explicit click carrying the plan_hash + single-use nonce.
 */

/* global Office, Excel, document */

const state = { plan: null, runId: null, caseId: null };

Office.onReady(() => {
  document.getElementById("preview-btn").onclick = wrap(previewSelection);
  document.getElementById("run-btn").onclick = wrap(runAnalysis);
  document.getElementById("approve-btn").onclick = wrap(approve);
});

function wrap(fn) {
  return async () => {
    try {
      setStatus("");
      await fn();
    } catch (e) {
      setStatus("Error: " + (e && e.message ? e.message : e));
    }
  };
}

function setStatus(msg) {
  document.getElementById("status").textContent = msg;
}

function gateway() {
  const g = document.getElementById("gateway").value.trim().replace(/\/+$/, "");
  if (!g) throw new Error("Enter the gateway URL.");
  return g;
}

// Entra SSO: a bearer whose audience is the gateway API (validated by services/entra_auth.py).
async function authHeader() {
  const token = await Office.auth.getAccessToken({ allowSignInPrompt: true });
  return { Authorization: "Bearer " + token, "Content-Type": "application/json" };
}

// Read ONLY the selected range and map it to Renewal Capacity Allocation accounts.
// Expected columns (header row): account_id, name, arr, renewal_date, health_score, segment.
async function readSelection() {
  return Excel.run(async (ctx) => {
    const range = ctx.workbook.getSelectedRange();
    range.load(["values", "address", "rowCount", "columnCount"]);
    await ctx.sync();
    const rows = range.values;
    if (!rows || rows.length < 2) throw new Error("Select a header row + at least one data row.");
    const header = rows[0].map((h) => String(h).trim().toLowerCase());
    const idx = (name) => header.indexOf(name);
    const accounts = rows.slice(1).filter((r) => r[idx("account_id")] !== "").map((r) => ({
      account_id: String(r[idx("account_id")]),
      name: String(r[idx("name")]),
      arr: Number(r[idx("arr")]) || 0,
      renewal_date: fmtDate(r[idx("renewal_date")]),
      health_score: idx("health_score") >= 0 ? Number(r[idx("health_score")]) : null,
      segment: idx("segment") >= 0 ? String(r[idx("segment")] || "standard") : "standard",
    }));
    return { accounts, address: range.address, cellCount: range.rowCount * range.columnCount };
  });
}

function fmtDate(v) {
  // Excel may hand back a serial number or a string; normalize to YYYY-MM-DD.
  if (typeof v === "number") {
    const d = new Date(Math.round((v - 25569) * 86400 * 1000));
    return d.toISOString().slice(0, 10);
  }
  return String(v).slice(0, 10);
}

async function previewSelection() {
  const sel = await readSelection();
  state.selection = sel;
  document.getElementById("preview").textContent =
    "Data to be sent (nothing else leaves the workbook):\n" +
    `  Range: ${sel.address}  ·  cells: ${sel.cellCount}\n` +
    `  Accounts: ${sel.accounts.length}\n` +
    "  Formula results are sent; formulas, hidden sheets and unrelated ranges are NOT.\n" +
    "  Processing: your organization's Azure gateway.  Raw workbook values retained: No.";
}

async function runAnalysis() {
  if (!state.selection) await previewSelection();
  const g = gateway();
  const headers = await authHeader();
  const packId = document.getElementById("pack").value;

  const created = await postJson(`${g}/v1/decision-cases`, headers, {
    pack_id: packId,
    title: document.getElementById("title").value || "Excel decision",
    pack_input: {
      accounts: state.selection.accounts,
      capacity: { total_hours: 400 },
      constraints: { strategic_min_hours: 4, allocation_step_hours: 1 },
    },
  });
  state.caseId = created.case_id;

  const accepted = await postJson(`${g}/v1/decision-cases/${state.caseId}/analysis-runs`, headers, {});
  state.runId = accepted.run_id;

  // async 202 + poll
  let result = null;
  for (let i = 0; i < 30; i++) {
    const res = await getJson(`${g}/v1/analysis-runs/${state.runId}/result`, headers);
    if (res.status === "completed") { result = res.result; break; }
    if (res.status === "failed") throw new Error("Analysis failed: " + (res.error || "unknown"));
    await sleep(1000);
  }
  if (!result) throw new Error("Analysis timed out.");

  await writeResultSheets(result);

  if (result.feasible) {
    state.plan = await postJson(`${g}/v1/analysis-runs/${state.runId}/action-plans`, headers, {});
    document.getElementById("approve-btn").disabled = false;
    setStatus("Recommendation ready. Review the new sheets, then Approve.");
  } else {
    document.getElementById("approve-btn").disabled = true;
    setStatus("No feasible solution — see the Algenta Decision sheet for the binding constraint.");
  }
}

async function approve() {
  if (!state.plan) throw new Error("Run an analysis first.");
  const g = gateway();
  const headers = await authHeader();
  const approval = await postJson(`${g}/v1/decision-plans/${state.plan.plan_id}/approve`, headers, {
    plan_hash: state.plan.plan_hash,
    nonce: state.plan.nonce,
  });
  setStatus(`Approved by ${approval.approver_principal || "you"}. Use Execute (owner) to publish the plan.`);
  document.getElementById("approve-btn").disabled = true;
}

// Write recommendation + sensitivity + evidence to NEW sheets (never overwrite existing cells).
async function writeResultSheets(result) {
  await Excel.run(async (ctx) => {
    const rid = result.recommended_scenario_id;
    const scn = (result.scenarios || []).find((s) => s.id === rid);

    const decision = uniqueSheet(ctx, "Algenta Decision");
    setRows(decision, [
      ["Model version", result.model_version],
      ["Feasible", String(result.feasible)],
      ["Recommended scenario", rid || "(none)"],
      ["Expected retained ARR", scn ? scn.expected_retained_arr : ""],
      ["Uplift vs baseline", scn ? scn.uplift_arr : ""],
      ["Confidence", result.confidence],
      ["Disclaimer", result.disclaimer],
    ]);

    if (scn) {
      const alloc = uniqueSheet(ctx, "Allocation Plan");
      const rows = [["Account", "Hours", "Est. renewal prob", "Est. retained ARR", "Reason"]];
      (scn.allocations || []).forEach((a) =>
        rows.push([a.name, a.hours, a.estimated_renewal_probability, a.estimated_expected_retained_arr, a.reason]));
      setRows(alloc, rows);
    }

    const sens = uniqueSheet(ctx, "Sensitivity");
    setRows(sens, (result.sensitivity || []).map((s) => [s.parameter, s.description]));

    const ev = uniqueSheet(ctx, "Evidence");
    const prov = result.provenance || {};
    setRows(ev, [
      ["Observed facts", (prov.observed_facts || []).join("\n")],
      ["Assumptions", (prov.customer_assumptions || []).join("\n")],
      ["Estimated parameters", (prov.estimated_parameters || []).join("\n")],
      ["Simulated outcomes", (prov.simulated_outcomes || []).join("\n")],
    ]);
    await ctx.sync();
  });
}

function uniqueSheet(ctx, base) {
  // Never overwrite: append a numeric suffix if the sheet already exists.
  const sheets = ctx.workbook.worksheets;
  const name = base.slice(0, 28);
  const ws = sheets.add(name + " " + shortStamp());
  ws.activate();
  return ws;
}

function shortStamp() {
  // A monotonic-ish suffix so re-runs create fresh sheets (edit-and-rerun = new artifact).
  return String(Math.floor(performance.now())).slice(-5);
}

function setRows(ws, rows) {
  if (!rows.length) return;
  const cols = Math.max(...rows.map((r) => r.length));
  const norm = rows.map((r) => { const c = r.slice(); while (c.length < cols) c.push(""); return c; });
  const range = ws.getRangeByIndexes(0, 0, norm.length, cols);
  range.values = norm;
}

async function postJson(url, headers, body) {
  const r = await fetch(url, { method: "POST", headers, body: JSON.stringify(body) });
  return handle(r);
}
async function getJson(url, headers) {
  const r = await fetch(url, { method: "GET", headers });
  return handle(r);
}
async function handle(r) {
  const text = await r.text();
  const data = text ? JSON.parse(text) : {};
  if (!r.ok) {
    const detail = data.detail || data.error || {};
    throw new Error((detail.message || detail.code || r.status) + "");
  }
  return data;
}
function sleep(ms) { return new Promise((res) => setTimeout(res, ms)); }
