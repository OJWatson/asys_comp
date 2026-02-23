function fmtNum(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) {
    return "-";
  }
  return Number(v).toFixed(d);
}

function fmtPct(v, d = 1) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) {
    return "-";
  }
  return `${(Number(v) * 100).toFixed(d)}%`;
}

function toTitle(s) {
  return String(s || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function tableHtml(columns, rows, options = {}) {
  const className = options.className || "";
  const rowClassFn = options.rowClassFn || (() => "");

  const header = columns.map((c) => `<th>${c.label}</th>`).join("");
  const body = rows
    .map((r) => {
      const cells = columns
        .map((c) => {
          const value = typeof c.render === "function" ? c.render(r[c.key], r) : r[c.key];
          return `<td>${value ?? "-"}</td>`;
        })
        .join("");
      return `<tr class="${rowClassFn(r)}">${cells}</tr>`;
    })
    .join("");

  return `<div class="table-wrap"><table class="${className}"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
}

async function loadJson(path) {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status}`);
  }
  return res.json();
}

function activateNav() {
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  let currentFile = path.split("/").pop() || "index.html";

  if (path === "/projects/e5cr7") {
    currentFile = "projects-e5cr7";
  } else if (path === "/lab/e5cr7") {
    currentFile = "lab";
  } else if (path === "/lab") {
    currentFile = "lab";
  } else if (path === "/projects") {
    currentFile = "index";
  }

  const normalize = (s) => String(s || "").replace(/\.html$/i, "");

  document.querySelectorAll("nav a").forEach((a) => {
    const href = a.getAttribute("href") || "";
    const hrefFile = href.replace(/^\.\//, "").split("/").pop();
    if (normalize(hrefFile) === normalize(currentFile)) {
      a.classList.add("active");
    }
  });
}

function kvHtml(rows) {
  const body = rows
    .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`)
    .join("");
  return `<dl class="kv">${body}</dl>`;
}

function buttonLink(url, label, options = {}) {
  const cls = options.primary ? "button-link primary" : "button-link";
  const target = options.newTab ? ' target="_blank" rel="noreferrer"' : "";
  return `<a class="${cls}" href="${url}"${target}>${label}</a>`;
}

function projectStatusBadge(status) {
  const kind = status === "active" ? "good" : "warn";
  return `<span class="badge ${kind}">${toTitle(status)}</span>`;
}

async function renderCompendiumHome() {
  const [catalog, overview] = await Promise.all([
    loadJson("./data/compendium_catalog.json"),
    loadJson("./data/artifacts/overview.json"),
  ]);

  document.getElementById("shared-lab-summary").innerHTML = kvHtml([
    ["Gateway", catalog.shared_lab.display_name],
    ["Configured URL", `<a href="${catalog.shared_lab.entrypoint_url}">${catalog.shared_lab.entrypoint_url}</a>`],
    ["Note", catalog.shared_lab.entrypoint_note],
  ]);

  document.getElementById("compendium-e5cr7-snapshot").innerHTML = kvHtml([
    ["Records", overview.project.dataset_records],
    ["Known relevant", overview.project.known_relevant],
    ["Estimated prevalence", fmtPct(overview.project.estimated_prevalence)],
    ["Best model", overview.model_snapshot.best_model],
    ["Immediate additional screening", `+${overview.recommendation.immediate_additional_docs}`],
  ]);

  const projectGrid = document.getElementById("project-grid");
  projectGrid.innerHTML = "";

  (catalog.projects || []).forEach((p) => {
    const article = document.createElement("article");
    article.className = "card";
    article.innerHTML = `
      <h3>${p.name}</h3>
      <p>${projectStatusBadge(p.status)} <span class="muted">Stage: ${p.stage || "-"}</span></p>
      <p>${p.summary || ""}</p>
      <p class="muted"><strong>Focus:</strong> ${p.focus || "-"}</p>
      <div class="cta-row">
        ${buttonLink(p.deep_dive_path || "./index.html", "Deep Dive", { newTab: false, primary: true })}
        ${buttonLink(p.lab_path || "./lab.html", "LAB Endpoint", { newTab: false })}
      </div>
    `;
    projectGrid.appendChild(article);
  });
}

function findProject(catalog, slug) {
  return (catalog.projects || []).find((p) => p.slug === slug) || null;
}

async function renderProjectE5cr7() {
  const [catalog, overview] = await Promise.all([
    loadJson("./data/compendium_catalog.json"),
    loadJson("./data/artifacts/overview.json"),
  ]);

  const project = findProject(catalog, "e5cr7") || {};

  document.getElementById("e5cr7-cta-row").innerHTML = [
    buttonLink("./lab.html", "Shared LAB Gateway", { newTab: false, primary: true }),
    buttonLink(project.lab_path || "./lab-e5cr7.html", "Project LAB Endpoint", { newTab: false }),
    buttonLink(project.legacy_explainer_path || "./asreview-explainer.html", "Legacy Explainer", { newTab: false }),
  ].join("");

  document.getElementById("e5cr7-dataset").innerHTML = kvHtml([
    ["Project", project.name || "e5cr7"],
    ["Stage", project.stage || "Active"],
    ["Dataset records", overview.project.dataset_records],
    ["Known relevant", overview.project.known_relevant],
    ["Estimated prevalence", fmtPct(overview.project.estimated_prevalence)],
    ["Preferred strategy", overview.project.preferred_strategy],
  ]);

  document.getElementById("e5cr7-model").innerHTML = kvHtml([
    ["Best model", overview.model_snapshot.best_model],
    ["Average precision", fmtNum(overview.model_snapshot.average_precision, 3)],
    ["ROC AUC", fmtNum(overview.model_snapshot.roc_auc, 3)],
    ["Recall@20", fmtNum(overview.model_snapshot.recall_at_20, 3)],
    ["Recall@50", fmtNum(overview.model_snapshot.recall_at_50, 3)],
  ]);

  const rec = overview.recommendation;
  document.getElementById("e5cr7-recommendation").innerHTML = `
    <p><strong>Immediate target:</strong> screen +${rec.immediate_additional_docs} additional records.</p>
    <p><strong>Contingent target:</strong> extend to +${rec.contingent_additional_docs} if stricter residual-risk tolerance is required.</p>
    <p>Projected false negatives after immediate stage: <strong>${fmtNum(rec.expected_fn_after_immediate, 2)}</strong>.
    FN reduction versus baseline: <strong>${fmtNum(rec.expected_fn_reduction_after_immediate, 2)}</strong>.</p>
  `;
}

async function renderLabShared() {
  const catalog = await loadJson("./data/compendium_catalog.json");

  document.getElementById("shared-lab-gateway").innerHTML = `
    <p><strong>${catalog.shared_lab.display_name}</strong></p>
    <p class="muted">${catalog.shared_lab.entrypoint_note}</p>
    <div class="cta-row">
      ${buttonLink(catalog.shared_lab.entrypoint_url, "Open Shared LAB URL", { primary: true })}
      ${buttonLink("./projects-e5cr7.html", "Back to e5cr7 Deep Dive", { newTab: false })}
    </div>
  `;

  const list = document.getElementById("lab-project-list");
  list.innerHTML = "";

  (catalog.projects || [])
    .filter((p) => p.slug && p.slug !== "next-slot")
    .forEach((p) => {
      const item = document.createElement("article");
      item.className = "card";
      item.innerHTML = `
        <h3>${p.name}</h3>
        <p>${p.summary || ""}</p>
        <div class="cta-row">
          ${buttonLink(p.lab_path || "./lab.html", "Project LAB landing", { newTab: false, primary: true })}
          ${buttonLink(p.legacy_lab_url || catalog.shared_lab.entrypoint_url, "Legacy/current URL")}
        </div>
      `;
      list.appendChild(item);
    });
}

async function renderLabE5cr7() {
  const catalog = await loadJson("./data/compendium_catalog.json");
  const project = findProject(catalog, "e5cr7") || {};

  document.getElementById("e5cr7-lab-links").innerHTML = `
    <p>Preferred route: shared gateway first, then project fallback if needed.</p>
    <div class="cta-row">
      ${buttonLink(catalog.shared_lab.entrypoint_url, "Open Shared Gateway", { primary: true })}
      ${buttonLink(project.legacy_lab_url || catalog.shared_lab.entrypoint_url, "Open Current/Legacy e5cr7 URL")}
      ${buttonLink("./lab.html", "All LAB Endpoints", { newTab: false })}
    </div>
  `;
}

async function renderExplainer() {
  const overview = await loadJson("./data/artifacts/overview.json");

  document.getElementById("dataset-snapshot").innerHTML = kvHtml([
    ["Total records", overview.project.dataset_records],
    ["Known relevant", overview.project.known_relevant],
    ["Estimated prevalence", fmtPct(overview.project.estimated_prevalence)],
    ["Preferred strategy", overview.project.preferred_strategy],
  ]);

  document.getElementById("model-snapshot").innerHTML = kvHtml([
    ["Best model", overview.model_snapshot.best_model],
    ["Average precision", fmtNum(overview.model_snapshot.average_precision, 3)],
    ["ROC AUC", fmtNum(overview.model_snapshot.roc_auc, 3)],
    ["Recall@20", fmtNum(overview.model_snapshot.recall_at_20, 3)],
    ["Recall@50", fmtNum(overview.model_snapshot.recall_at_50, 3)],
  ]);

  document.getElementById("risk-baselines").innerHTML = tableHtml(
    [
      { key: "threshold_policy", label: "Policy", render: (v) => toTitle(v) },
      { key: "target_recall", label: "Target Recall", render: (v) => fmtPct(v, 1) },
      { key: "docs_screened_mean", label: "Docs Screened" },
      { key: "work_saved_docs", label: "Work Saved" },
      { key: "expected_fn", label: "Expected FN" },
      { key: "expected_fp", label: "Expected FP" },
      { key: "estimated_recall", label: "Estimated Recall", render: (v) => fmtPct(v, 1) },
    ],
    overview.risk_baselines
  );

  const rec = overview.recommendation;
  document.getElementById("recommendation").innerHTML = `
    <p><strong>Immediate target:</strong> screen +${rec.immediate_additional_docs} additional records.</p>
    <p><strong>Contingent target:</strong> extend to +${rec.contingent_additional_docs} if residual risk tolerance is stricter.</p>
    <p>Projected FN after immediate stage: <strong>${fmtNum(rec.expected_fn_after_immediate, 2)}</strong>
       (reduction of <strong>${fmtNum(rec.expected_fn_reduction_after_immediate, 2)}</strong>).</p>
  `;
}

async function renderMethodsResults() {
  const data = await loadJson("./data/artifacts/methods_results.json");

  document.getElementById("methods-list").innerHTML = data.methods
    .map((m) => `<li>${m}</li>`)
    .join("");

  const leaderboardRows = data.model_leaderboard.map((r) => ({
    model: r.model,
    average_precision: fmtNum(r["average_precision"], 3),
    wss95: fmtNum(r["wss@95"], 3),
    recall20: fmtNum(r["recall@20"], 3),
    recall50: fmtNum(r["recall@50"], 3),
    precision10: fmtNum(r["precision@10"], 3),
  }));

  document.getElementById("leaderboard-table").innerHTML = tableHtml(
    [
      { key: "model", label: "Model" },
      { key: "average_precision", label: "Average Precision" },
      { key: "wss95", label: "WSS@95" },
      { key: "recall20", label: "Recall@20" },
      { key: "recall50", label: "Recall@50" },
      { key: "precision10", label: "Precision@10" },
    ],
    leaderboardRows
  );

  document.getElementById("comparison-table").innerHTML = tableHtml(
    [
      { key: "metric", label: "Metric" },
      { key: "baseline", label: "Baseline", render: (v) => fmtNum(v, 4) },
      { key: "improved_best", label: "Improved", render: (v) => fmtNum(v, 4) },
      {
        key: "delta",
        label: "Delta",
        render: (v) => {
          const n = Number(v);
          const cls = n >= 0 ? "good" : "warn";
          return `<span class="badge ${cls}">${n >= 0 ? "+" : ""}${fmtNum(n, 4)}</span>`;
        },
      },
    ],
    data.baseline_vs_improved
  );

  const nestedRows = data.nested_cv_summary || [];
  const nested = Object.fromEntries(nestedRows.map((r) => [r.metric, r]));
  document.getElementById("nested-cv").innerHTML = kvHtml([
    ["AP mean ± std", `${fmtNum(nested.ap?.mean, 3)} ± ${fmtNum(nested.ap?.std, 3)}`],
    ["ROC AUC mean ± std", `${fmtNum(nested.roc_auc?.mean, 3)} ± ${fmtNum(nested.roc_auc?.std, 3)}`],
    [
      "Threshold@Recall 0.90 mean ± std",
      `${fmtNum(nested["threshold_recall_0.90"]?.mean, 3)} ± ${fmtNum(nested["threshold_recall_0.90"]?.std, 3)}`,
    ],
    [
      "Threshold@Recall 0.95 mean ± std",
      `${fmtNum(nested["threshold_recall_0.95"]?.mean, 3)} ± ${fmtNum(nested["threshold_recall_0.95"]?.std, 3)}`,
    ],
  ]);
}

async function renderWhyMoreReview() {
  const data = await loadJson("./data/artifacts/fn_fp_risk.json");
  const framing = data.framing || {};
  const story = data.story || {};

  document.getElementById("why-list").innerHTML = (framing.why_more_review || [])
    .map((x) => `<li>${x}</li>`)
    .join("");
  document.getElementById("risk-source-note").textContent = framing.source_note || "";

  const container = document.getElementById("fnfp-policies");
  container.innerHTML = "";

  (story.policies || []).forEach((policy) => {
    const block = document.createElement("article");
    block.className = "card";

    const heading = document.createElement("h3");
    heading.textContent = `${toTitle(policy.threshold_policy)} (target ${fmtPct(policy.target_recall)})`;

    const table = tableHtml(
      [
        { key: "additional_docs_requested", label: "Additional" },
        { key: "screened_docs_total", label: "Total Screened" },
        { key: "fn", label: "Expected FN", render: (v) => fmtNum(v, 2) },
        { key: "fp", label: "Expected FP", render: (v) => fmtNum(v, 2) },
        { key: "recall", label: "Recall", render: (v) => fmtPct(v, 1) },
        { key: "precision", label: "Precision", render: (v) => fmtPct(v, 1) },
        { key: "work_saved_fraction", label: "Work Saved", render: (v) => fmtPct(v, 1) },
      ],
      policy.rows || [],
      {
        rowClassFn: (r) => (Number(r.additional_docs_requested) === 0 ? "baseline" : ""),
      }
    );

    block.appendChild(heading);
    block.innerHTML += table;
    container.appendChild(block);
  });
}

function uniqueValues(rows, key) {
  return Array.from(new Set(rows.map((r) => r[key])));
}

function optionHtml(values, labelFn) {
  return values
    .map((v) => `<option value="${v}">${labelFn ? labelFn(v) : v}</option>`)
    .join("");
}

function renderPlannerResult(row) {
  if (!row) {
    return "<p>No scenario selected.</p>";
  }

  const left = kvHtml([
    ["Additional requested", row.additional_docs_requested],
    ["Additional effective", row.additional_docs_effective],
    ["Total screened", row.screened_docs_total],
    ["Work saved", `${row.work_saved_docs} (${fmtPct(row.work_saved_fraction, 1)})`],
    ["Cap reached", row.cap_reached ? "Yes" : "No"],
  ]);

  const right = kvHtml([
    ["Expected TP", fmtNum(row.tp, 2)],
    ["Expected FN", fmtNum(row.fn, 2)],
    ["Expected FP", fmtNum(row.fp, 2)],
    ["Recall", fmtPct(row.recall, 1)],
    ["Precision", fmtPct(row.precision, 1)],
  ]);

  return `<article class="card">${left}</article><article class="card">${right}</article>`;
}

async function renderHowManyMore() {
  const planner = await loadJson("./data/artifacts/simulation_planner.json");
  const rows = planner.rows || [];

  const policyEl = document.getElementById("planner-policy");
  const bandEl = document.getElementById("planner-band");
  const addEl = document.getElementById("planner-additional");

  const policies = uniqueValues(rows, "threshold_policy");
  const bands = uniqueValues(rows, "prevalence_band");
  const adds = uniqueValues(rows, "additional_docs_requested").sort((a, b) => a - b);

  policyEl.innerHTML = optionHtml(policies, toTitle);
  bandEl.innerHTML = optionHtml(bands, toTitle);
  addEl.innerHTML = optionHtml(adds, (v) => `+${v}`);

  function subset() {
    return rows
      .filter((r) => r.threshold_policy === policyEl.value)
      .filter((r) => r.prevalence_band === bandEl.value)
      .sort((a, b) => Number(a.additional_docs_requested) - Number(b.additional_docs_requested));
  }

  function rerender() {
    const filtered = subset();

    const values = uniqueValues(filtered, "additional_docs_requested").sort((a, b) => a - b);
    addEl.innerHTML = optionHtml(values, (v) => `+${v}`);

    const pick = filtered.find((r) => Number(r.additional_docs_requested) === Number(addEl.value)) || filtered[0];

    document.getElementById("planner-result").innerHTML = renderPlannerResult(pick);
    document.getElementById("planner-table").innerHTML = tableHtml(
      [
        { key: "additional_docs_requested", label: "Additional" },
        { key: "additional_docs_effective", label: "Effective" },
        { key: "fn", label: "FN", render: (v) => fmtNum(v, 2) },
        { key: "fp", label: "FP", render: (v) => fmtNum(v, 2) },
        { key: "recall", label: "Recall", render: (v) => fmtPct(v, 1) },
        { key: "precision", label: "Precision", render: (v) => fmtPct(v, 1) },
        { key: "work_saved_fraction", label: "Work Saved", render: (v) => fmtPct(v, 1) },
      ],
      filtered
    );
  }

  policyEl.addEventListener("change", rerender);
  bandEl.addEventListener("change", rerender);
  addEl.addEventListener("change", rerender);

  const rec = planner.recommended_targets || {};
  document.getElementById("planner-recommendation").innerHTML = `
    <p><strong>Immediate stage:</strong> +${rec.immediate_additional_docs || 50} records.</p>
    <p><strong>If stricter assurance is required:</strong> continue to +${rec.contingent_additional_docs || 100}.</p>
    <p class="muted">These are planning estimates from current simulation outputs; rerun after new labels are synced.</p>
  `;

  rerender();
}

async function main() {
  activateNav();
  const page = document.body.dataset.page;

  if (page === "compendium-home") {
    await renderCompendiumHome();
  } else if (page === "project-e5cr7") {
    await renderProjectE5cr7();
  } else if (page === "lab-shared") {
    await renderLabShared();
  } else if (page === "lab-e5cr7") {
    await renderLabE5cr7();
  } else if (page === "asreview-explainer") {
    await renderExplainer();
  } else if (page === "methods-results") {
    await renderMethodsResults();
  } else if (page === "why-more-review") {
    await renderWhyMoreReview();
  } else if (page === "how-many-more") {
    await renderHowManyMore();
  }
}

main().catch((err) => {
  console.error(err);
  const mainEl = document.querySelector("main");
  if (mainEl) {
    const div = document.createElement("div");
    div.className = "panel";
    div.innerHTML = `<h2>Data Load Error</h2><p>${String(err)}</p>`;
    mainEl.prepend(div);
  }
});
