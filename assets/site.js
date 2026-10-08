// SPDX-License-Identifier: MIT
"use strict";

const CATALOG_URL = "data/catalog.json";
const FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const INTEGER = new Intl.NumberFormat("en-US");
const SERIES_COLORS = new Map([[2048, "#1b9f9a"], [4096, "#e88147"], [6144, "#5272d8"], [8192, "#9472d9"]]);
const LONG_COLORS = ["#1b9f9a", "#e88147", "#5272d8", "#9472d9"];
const csvCache = new Map();
const state = { platform: "strix-halo", model: "qwen-q2", workload: "single", contexts: [2048, 4096, 6144, 8192], selectedSeries: [], request: 0 };
let catalog = null;
let activeRows = [];
let activeDataset = null;
let activeLongSeries = [];
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
  if (value.schema_version !== 1 || !Array.isArray(value.datasets) || !Array.isArray(value.models) || !Array.isArray(value.platforms) || !Array.isArray(value.workloads)) {
    throw new Error("Unsupported benchmark catalog.");
  }
  for (const dataset of value.datasets) {
    if (!value.models.some(model => model.id === dataset.model) || !value.platforms.some(platform => platform.id === dataset.platform) || !value.workloads.some(workload => workload.id === dataset.workload)) {
      throw new Error("A dataset references an unknown model, platform or workload.");
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

function hasResult(type, id) {
  return catalog.datasets.some(dataset => dataset[type] === id);
}

function select(type, id) {
  state[type] = id;
  if (type === "model" && !catalog.datasets.some(dataset => dataset.platform === state.platform && dataset.model === state.model && dataset.workload === state.workload)) {
    const first = catalog.datasets.find(dataset => dataset.platform === state.platform && dataset.model === state.model);
    if (first) state.workload = first.workload;
  }
  renderOptions();
  showSelection();
}

function renderOptionList(containerId, items, type) {
  const container = document.getElementById(containerId);
  container.replaceChildren();
  for (const item of items) {
    const button = element("button", "selector-option");
    button.type = "button";
    button.setAttribute("aria-pressed", String(state[type] === item.id));
    const title = element("strong", "", item.name);
    const detail = element("small", "", item.detail);
    const badge = element("span", hasResult(type, item.id) ? "option-badge" : "option-badge pending", hasResult(type, item.id) ? "Measured" : "Awaiting data");
    button.append(title, detail, badge);
    button.addEventListener("click", () => select(type, item.id));
    container.append(button);
  }
}

function renderOptions() {
  renderOptionList("workload-options", catalog.workloads, "workload");
  renderOptionList("model-options", catalog.models, "model");
  renderOptionList("platform-options", catalog.platforms, "platform");
}

function rowsForView() {
  if (state.workload === "long") {
    return selectedLongSeries().flatMap(series => series.rows.map(row => ({ ...row, seriesLabel: series.label })))
      .sort((a, b) => a.prompt - b.prompt || a.seriesLabel.localeCompare(b.seriesLabel));
  }
  if (state.workload === "concurrent") return activeRows.filter(row => state.contexts.includes(row.prompt));
  return activeRows;
}

function selectedLongSeries() {
  return activeLongSeries.filter(series => state.selectedSeries.includes(series.id));
}

function makeInsight(label, value, note, accent) {
  const card = element("article", "insight-card" + (accent ? " insight-accent" : ""));
  card.append(element("p", "", label), element("strong", "", value), element("span", "", note));
  return card;
}

function renderInsights(rows) {
  const target = document.getElementById("insight-grid");
  target.replaceChildren();
  if (state.workload === "single") {
    const last = rows[rows.length - 1];
    target.append(
      makeInsight(formatContext(last.prompt) + " prefill", FORMAT.format(last.prefillTps), "input tokens per second", true),
      makeInsight(formatContext(last.prompt) + " decode", FORMAT.format(last.decodeTps), "output tokens per second")
    );
  } else if (state.workload === "long") {
    for (const series of selectedLongSeries()) {
      const last = series.rows[series.rows.length - 1];
      target.append(
        makeInsight(series.label + " · " + formatContext(last.prompt) + " prefill", FORMAT.format(last.prefillTps), "input tokens per second", series.model === state.model),
        makeInsight(series.label + " · " + formatContext(last.prompt) + " decode", FORMAT.format(last.decodeTps), "output tokens per second")
      );
    }
  } else {
    const context = Math.min(...state.contexts);
    const subset = rows.filter(row => row.prompt === context);
    const last = subset[subset.length - 1];
    target.append(
      makeInsight(formatContext(context) + " · C" + last.users + " prefill", FORMAT.format(last.prefillTps), "group input tokens per second", true),
      makeInsight(formatContext(context) + " · C" + last.users + " decode", FORMAT.format(last.decodeTps), "group output tokens per second")
    );
  }
}

function renderToolbar() {
  const toolbar = document.getElementById("chart-toolbar");
  toolbar.replaceChildren();
  toolbar.hidden = state.workload === "single";
  if (toolbar.hidden) return;
  const heading = element("div", "toolbar-copy");
  heading.append(element("strong", "", state.workload === "long" ? "Overlay measured series" : "Prompt per user"),
    element("span", "", state.workload === "long" ? "Select one or more lines for direct visual comparison." : "Toggle context lengths to focus the curves."));
  const group = element("div", "toolbar-options");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", state.workload === "long" ? "Measured model and chunk series" : "Prompt length per user");
  const choices = state.workload === "long" ? activeLongSeries : [...new Set(activeRows.map(row => row.prompt))].sort((a, b) => a - b);
  for (const value of choices) {
    const selected = state.workload === "long" ? state.selectedSeries.includes(value.id) : state.contexts.includes(value);
    const button = element("button", "toolbar-option", state.workload === "long" ? value.label : formatContext(value));
    button.type = "button";
    button.setAttribute("aria-pressed", String(selected));
    button.addEventListener("click", () => {
      if (state.workload === "long") {
        if (selected && state.selectedSeries.length === 1) return;
        state.selectedSeries = selected ? state.selectedSeries.filter(id => id !== value.id) : [...state.selectedSeries, value.id];
      }
      else if (selected && state.contexts.length > 1) state.contexts = state.contexts.filter(item => item !== value);
      else if (!selected) state.contexts.push(value);
      renderDataset();
    });
    group.append(button);
  }
  toolbar.append(heading, group);
}

function chartConfigurations() {
  const prompt = state.workload !== "concurrent";
  return [
    { key: "prefillTps", title: "Prefill throughput", description: "Input tokens processed per second. The vertical axis starts at zero.", unit: "input tok/s", color: "#1b9f9a" },
    { key: "decodeTps", title: "Decode throughput", description: prompt ? "Output tokens generated per second for one user. The vertical axis starts at zero." : "Combined output across the group, not per-user speed. The vertical axis starts at zero.", unit: "output tok/s", color: "#e88147" }
  ];
}

function chartSeries(rows, config) {
  if (state.workload === "long") {
    return selectedLongSeries().map(series => ({ name: series.label, color: series.color, model: series.model, rows: series.rows }));
  }
  if (state.workload === "concurrent") {
    return [...new Set(rows.map(row => row.prompt))].sort((a, b) => a - b).map(prompt => ({
      name: formatContext(prompt) + " prompt", color: SERIES_COLORS.get(prompt), rows: rows.filter(row => row.prompt === prompt)
    }));
  }
  return [{ name: "One request", color: config.color, rows }];
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
}

function drawChart(host, config, rows, index) {
  if (!window.echarts) throw new Error("The chart library could not be loaded.");
  const article = element("article", "chart-card");
  const heading = element("div", "chart-heading");
  const title = element("div");
  title.append(element("p", "chart-number", "CHART " + String(index + 1).padStart(2, "0")), element("h4", "", config.title));
  heading.append(title, element("span", "chart-unit", config.unit));
  article.append(heading, element("p", "chart-description", config.description));
  const plot = element("div", "chart-plot");
  plot.setAttribute("role", "img");
  plot.setAttribute("aria-label", config.title + " by " + (state.workload === "concurrent" ? "concurrent users" : "prompt length") + ". Vertical axis begins at zero. Values are in the table below.");
  article.append(plot);
  host.append(article);
  const multi = state.workload === "concurrent", long = state.workload === "long";
  const series = chartSeries(rows, config);
  const chart = window.echarts.init(plot, null, { renderer: "svg" });
  chartInstances.push(chart);
  chart.setOption({
    animation: false,
    color: series.map(item => item.color),
    grid: { top: series.length > 1 ? 59 : 24, left: 16, right: 23, bottom: long ? 77 : 42, containLabel: true },
    legend: { show: series.length > 1, type: "scroll", top: 8, textStyle: { color: "#526674", fontSize: 11 }, itemWidth: 19, itemHeight: 4 },
    tooltip: {
      trigger: "axis", confine: true, axisPointer: { type: "line" },
      formatter: items => {
        const at = multi ? "C" + items[0].value[0] : formatContext(items[0].value[0]) + " prompt";
        return "<strong>" + escapeHtml(at) + "</strong><br>" + items.map(item =>
          escapeHtml(item.seriesName) + ": <strong>" + FORMAT.format(item.value[1]) + " " + escapeHtml(config.unit) + "</strong>"
        ).join("<br>");
      }
    },
    xAxis: {
      type: "value", min: multi ? 1 : 0, minInterval: multi ? 1 : undefined,
      name: multi ? "Concurrent users" : "Prompt tokens", nameLocation: "middle", nameGap: 28,
      axisLabel: { color: "#657987", hideOverlap: true, formatter: value => multi ? "C" + value : window.innerWidth < 600 && value >= 1000 ? INTEGER.format(value / 1000) + "k" : formatContext(value) },
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
      lineStyle: { width: long && item.model === state.model ? 3.3 : 2.4 }, emphasis: { focus: "series" },
      data: item.rows.map(row => [multi ? row.users : row.prompt, row[config.key]])
    }))
  });
}

function renderTable(rows) {
  const table = document.getElementById("benchmark-table");
  const head = table.querySelector("thead"), body = table.querySelector("tbody");
  const multi = state.workload === "concurrent", long = state.workload === "long";
  const columns = multi
    ? [["Prompt / user", "prompt"], ["Users", "users"], ["Prefill t/s", "prefillTps"], ["Decode t/s", "decodeTps"], ["Whole-group t/s", "wallTps"], ["Prefill seconds", "prefillSeconds"], ["Decode seconds", "decodeSeconds"]]
    : [...(long ? [["Series", "seriesLabel"]] : []), ["Prompt tokens", "prompt"], ...(long ? [["Chunk tokens", "chunk"]] : []), ["Prefill t/s", "prefillTps"], ["Decode t/s", "decodeTps"], ["Prefill seconds", "prefillSeconds"], ["Decode seconds", "decodeSeconds"]];
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
  renderToolbar();
  const comparisonNote = document.getElementById("comparison-note");
  comparisonNote.hidden = state.workload !== "long";
  const hasMatchedQ2Ud = activeLongSeries.some(series => series.model === "qwen-q2" && series.chunk === 2048) && activeLongSeries.some(series => series.model === "qwen-ud-q4" && series.chunk === 2048);
  comparisonNote.textContent = hasMatchedQ2Ud
    ? "Matched model comparison: Q2 2K and UD-Q4 2K use the same physical prompts and measurement contract. Q2 4K/8K change the chunk size; compare those as a separate diagnostic."
    : "Only series from the same platform and measurement campaign are shown. Different chunk sizes are a separate diagnostic.";
  renderInsights(rows);
  const host = document.getElementById("chart-grid");
  for (const chart of chartInstances) chart.dispose();
  chartInstances = [];
  host.replaceChildren();
  chartConfigurations().forEach((config, index) => drawChart(host, config, rows, index));
  renderTable(rows);
}

function renderMethod(dataset) {
  const list = document.getElementById("dataset-conditions");
  list.replaceChildren(...dataset.conditions.map(value => element("li", "", value)));
  const hasMatchedQ2Ud = dataset.workload === "long" && activeLongSeries.some(series => series.model === "qwen-q2" && series.chunk === 2048) && activeLongSeries.some(series => series.model === "qwen-ud-q4" && series.chunk === 2048);
  document.getElementById("dataset-caveat").textContent = dataset.caveat + (hasMatchedQ2Ud ? " Q2/UD at 2K are matched; Q2 at 4K/8K changes the chunk size." : "");
  const quality = document.getElementById("quality-link");
  quality.hidden = !dataset.quality;
  if (dataset.quality) quality.href = dataset.quality;
}

async function showSelection() {
  const request = ++state.request;
  const dataset = catalog.datasets.find(item => item.platform === state.platform && item.model === state.model && item.workload === state.workload);
  const available = document.getElementById("dataset-available"), empty = document.getElementById("dataset-empty"), status = document.getElementById("benchmark-status");
  if (!dataset) {
    activeDataset = null;
    available.hidden = true;
    empty.hidden = false;
    status.textContent = "No qualified CSV for this selection.";
    const platform = catalog.platforms.find(item => item.id === state.platform);
    const model = catalog.models.find(item => item.id === state.model);
    document.getElementById("empty-description").textContent = model.name + " on " + platform.name + " has no integrated " + state.workload + " measurement yet. We leave the chart empty instead of inventing a number.";
    return;
  }
  available.hidden = true;
  empty.hidden = true;
  status.textContent = "Loading measured CSV…";
  try {
    const rows = normalizedRows(dataset, await readCsv(dataset.csv));
    let longSeries = [];
    if (dataset.workload === "long") {
      const comparable = dataset.comparison_group
        ? catalog.datasets.filter(item => item.workload === "long" && item.platform === dataset.platform && item.format === dataset.format && item.comparison_group === dataset.comparison_group)
        : [dataset];
      const sources = await Promise.all(comparable.map(async item => ({ item, rows: normalizedRows(item, await readCsv(item.csv)) })));
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
          longSeries.push({
            id: source.item.id + ":" + chunk,
            label: (model.chart_name || model.name) + " · " + formatContext(chunk) + " chunk",
            model: source.item.model, chunk, rows: source.rows.filter(row => row.chunk === chunk)
          });
        }
      }
      longSeries.sort((a, b) => a.chunk - b.chunk || a.model.localeCompare(b.model));
      longSeries.forEach((series, index) => { series.color = LONG_COLORS[index % LONG_COLORS.length]; });
    }
    if (request !== state.request) return;
    activeDataset = dataset;
    activeRows = rows;
    activeLongSeries = longSeries;
    state.selectedSeries = longSeries.filter(series => series.chunk === 2048).map(series => series.id);
    if (longSeries.length && !state.selectedSeries.length) state.selectedSeries = [longSeries[0].id];
    const contexts = [...new Set(rows.map(row => row.prompt))];
    state.contexts = state.contexts.filter(value => contexts.includes(value));
    if (!state.contexts.length) state.contexts = contexts;
    document.getElementById("dataset-overline").textContent = state.workload === "long" ? "CONTROLLED FULL-PROMPT TEST" : state.workload === "concurrent" ? "NATIVE BATCH TEST" : "SINGLE REQUEST TEST";
    document.getElementById("dataset-title").textContent = dataset.title;
    document.getElementById("dataset-intro").textContent = dataset.intro;
    document.getElementById("dataset-download").href = dataset.csv;
    renderMethod(dataset);
    available.hidden = false;
    renderDataset();
    status.textContent = rowsForView().length + " measured rows loaded from the source CSV.";
  } catch (error) {
    if (request !== state.request) return;
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
initExplorer();
