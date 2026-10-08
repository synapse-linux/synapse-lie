// SPDX-License-Identifier: MIT
"use strict";

const CATALOG_URL = "data/catalog.json";
const FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const INTEGER = new Intl.NumberFormat("en-US");
const SERIES_COLORS = ["#1b9f9a", "#e88147", "#5272d8", "#9472d9", "#a3a02f", "#375a72"];
const csvCache = new Map();
const state = { platform: "strix-halo", model: "qwen-q2", workload: "single", campaign: "counting-full", selectedSeries: [], request: 0 };
let catalog = null;
let activeDataset = null;
let activeSeries = [];
let chartInstances = [];

function formatContext(value) {
  return value >= 1024 && value % 1024 === 0 ? INTEGER.format(value / 1024) + "K" : INTEGER.format(value);
}

function parseCsv(input) {
  const lines = input.trim().split(/\r?\n/);
  if (lines.length < 2) throw new Error("The CSV has no data rows.");
  const headers = lines.shift().split(",");
  const rows = lines.map((line, index) => {
    const cells = line.split(",");
    if (cells.length !== headers.length) throw new Error("Invalid CSV row " + (index + 2) + ".");
    return Object.fromEntries(headers.map((header, column) => [header, cells[column]]));
  });
  return { headers, rows };
}

function numeric(row, field) {
  const value = Number(row[field]);
  if (!Number.isFinite(value) || value < 0 || row[field] === "") throw new Error("Invalid " + field + " in benchmark CSV.");
  return value;
}

function validateCatalog(value) {
  if (value.schema_version !== 1 || !Array.isArray(value.datasets) || !Array.isArray(value.models) || !Array.isArray(value.platforms) || !Array.isArray(value.workloads) || !Array.isArray(value.campaigns)) {
    throw new Error("Unsupported benchmark catalog.");
  }
  for (const dataset of value.datasets) {
    if (!value.models.some(model => model.id === dataset.model) || !value.platforms.some(platform => platform.id === dataset.platform) || !value.workloads.some(workload => workload.id === dataset.workload) || !value.campaigns.some(campaign => campaign.id === dataset.campaign)) {
      throw new Error("A dataset references an unknown model, platform, workload or campaign.");
    }
  }
  return value;
}

async function readCsv(path) {
  if (!csvCache.has(path)) {
    csvCache.set(path, fetch(path).then(response => {
      if (!response.ok) throw new Error("Could not load " + path + " (HTTP " + response.status + ").");
      return response.text();
    }).then(parseCsv));
  }
  return csvCache.get(path);
}

function normalizedRows(dataset, csv) {
  const coreColumns = ["tokens", "users", "prefill_tps", "decode_tps", "wall_output_tps", "prefill_seconds", "decode_seconds", "wall_seconds"];
  const longColumns = ["model", "prompt_tokens", "prefill_chunk", "warmup", "repetition", "physical_ids_sha256", "prefill_tps", "decode_tps", "prefill_seconds", "decode_seconds", "output_tokens"];
  const required = dataset.format === "core-flow-v1" ? coreColumns : dataset.format === "full-prefill-v1" ? longColumns : null;
  if (!required || required.some(column => !csv.headers.includes(column))) throw new Error("The CSV does not match its catalog schema.");
  const rows = [];
  for (const raw of csv.rows) {
    if (dataset.format === "core-flow-v1") {
      if (dataset.workload === "single" && Number(raw.users) !== 1) continue;
      rows.push({
        prompt: numeric(raw, "tokens"), users: numeric(raw, "users"), chunk: 2048,
        prefillTps: numeric(raw, "prefill_tps"), decodeTps: numeric(raw, "decode_tps"),
        wallTps: numeric(raw, "wall_output_tps"), prefillSeconds: numeric(raw, "prefill_seconds"),
        decodeSeconds: numeric(raw, "decode_seconds"), wallSeconds: numeric(raw, "wall_seconds")
      });
    } else if (raw.model === dataset.row_model && raw.warmup === "False") {
      if (raw.repetition !== "1" || Number(raw.output_tokens) !== 128) throw new Error("Unexpected full-context measurement contract.");
      rows.push({
        prompt: numeric(raw, "prompt_tokens"), users: 1, chunk: numeric(raw, "prefill_chunk"),
        promptSha: raw.physical_ids_sha256,
        prefillTps: numeric(raw, "prefill_tps"), decodeTps: numeric(raw, "decode_tps"),
        prefillSeconds: numeric(raw, "prefill_seconds"), decodeSeconds: numeric(raw, "decode_seconds")
      });
    }
  }
  if (!rows.length) throw new Error("No measured rows match this selection.");
  const keys = new Set();
  for (const row of rows) {
    const key = [row.prompt, row.users, row.chunk].join(":");
    if (keys.has(key)) throw new Error("Duplicate measurement " + key + ".");
    keys.add(key);
  }
  return rows.sort((a, b) => a.chunk - b.chunk || a.prompt - b.prompt || a.users - b.users);
}

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

function campaignsForWorkload() {
  const ids = new Set(catalog.datasets.filter(dataset => dataset.workload === state.workload).map(dataset => dataset.campaign));
  return catalog.campaigns.filter(campaign => ids.has(campaign.id));
}

function chooseCampaign() {
  const candidates = catalog.datasets.filter(dataset => dataset.workload === state.workload);
  const selected = candidates.find(dataset => dataset.campaign === state.campaign && dataset.model === state.model && dataset.platform === state.platform);
  if (selected) return;
  const next = candidates.find(dataset => dataset.model === state.model && dataset.platform === state.platform)
    || candidates.find(dataset => dataset.model === state.model)
    || candidates[0];
  if (next) state.campaign = next.campaign;
}

function select(type, id) {
  state[type] = id;
  if (type === "workload" || type === "model") chooseCampaign();
  renderOptions();
  showSelection();
}

function fillSelect(id, items, type) {
  const control = document.getElementById(id);
  control.replaceChildren(...items.map(item => {
    const option = element("option", "", item.name);
    option.value = item.id;
    return option;
  }));
  control.value = state[type];
}

function renderOptions() {
  const workload = document.getElementById("workload-options");
  workload.replaceChildren();
  for (const item of catalog.workloads) {
    const button = element("button", "mode-option", item.name);
    button.type = "button";
    button.setAttribute("aria-pressed", String(state.workload === item.id));
    button.addEventListener("click", () => select("workload", item.id));
    workload.append(button);
  }
  fillSelect("model-select", catalog.models, "model");
  fillSelect("platform-select", catalog.platforms, "platform");
  fillSelect("campaign-select", campaignsForWorkload(), "campaign");
  document.getElementById("campaign-detail").textContent = catalog.campaigns.find(item => item.id === state.campaign)?.detail || "Select a measured campaign.";
}

function selectedSeries() {
  return activeSeries.filter(series => state.selectedSeries.includes(series.id));
}

function rowsForView() {
  return selectedSeries().flatMap(series => series.rows.map(row => ({ ...row, seriesLabel: series.label })))
    .sort((a, b) => a.prompt - b.prompt || a.users - b.users || a.seriesLabel.localeCompare(b.seriesLabel));
}

function makeInsight(label, value, note, accent) {
  const card = element("article", "insight-card" + (accent ? " insight-accent" : ""));
  card.append(element("p", "", label), element("strong", "", value), element("span", "", note));
  return card;
}

function renderInsights() {
  const target = document.getElementById("insight-grid");
  target.replaceChildren();
  const choices = selectedSeries();
  const focused = state.workload === "concurrent"
    ? choices[choices.length - 1]
    : choices.find(series => series.model === state.model && series.chunk === 2048) || choices.find(series => series.model === state.model) || choices[0];
  const last = focused.rows[focused.rows.length - 1];
  const label = focused.label + " · " + formatContext(last.prompt);
  target.append(
    makeInsight(label + " prefill", FORMAT.format(last.prefillTps), "input tokens per second · longest measured prompt", true),
    makeInsight(label + " decode", FORMAT.format(last.decodeTps), state.workload === "concurrent" ? "combined output tokens per second · longest prompt" : "output tokens per second · longest measured prompt")
  );
}

function renderToolbar() {
  const toolbar = document.getElementById("chart-toolbar");
  toolbar.replaceChildren();
  toolbar.hidden = !activeSeries.length;
  if (toolbar.hidden) return;
  const heading = element("div", "toolbar-copy");
  heading.append(element("strong", "", state.workload === "concurrent" ? "Concurrent requests" : "Measured curves"),
    element("span", "", state.selectedSeries.length + " of " + activeSeries.length + " selected · choose any combination"));
  const group = element("div", "toolbar-options");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", state.workload === "concurrent" ? "Concurrent request counts" : "Measured model and chunk curves");
  for (const series of activeSeries) {
    const selected = state.selectedSeries.includes(series.id);
    const button = element("button", "toolbar-option", series.label);
    button.type = "button";
    button.setAttribute("aria-pressed", String(selected));
    button.style.setProperty("--series-color", series.color);
    button.addEventListener("click", () => {
      if (selected && state.selectedSeries.length === 1) return;
      state.selectedSeries = selected ? state.selectedSeries.filter(id => id !== series.id) : [...state.selectedSeries, series.id];
      renderDataset();
    });
    group.append(button);
  }
  const all = element("button", "toolbar-reset", "Show all");
  all.type = "button";
  all.disabled = state.selectedSeries.length === activeSeries.length;
  all.addEventListener("click", () => { state.selectedSeries = activeSeries.map(series => series.id); renderDataset(); });
  toolbar.append(heading, group, all);
}

function chartConfigurations() {
  return [
    { key: "prefillTps", title: "Prefill throughput", description: "Input tokens processed per second. The vertical axis starts at zero.", unit: "input tok/s", color: "#1b9f9a" },
    { key: "decodeTps", title: "Decode throughput", description: state.workload === "single" ? "Output tokens generated per second for one request. The vertical axis starts at zero." : "Combined output across the selected request group, not per-user speed. The vertical axis starts at zero.", unit: "output tok/s", color: "#e88147" }
  ];
}

function chartSeries() {
  return selectedSeries().map(series => ({ name: series.label, color: series.color, model: series.model, rows: series.rows }));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function drawChart(host, config, index) {
  if (!window.echarts) throw new Error("The chart library could not be loaded.");
  const article = element("article", "chart-card");
  const heading = element("div", "chart-heading");
  const title = element("div");
  title.append(element("p", "chart-number", "CHART " + String(index + 1).padStart(2, "0")), element("h4", "", config.title));
  heading.append(title, element("span", "chart-unit", config.unit));
  article.append(heading, element("p", "chart-description", config.description));
  const long = activeDataset.format === "full-prefill-v1";
  const series = chartSeries();
  const key = element("div", "chart-key");
  key.setAttribute("aria-label", "Visible curves");
  for (const item of series) {
    const label = element("span", "chart-key-item");
    const marker = element("span", "chart-key-marker");
    marker.style.backgroundColor = item.color;
    marker.setAttribute("aria-hidden", "true");
    label.append(marker, document.createTextNode(item.name));
    key.append(label);
  }
  article.append(key);
  const plot = element("div", "chart-plot");
  plot.setAttribute("role", "img");
  plot.setAttribute("aria-label", config.title + " by prompt length for the selected curves. Vertical axis begins at zero. Values are in the table below.");
  article.append(plot);
  host.append(article);
  const chart = window.echarts.init(plot, null, { renderer: "svg" });
  chartInstances.push(chart);
  chart.setOption({
    animation: false,
    color: series.map(item => item.color),
    grid: { top: 24, left: 16, right: 23, bottom: long ? 77 : 42, containLabel: true },
    legend: { show: false },
    tooltip: {
      trigger: "axis", confine: true, axisPointer: { type: "line" },
      formatter: items => {
        const at = formatContext(items[0].value[0]) + " prompt";
        return "<strong>" + escapeHtml(at) + "</strong><br>" + items.map(item =>
          escapeHtml(item.seriesName) + ": <strong>" + FORMAT.format(item.value[1]) + " " + escapeHtml(config.unit) + "</strong>"
        ).join("<br>");
      }
    },
    xAxis: {
      type: "value", min: 0,
      name: "Prompt tokens", nameLocation: "middle", nameGap: 28,
      axisLabel: { color: "#657987", hideOverlap: true, formatter: value => window.innerWidth < 600 && value >= 1000 ? INTEGER.format(value / 1000) + "k" : formatContext(value) },
      axisLine: { lineStyle: { color: "#aebfc5" } }, splitLine: { show: false }
    },
    yAxis: {
      type: "value", min: 0, scale: false, name: config.unit, nameTextStyle: { color: "#657987" },
      axisLabel: { color: "#657987", formatter: value => INTEGER.format(value) },
      axisLine: { show: true, lineStyle: { color: "#aebfc5" } },
      splitLine: { lineStyle: { color: "#e8eeec" } }
    },
    dataZoom: long ? [
      { type: "inside", xAxisIndex: 0, filterMode: "none" },
      { type: "slider", xAxisIndex: 0, filterMode: "none", bottom: 7, height: 20, borderColor: "#d3dfd8", fillerColor: "rgba(27,159,154,.12)" }
    ] : [],
    series: series.map(item => ({
      name: item.name, type: "line", smooth: false, showSymbol: item.rows.length <= 12, symbolSize: 7,
      lineStyle: { width: item.model === state.model ? 3.3 : 2.4 }, emphasis: { focus: "series" },
      data: item.rows.map(row => [row.prompt, row[config.key]])
    }))
  });
}

function renderTable(rows) {
  const table = document.getElementById("benchmark-table");
  const head = table.querySelector("thead"), body = table.querySelector("tbody");
  const long = activeDataset.format === "full-prefill-v1";
  const columns = [
    ["Series", "seriesLabel"], ["Prompt tokens", "prompt"],
    ...(state.workload === "concurrent" ? [["Requests", "users"]] : []),
    ...(long ? [["Chunk tokens", "chunk"]] : []),
    ["Prefill t/s", "prefillTps"], ["Decode t/s", "decodeTps"],
    ...(state.workload === "concurrent" ? [["Whole-group t/s", "wallTps"]] : []),
    ["Prefill seconds", "prefillSeconds"], ["Decode seconds", "decodeSeconds"]
  ];
  const tr = element("tr");
  for (const [label] of columns) {
    const th = element("th", "", label);
    th.scope = "col";
    tr.append(th);
  }
  head.replaceChildren(tr);
  body.replaceChildren();
  for (const row of rows) {
    const record = element("tr");
    for (const [, field] of columns) {
      const value = field === "seriesLabel" ? row[field] : ["prompt", "users", "chunk"].includes(field) ? INTEGER.format(row[field]) : FORMAT.format(row[field]) + (field.endsWith("Seconds") ? " s" : "");
      record.append(element("td", "", value));
    }
    body.append(record);
  }
  document.getElementById("benchmark-caption").textContent = rows.length + " measured rows for the selected workload and series. Rates are tokens per second.";
}

function renderDataset() {
  const rows = rowsForView();
  document.getElementById("benchmark-status").textContent = rows.length + " measured rows shown from the selected campaign.";
  renderToolbar();
  const comparisonNote = document.getElementById("comparison-note");
  const long = activeDataset.format === "full-prefill-v1";
  comparisonNote.hidden = !long;
  if (long) {
    const matched = activeSeries.some(series => series.model === "qwen-q2" && series.chunk === 2048) && activeSeries.some(series => series.model === "qwen-ud-q4" && series.chunk === 2048);
    comparisonNote.textContent = matched
      ? "Matched model comparison: Q2 2K and UD-Q4 2K use the same physical prompts and measurement contract. Q2 4K/8K change the chunk size; read those as a separate diagnostic."
      : "Only curves from the same platform and campaign are shown. Different chunk sizes are a separate diagnostic.";
  }
  renderInsights();
  const host = document.getElementById("chart-grid");
  for (const chart of chartInstances) chart.dispose();
  chartInstances = [];
  host.replaceChildren();
  chartConfigurations().forEach((config, index) => drawChart(host, config, index));
  renderTable(rows);
}

function renderMethod(dataset) {
  const list = document.getElementById("dataset-conditions");
  list.replaceChildren(...dataset.conditions.map(value => element("li", "", value)));
  const hasMatchedQ2Ud = dataset.format === "full-prefill-v1" && activeSeries.some(series => series.model === "qwen-q2" && series.chunk === 2048) && activeSeries.some(series => series.model === "qwen-ud-q4" && series.chunk === 2048);
  document.getElementById("dataset-caveat").textContent = dataset.caveat + (hasMatchedQ2Ud ? " Q2/UD at 2K are matched; Q2 at 4K/8K changes the chunk size." : "");
  const quality = document.getElementById("quality-link");
  quality.hidden = !dataset.quality;
  if (dataset.quality) quality.href = dataset.quality;
}

async function showSelection() {
  const request = ++state.request;
  const dataset = catalog.datasets.find(item => item.platform === state.platform && item.model === state.model && item.workload === state.workload && item.campaign === state.campaign);
  const available = document.getElementById("dataset-available"), empty = document.getElementById("dataset-empty"), status = document.getElementById("benchmark-status");
  if (!dataset) {
    activeDataset = null;
    activeSeries = [];
    renderToolbar();
    available.hidden = true;
    empty.hidden = false;
    status.textContent = "No qualified CSV for this selection.";
    const platform = catalog.platforms.find(item => item.id === state.platform);
    const model = catalog.models.find(item => item.id === state.model);
    const campaign = catalog.campaigns.find(item => item.id === state.campaign);
    document.getElementById("empty-description").textContent = model.name + " on " + platform.name + " has no integrated measurement for " + campaign.name + ". We leave the chart empty instead of inventing a number.";
    return;
  }
  available.hidden = true;
  empty.hidden = true;
  status.textContent = "Loading measured CSV…";
  try {
    const comparable = dataset.format === "full-prefill-v1" && dataset.comparison_group
      ? catalog.datasets.filter(item => item.workload === dataset.workload && item.platform === dataset.platform && item.campaign === dataset.campaign && item.format === dataset.format && item.comparison_group === dataset.comparison_group)
      : [dataset];
    const sources = await Promise.all(comparable.map(async item => ({ item, rows: normalizedRows(item, await readCsv(item.csv)) })));
    const series = [];
    if (dataset.format === "full-prefill-v1") {
      const promptHashes = new Map();
      for (const source of sources) {
        for (const row of source.rows) {
          if (!/^[0-9a-f]{64}$/.test(row.promptSha)) throw new Error("Invalid physical prompt hash in long-context CSV.");
          if (promptHashes.has(row.prompt) && promptHashes.get(row.prompt) !== row.promptSha) throw new Error("Comparison series use different physical prompts.");
          promptHashes.set(row.prompt, row.promptSha);
        }
      }
      for (const source of sources) {
        const model = catalog.models.find(item => item.id === source.item.model);
        for (const chunk of [...new Set(source.rows.map(row => row.chunk))].sort((a, b) => a - b)) {
          series.push({
            id: source.item.id + ":" + chunk,
            label: (model.chart_name || model.name) + " · " + formatContext(chunk) + " chunk",
            model: source.item.model, chunk, rows: source.rows.filter(row => row.chunk === chunk)
          });
        }
      }
      series.sort((a, b) => a.chunk - b.chunk || a.model.localeCompare(b.model));
    } else if (state.workload === "concurrent") {
      const rows = sources[0].rows;
      for (const users of [...new Set(rows.map(row => row.users))].sort((a, b) => a - b)) {
        series.push({
          id: dataset.id + ":C" + users,
          label: "C" + users + " · " + users + (users === 1 ? " request" : " requests"),
          model: dataset.model, users, rows: rows.filter(row => row.users === users)
        });
      }
    } else {
      const model = catalog.models.find(item => item.id === dataset.model);
      series.push({ id: dataset.id, label: (model.chart_name || model.name) + " · C1", model: dataset.model, users: 1, rows: sources[0].rows });
    }
    series.forEach((item, index) => { item.color = SERIES_COLORS[index % SERIES_COLORS.length]; });
    if (request !== state.request) return;
    const sameCampaign = activeDataset && activeDataset.campaign === dataset.campaign && activeDataset.platform === dataset.platform && activeDataset.workload === dataset.workload;
    const previous = sameCampaign ? state.selectedSeries.filter(id => series.some(item => item.id === id)) : [];
    activeDataset = dataset;
    activeSeries = series;
    state.selectedSeries = previous.length ? previous : dataset.format === "full-prefill-v1" ? series.filter(item => item.chunk === 2048).map(item => item.id) : series.map(item => item.id);
    if (!state.selectedSeries.length) state.selectedSeries = [series[0].id];
    if (dataset.format === "full-prefill-v1" && !series.some(item => item.model === state.model && state.selectedSeries.includes(item.id))) {
      const focused = series.find(item => item.model === state.model && item.chunk === 2048) || series.find(item => item.model === state.model);
      if (focused) state.selectedSeries.push(focused.id);
    }
    document.getElementById("dataset-overline").textContent = state.workload === "concurrent" ? "NATIVE BATCH TEST" : "SINGLE REQUEST TEST";
    document.getElementById("dataset-title").textContent = dataset.title;
    document.getElementById("dataset-intro").textContent = dataset.intro;
    document.getElementById("dataset-download").href = dataset.csv;
    renderMethod(dataset);
    available.hidden = false;
    renderDataset();
  } catch (error) {
    if (request !== state.request) return;
    activeDataset = null;
    activeSeries = [];
    renderToolbar();
    available.hidden = true;
    empty.hidden = false;
    status.textContent = "Could not load the benchmark: " + error.message;
    document.getElementById("empty-description").textContent = "The source CSV or its schema could not be loaded. Please use the data catalog or try again later.";
  }
}

function initInstallTabs() {
  const tabs = [...document.querySelectorAll("[role='tab'][data-distro]")];
  const activate = tab => {
    for (const candidate of tabs) {
      const selected = candidate === tab;
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      document.getElementById(candidate.getAttribute("aria-controls")).hidden = !selected;
    }
  };
  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", event => {
      let next = index;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = tabs.length - 1;
      else return;
      event.preventDefault();
      activate(tabs[next]);
      tabs[next].focus();
    });
  }
}

async function copyText(value) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try { await navigator.clipboard.writeText(value); return; } catch { /* Use the local fallback. */ }
  }
  const input = element("textarea");
  input.value = value;
  input.style.position = "fixed";
  input.style.opacity = "0";
  document.body.append(input);
  input.select();
  const copied = document.execCommand("copy");
  input.remove();
  if (!copied) throw new Error("Copy failed");
}

function initCopyButtons() {
  for (const button of document.querySelectorAll(".copy-button")) {
    button.addEventListener("click", async () => {
      try {
        await copyText(button.closest(".code-block").querySelector("code").textContent);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Select text";
      }
      setTimeout(() => { button.textContent = "Copy"; }, 2200);
    });
  }
}

async function initExplorer() {
  const status = document.getElementById("benchmark-status");
  window.addEventListener("resize", () => { for (const chart of chartInstances) chart.resize(); });
  for (const [id, type] of [["model-select", "model"], ["platform-select", "platform"], ["campaign-select", "campaign"]]) {
    document.getElementById(id).addEventListener("change", event => select(type, event.target.value));
  }
  try {
    const response = await fetch(CATALOG_URL);
    if (!response.ok) throw new Error("Catalog returned HTTP " + response.status + ".");
    catalog = validateCatalog(await response.json());
    renderOptions();
    const core = await readCsv("data/q2-core-model-flow-2k8k.csv");
    const example = normalizedRows(catalog.datasets.find(item => item.id === "q2-promessi-single"), core).find(row => row.prompt === 2048);
    document.querySelector("[data-hero='prefill']").textContent = FORMAT.format(example.prefillTps);
    document.querySelector("[data-hero='decode']").textContent = FORMAT.format(example.decodeTps);
    await showSelection();
  } catch (error) {
    status.classList.add("error");
    status.textContent = "Could not load the benchmark explorer: " + error.message;
  }
}

initInstallTabs();
initCopyButtons();
if (document.getElementById("benchmark-status")) initExplorer();
