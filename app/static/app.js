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

function normalizeRoute(rawPath) {
  const path = String(rawPath || "").replace(/\/+$/, "") || "/";

  if (path === "/" || path === "/index" || path.endsWith("/index.html")) {
    return "index";
  }
  if (path === "/projects" || path === "/projects/" || path.endsWith("/index.html#projects")) {
    return "index";
  }
  if (path === "/lab" || path.endsWith("/lab.html")) {
    return "lab";
  }
  if (path === "/projects/e5cr7" || path.endsWith("/projects-e5cr7.html")) {
    return "projects-e5cr7";
  }

  return path.split("/").pop().replace(/\.html$/i, "");
}

function activateNav() {
  const current = normalizeRoute(window.location.pathname);
  document.querySelectorAll(".global-nav a").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#")) {
      return;
    }
    const hrefPath = href.startsWith("./") ? href.slice(1) : href;
    const route = normalizeRoute(hrefPath);
    if (route === current) {
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

function findProject(catalog, slug) {
  return (catalog.projects || []).find((p) => p.slug === slug) || null;
}

async function renderCompendiumHome() {
  const [catalog, overview] = await Promise.all([
    loadJson("./data/compendium_catalog.json"),
    loadJson("./data/artifacts/overview.json"),
  ]);

  document.getElementById("shared-lab-summary").innerHTML = kvHtml([
    ["Gateway", catalog.shared_lab.display_name],
    ["Configured URL", `<a href="${catalog.shared_lab.entrypoint_url}">${catalog.shared_lab.entrypoint_url}</a>`],
    ["Why this matters", "One stable runtime URL across projects and deployment environments."],
  ]);

  document.getElementById("compendium-e5cr7-snapshot").innerHTML = kvHtml([
    ["Records", overview.project.dataset_records],
    ["Known relevant", overview.project.known_relevant],
    ["Estimated prevalence", fmtPct(overview.project.estimated_prevalence)],
    ["Best model", overview.model_snapshot.best_model],
    ["Immediate recommendation", `Screen +${overview.recommendation.immediate_additional_docs}`],
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
        ${buttonLink(p.deep_dive_path || "./index.html", "Open project deep dive", { newTab: false, primary: true })}
        ${buttonLink(p.lab_path || "./lab.html", "LAB links", { newTab: false })}
      </div>
    `;
    projectGrid.appendChild(article);
  });
}

function renderPolicyCards(policies, targetElId) {
  const container = document.getElementById(targetElId);
  container.innerHTML = "";

  (policies || []).forEach((policy) => {
    const block = document.createElement("article");
    block.className = "card";

    const heading = document.createElement("h3");
    heading.textContent = `${toTitle(policy.threshold_policy)} (target ${fmtPct(policy.target_recall)})`;

    const intro = document.createElement("p");
    intro.className = "muted";
    intro.textContent = "Baseline row is +0 additional documents under this stopping policy.";

    const table = tableHtml(
      [
        { key: "additional_docs_requested", label: "Additional docs" },
        { key: "screened_docs_total", label: "Total screened" },
        { key: "fn", label: "Expected FN", render: (v) => fmtNum(v, 2) },
        { key: "fp", label: "Expected FP", render: (v) => fmtNum(v, 2) },
        { key: "recall", label: "Recall", render: (v) => fmtPct(v, 1) },
        { key: "precision", label: "Precision", render: (v) => fmtPct(v, 1) },
        { key: "work_saved_fraction", label: "Work saved", render: (v) => fmtPct(v, 1) },
      ],
      policy.rows || [],
      {
        rowClassFn: (r) => (Number(r.additional_docs_requested) === 0 ? "baseline" : ""),
      }
    );

    block.appendChild(heading);
    block.appendChild(intro);
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

function renderPlanner(planner) {
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
        { key: "fn", label: "Expected FN", render: (v) => fmtNum(v, 2) },
        { key: "fp", label: "Expected FP", render: (v) => fmtNum(v, 2) },
        { key: "recall", label: "Recall", render: (v) => fmtPct(v, 1) },
        { key: "precision", label: "Precision", render: (v) => fmtPct(v, 1) },
        { key: "work_saved_fraction", label: "Work saved", render: (v) => fmtPct(v, 1) },
      ],
      filtered,
      {
        rowClassFn: (r) => (Number(r.additional_docs_requested) === 0 ? "baseline" : ""),
      }
    );
  }

  policyEl.addEventListener("change", rerender);
  bandEl.addEventListener("change", rerender);
  addEl.addEventListener("change", rerender);

  const rec = planner.recommended_targets || {};
  document.getElementById("planner-recommendation").innerHTML = `
    <h3>Recommended staged targets</h3>
    <p><strong>Immediate stage:</strong> +${rec.immediate_additional_docs || 50} records.</p>
    <p><strong>If stricter assurance is required:</strong> continue to +${rec.contingent_additional_docs || 100}.</p>
    <p class="muted">Planning note: scenario values are approximations from current active-learning traces and should be refreshed after new labels are synced.</p>
  `;

  rerender();
}

async function renderProjectE5cr7() {
  const [catalog, overview, methodsResults, fnFpRisk, planner] = await Promise.all([
    loadJson("./data/compendium_catalog.json"),
    loadJson("./data/artifacts/overview.json"),
    loadJson("./data/artifacts/methods_results.json"),
    loadJson("./data/artifacts/fn_fp_risk.json"),
    loadJson("./data/artifacts/simulation_planner.json"),
  ]);

  const project = findProject(catalog, "e5cr7") || {};

  document.getElementById("e5cr7-cta-row").innerHTML = [
    buttonLink(catalog.shared_lab.entrypoint_url, "Open shared LAB URL", { primary: true }),
    buttonLink("./lab.html", "Open LAB landing page", { newTab: false }),
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
    <p><strong>Current recommendation:</strong> screen <strong>+${rec.immediate_additional_docs}</strong> records now, then reassess.</p>
    <p><strong>If stricter residual-risk tolerance is required:</strong> continue to <strong>+${rec.contingent_additional_docs}</strong>.</p>
    <p>After the immediate stage, projected false negatives are <strong>${fmtNum(rec.expected_fn_after_immediate, 2)}</strong>
    (reduction of <strong>${fmtNum(rec.expected_fn_reduction_after_immediate, 2)}</strong> vs current baseline stopping point).</p>
  `;

  document.getElementById("e5cr7-methods-list").innerHTML = (methodsResults.methods || [])
    .map((m) => `<li>${m}</li>`)
    .join("");

  const leaderboardRows = (methodsResults.model_leaderboard || []).map((r) => ({
    model: r.model,
    average_precision: fmtNum(r["average_precision"], 3),
    wss95: fmtNum(r["wss@95"], 3),
    recall20: fmtNum(r["recall@20"], 3),
    recall50: fmtNum(r["recall@50"], 3),
    precision10: fmtNum(r["precision@10"], 3),
  }));

  document.getElementById("e5cr7-leaderboard-table").innerHTML = tableHtml(
    [
      { key: "model", label: "Model" },
      { key: "average_precision", label: "Average precision" },
      { key: "wss95", label: "WSS@95" },
      { key: "recall20", label: "Recall@20" },
      { key: "recall50", label: "Recall@50" },
      { key: "precision10", label: "Precision@10" },
    ],
    leaderboardRows
  );

  const bench = methodsResults.benchmarking || {};
  const benchWinner = bench.winner || {};
  const benchRunnerUp = bench.runner_up || {};
  const benchBestDory = bench.best_dory || {};
  const benchBestNeural = bench.best_neural || {};
  const benchBestNonDory = bench.best_non_dory || {};
  const benchComboCounts = bench.combo_matrix_counts || {};
  const benchInsights = bench.interpretation || [];

  const winnerName = benchWinner.display_name || "(not available)";
  const runnerName = benchRunnerUp.display_name || "(not available)";
  const winnerAp = fmtNum(benchWinner.average_precision_mean, 3);
  const runnerAp = fmtNum(benchRunnerUp.average_precision_mean, 3);

  const dorySummary = benchBestDory.display_name
    ? ` Best Dory result: ${benchBestDory.display_name} (AP ${fmtNum(benchBestDory.average_precision_mean, 3)}).`
    : "";
  const neuralSummary = benchBestNeural.display_name
    ? ` Best neural result: ${benchBestNeural.display_name} (AP ${fmtNum(benchBestNeural.average_precision_mean, 3)}).`
    : "";

  document.getElementById("e5cr7-benchmark-plain").innerHTML =
    `<strong>Plain-language read:</strong> ${winnerName} currently leads on ranking quality (AP ${winnerAp}). ` +
    `Runner-up is ${runnerName} (AP ${runnerAp}).` +
    dorySummary +
    neuralSummary +
    ` Use the winner when recall-first performance matters; use faster alternatives when frequent retraining speed is the main constraint.`;

  const benchRows = (bench.model_results || []).map((r) => ({
    rank: r.rank,
    cohort: toTitle(r.cohort),
    model: r.display_name,
    ap: fmtNum(r.average_precision_mean, 3),
    roc: fmtNum(r.roc_auc_mean, 3),
    wss95: fmtNum(r["wss@95_mean"], 3),
    recall20: fmtNum(r["recall@20_mean"], 3),
    precision20: fmtNum(r["precision@20_mean"], 3),
    fit: fmtNum(r.fit_seconds_mean, 3),
  }));

  document.getElementById("e5cr7-benchmark-table").innerHTML = tableHtml(
    [
      { key: "rank", label: "Rank" },
      { key: "cohort", label: "Cohort" },
      { key: "model", label: "Model" },
      { key: "ap", label: "AP (mean)" },
      { key: "roc", label: "ROC-AUC (mean)" },
      { key: "wss95", label: "WSS@95 (mean)" },
      { key: "recall20", label: "Recall@20 (mean)" },
      { key: "precision20", label: "Precision@20 (mean)" },
      { key: "fit", label: "Fit time sec/fold" },
    ],
    benchRows
  );

  const blockers = (bench.blocked_models || []).map(
    (b) => `<li><strong>${b.display_name || b.model_id}</strong>: ${b.reason || "Unavailable"}</li>`
  );

  const comboSummary = `Combo sweep: attempted ${benchComboCounts.attempted ?? "?"}, succeeded ${benchComboCounts.succeeded ?? "?"}, failed ${benchComboCounts.failed ?? "?"}, skipped ${benchComboCounts.skipped ?? "?"}.`;

  const doryGapText = benchBestDory.display_name && benchBestNonDory.display_name
    ? `Best Dory vs current best non-Dory AP gap: ${(Number(benchBestDory.average_precision_mean) - Number(benchBestNonDory.average_precision_mean)).toFixed(3)}.`
    : "";

  document.getElementById("e5cr7-benchmark-blockers").innerHTML = `
    <h4>Unavailable/heavy options</h4>
    ${blockers.length ? `<ul>${blockers.join("")}</ul>` : "<p class=\"muted\">No blocked models reported.</p>"}
    <p class="muted">${comboSummary} ${doryGapText}</p>
    ${benchInsights.length ? `<p class=\"muted\">${benchInsights.join(" ")}</p>` : ""}
  `;

  document.getElementById("e5cr7-baseline-definition").innerHTML =
    "<strong>Baseline definition:</strong> in this table, <em>Baseline</em> is the pre-improvement reference run (reproduced from the baseline pipeline), and <em>Improved</em> is the best current model configuration (<code>calibrated_svm_word_char</code>).";

  document.getElementById("e5cr7-comparison-table").innerHTML = tableHtml(
    [
      { key: "metric", label: "Metric" },
      { key: "baseline", label: "Baseline", render: (v) => fmtNum(v, 4) },
      { key: "improved_best", label: "Improved", render: (v) => fmtNum(v, 4) },
      {
        key: "delta",
        label: "Delta (improved - baseline)",
        render: (v) => {
          const n = Number(v);
          const cls = n >= 0 ? "good" : "warn";
          return `<span class="badge ${cls}">${n >= 0 ? "+" : ""}${fmtNum(n, 4)}</span>`;
        },
      },
    ],
    methodsResults.baseline_vs_improved || []
  );

  const nestedRows = methodsResults.nested_cv_summary || [];
  const nested = Object.fromEntries(nestedRows.map((r) => [r.metric, r]));
  document.getElementById("e5cr7-nested-cv").innerHTML = kvHtml([
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

  document.getElementById("e5cr7-why-list").innerHTML = (fnFpRisk.framing?.why_more_review || [])
    .map((x) => `<li>${x}</li>`)
    .join("");
  document.getElementById("e5cr7-risk-source-note").textContent = fnFpRisk.framing?.source_note || "";

  renderPolicyCards(fnFpRisk.story?.policies || [], "e5cr7-fnfp-policies");
  renderPlanner(planner);

  document.getElementById("e5cr7-lab-links").innerHTML = `
    <div class="cta-row">
      ${buttonLink(catalog.shared_lab.entrypoint_url, "Open shared gateway", { primary: true })}
      ${buttonLink("./lab.html", "All LAB endpoints", { newTab: false })}
      ${buttonLink(project.legacy_lab_url || catalog.shared_lab.entrypoint_url, "Current/legacy URL")}
    </div>
  `;
}

async function renderLabShared() {
  const catalog = await loadJson("./data/compendium_catalog.json");

  document.getElementById("shared-lab-gateway").innerHTML = `
    <p><strong>${catalog.shared_lab.display_name}</strong></p>
    <p class="muted">${catalog.shared_lab.entrypoint_note}</p>
    <div class="cta-row">
      ${buttonLink(catalog.shared_lab.entrypoint_url, "Open shared LAB URL", { primary: true })}
      ${buttonLink("./index.html#projects", "Back to projects", { newTab: false })}
    </div>
  `;

  const list = document.getElementById("lab-project-list");
  list.innerHTML = "";

  (catalog.projects || []).forEach((p) => {
    const item = document.createElement("article");
    item.className = "card";
    item.innerHTML = `
      <h3>${p.name}</h3>
      <p>${p.summary || ""}</p>
      <div class="cta-row">
        ${buttonLink(p.deep_dive_path || "./index.html", "Project deep dive", { newTab: false, primary: true })}
        ${buttonLink(p.legacy_lab_url || catalog.shared_lab.entrypoint_url, "Current/legacy URL")}
      </div>
    `;
    list.appendChild(item);
  });
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
