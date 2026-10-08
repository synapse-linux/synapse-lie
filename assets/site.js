// SPDX-License-Identifier: MIT
"use strict";

const CATALOG_URL = "data/catalog.json";
const SVG_NS = "http://www.w3.org/2000/svg";
const FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const INTEGER = new Intl.NumberFormat("en-US");
const SERIES_COLORS = new Map([[2048, "#1b9f9a"], [4096, "#e88147"], [6144, "#5272d8"], [8192, "#9472d9"]]);
const csvCache = new Map();
const state = { platform: "strix-halo", model: "qwen-q2", workload: "single", chunk: 2048, contexts: [2048, 4096, 6144, 8192], request: 0 };
let catalog = null;
let activeRows = [];
let activeDataset = null;

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
  const longColumns = ["model", "prompt_tokens", "prefill_chunk", "warmup", "repetition", "prefill_tps", "decode_tps", "prefill_seconds", "decode_seconds", "output_tokens"];
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

function svg(tag, attributes) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attributes || {})) node.setAttribute(key, String(value));
  return node;
}

function svgText(content, attributes) {
  const node = svg("text", attributes);
  node.textContent = content;
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
  if (state.workload === "long") return activeRows.filter(row => row.chunk === state.chunk);
  if (state.workload === "concurrent") return activeRows.filter(row => state.contexts.includes(row.prompt));
  return activeRows;
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
    const first = rows[0], last = rows[rows.length - 1];
    target.append(
      makeInsight("2K prompt read", FORMAT.format(first.prefillSeconds) + " s", "before answer generation begins", true),
      makeInsight("2K answer generation", FORMAT.format(first.decodeTps), "output tokens per second"),
      makeInsight("8K prompt read", FORMAT.format(last.prefillSeconds) + " s", "for " + INTEGER.format(last.prompt) + " input tokens")
    );
  } else if (state.workload === "long") {
    const last = rows[rows.length - 1];
    target.append(
      makeInsight(formatContext(last.prompt) + " prompt read", FORMAT.format(last.prefillSeconds) + " s", "full prompt from an empty sequence", true),
      makeInsight("Prompt reading rate", FORMAT.format(last.prefillTps), "input tokens per second at " + formatContext(last.prompt)),
      makeInsight("Answer generation rate", FORMAT.format(last.decodeTps), "output tokens per second at " + formatContext(last.prompt))
    );
  } else {
    const context = Math.min(...state.contexts);
    const subset = rows.filter(row => row.prompt === context);
    const first = subset[0], last = subset[subset.length - 1];
    target.append(
      makeInsight(formatContext(context) + " · C1 decode", FORMAT.format(first.decodeTps), "group output tokens per second"),
      makeInsight(formatContext(context) + " · C" + last.users + " decode", FORMAT.format(last.decodeTps), "native batch output tokens per second", true),
      makeInsight("Whole group at C" + last.users, FORMAT.format(last.wallTps), "output tokens per second including prompt reading")
    );
  }
}

function renderToolbar() {
  const toolbar = document.getElementById("chart-toolbar");
  toolbar.replaceChildren();
  toolbar.hidden = state.workload === "single";
  if (toolbar.hidden) return;
  const heading = element("div", "toolbar-copy");
  heading.append(element("strong", "", state.workload === "long" ? "Prompt chunk" : "Prompt per user"),
    element("span", "", state.workload === "long" ? "Each line is one chunk setting." : "Toggle context lengths to focus the curves."));
  const group = element("div", "toolbar-options");
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", state.workload === "long" ? "Prefill chunk size" : "Prompt length per user");
  const choices = state.workload === "long" ? [...new Set(activeRows.map(row => row.chunk))].sort((a, b) => a - b) : [...new Set(activeRows.map(row => row.prompt))].sort((a, b) => a - b);
  for (const value of choices) {
    const selected = state.workload === "long" ? state.chunk === value : state.contexts.includes(value);
    const button = element("button", "toolbar-option", formatContext(value));
    button.type = "button";
    button.setAttribute("aria-pressed", String(selected));
    button.addEventListener("click", () => {
      if (state.workload === "long") state.chunk = value;
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
  const common = [
    { key: "prefillTps", title: "Prompt reading speed", description: "Input tokens processed per second. The vertical scale is zoomed to reveal changes.", unit: "input tok/s", color: "#1b9f9a", zoom: true },
    { key: "decodeTps", title: "Answer generation speed", description: prompt ? "Output tokens generated per second for one user. Zoomed vertical scale." : "Combined output across the group, not per-user speed.", unit: "output tok/s", color: "#e88147", zoom: prompt }
  ];
  if (prompt) common.splice(1, 0, { key: "prefillSeconds", title: "Time spent reading", description: "Seconds spent processing the complete prompt before generation.", unit: "seconds", color: "#5272d8", zoom: false });
  else common.push({ key: "wallTps", title: "Whole-group output rate", description: "Includes every serialized prompt and all batched generation.", unit: "output tok/s", color: "#5272d8", zoom: false },
    { key: "prefillSeconds", title: "Time spent reading all prompts", description: "The group waits for serialized prompt reading to finish.", unit: "seconds", color: "#9472d9", zoom: false });
  return common;
}

function axisValue(value) {
  return value >= 1000 ? INTEGER.format(Math.round(value)) : value >= 100 ? String(Math.round(value)) : FORMAT.format(value);
}

function drawChart(host, config, rows, index) {
  const article = element("article", "chart-card" + (index === 0 ? " chart-card-wide" : ""));
  const heading = element("div", "chart-heading");
  const title = element("div");
  title.append(element("p", "chart-number", "CHART " + String(index + 1).padStart(2, "0")), element("h4", "", config.title));
  heading.append(title, element("span", "chart-unit", config.unit));
  article.append(heading, element("p", "chart-description", config.description));
  const surface = element("div", "chart-surface");
  const width = 760, height = 310, margin = { left: 68, right: 20, top: 20, bottom: 48 };
  const innerWidth = width - margin.left - margin.right, innerHeight = height - margin.top - margin.bottom;
  const multi = state.workload === "concurrent";
  const xValues = rows.map(row => multi ? row.users : row.prompt);
  const xMin = Math.min(...xValues), xMax = Math.max(...xValues);
  const values = rows.map(row => row[config.key]);
  const low = Math.min(...values), high = Math.max(...values);
  const yMin = config.zoom ? Math.max(0, Math.floor((low - Math.max(2, (high - low) * .16)) / (high > 100 ? 25 : 1)) * (high > 100 ? 25 : 1)) : 0;
  const yMax = Math.max(yMin + 1, high + Math.max(2, (high - yMin) * .08));
  const x = value => margin.left + ((value - xMin) / Math.max(1, xMax - xMin)) * innerWidth;
  const y = value => margin.top + innerHeight * (1 - (value - yMin) / (yMax - yMin));
  const picture = svg("svg", { viewBox: "0 0 " + width + " " + height, role: "group", "aria-label": config.title + " by " + (multi ? "concurrent users" : "prompt length") });
  for (let tick = 0; tick <= 4; tick++) {
    const value = yMin + (yMax - yMin) * tick / 4, py = y(value);
    picture.append(svg("line", { x1: margin.left, x2: width - margin.right, y1: py, y2: py, class: "grid-line" }));
    picture.append(svgText(axisValue(value), { x: margin.left - 10, y: py + 4, "text-anchor": "end", class: "axis-text" }));
  }
  const ticks = multi ? [...new Set(xValues)].sort((a, b) => a - b) : xMax > 16384 ? [xMin, 32768, 65536, 98304, xMax] : [...new Set(xValues)].sort((a, b) => a - b);
  for (const value of ticks) {
    picture.append(svgText(multi ? "C" + value : formatContext(value), { x: x(value), y: height - 23, "text-anchor": "middle", class: "axis-text" }));
  }
  picture.append(svgText(multi ? "CONCURRENT USERS" : "PROMPT TOKENS", { x: margin.left + innerWidth / 2, y: height - 3, "text-anchor": "middle", class: "axis-title" }));
  const tip = element("div", "chart-tooltip");
  tip.hidden = true;
  tip.setAttribute("aria-hidden", "true");
  const series = multi ? [...new Set(rows.map(row => row.prompt))].sort((a, b) => a - b).map(prompt => rows.filter(row => row.prompt === prompt)) : [rows];
  for (const lineRows of series) {
    const sorted = [...lineRows].sort((a, b) => (multi ? a.users - b.users : a.prompt - b.prompt));
    const color = multi ? SERIES_COLORS.get(sorted[0].prompt) : config.color;
    const points = sorted.map((row, point) => (point ? "L" : "M") + x(multi ? row.users : row.prompt).toFixed(2) + "," + y(row[config.key]).toFixed(2)).join(" ");
    picture.append(svg("path", { d: points, stroke: color, class: "series-line" }));
    for (const row of sorted) {
      const readout = formatContext(row.prompt) + " prompt" + (multi ? " · " + row.users + " users" : "") + " · " + FORMAT.format(row[config.key]) + " " + config.unit;
      const circle = svg("circle", { cx: x(multi ? row.users : row.prompt), cy: y(row[config.key]), r: multi ? 5 : 4, fill: color, class: "data-point", tabindex: "0", "aria-label": readout });
      const pointTitle = svg("title", {});
      pointTitle.textContent = readout;
      circle.append(pointTitle);
      const show = () => {
        tip.textContent = readout;
        tip.hidden = false;
        const point = circle.getBoundingClientRect(), bounds = surface.getBoundingClientRect();
        tip.style.left = point.left + point.width / 2 - bounds.left + surface.scrollLeft + "px";
        tip.style.top = point.top - bounds.top + surface.scrollTop - 4 + "px";
      };
      circle.addEventListener("pointerenter", show);
      circle.addEventListener("focus", show);
      circle.addEventListener("pointerleave", () => { tip.hidden = true; });
      circle.addEventListener("blur", () => { tip.hidden = true; });
      picture.append(circle);
    }
  }
  surface.append(picture, tip);
  if (multi) {
    const legend = element("div", "chart-legend");
    for (const lineRows of series) {
      const prompt = lineRows[0].prompt, item = element("span", "legend-item", formatContext(prompt) + " prompt");
      item.style.setProperty("--legend-color", SERIES_COLORS.get(prompt));
      legend.append(item);
    }
    surface.append(legend);
  }
  article.append(surface);
  host.append(article);
}

function renderTable(rows) {
  const table = document.getElementById("benchmark-table");
  const head = table.querySelector("thead"), body = table.querySelector("tbody");
  const multi = state.workload === "concurrent", long = state.workload === "long";
  const columns = multi
    ? [["Prompt / user", "prompt"], ["Users", "users"], ["Prefill tok/s", "prefillTps"], ["Decode tok/s", "decodeTps"], ["Whole-group tok/s", "wallTps"], ["Prompt time", "prefillSeconds"], ["Decode time", "decodeSeconds"]]
    : [["Prompt tokens", "prompt"], ...(long ? [["Chunk tokens", "chunk"]] : []), ["Prefill tok/s", "prefillTps"], ["Prompt time", "prefillSeconds"], ["Decode tok/s", "decodeTps"], ["Decode time", "decodeSeconds"]];
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
      const value = ["prompt", "users", "chunk"].includes(field) ? INTEGER.format(row[field]) : FORMAT.format(row[field]) + (field.endsWith("Seconds") ? " s" : "");
      record.append(element("td", "", value));
    }
    body.append(record);
  }
  document.getElementById("benchmark-caption").textContent = rows.length + " measured rows for the selected model, workload and filters. Rates are tokens per second.";
}

function renderDataset() {
  const rows = rowsForView();
  renderToolbar();
  renderInsights(rows);
  const host = document.getElementById("chart-grid");
  host.replaceChildren();
  chartConfigurations().forEach((config, index) => drawChart(host, config, rows, index));
  renderTable(rows);
}

function renderMethod(dataset) {
  const list = document.getElementById("dataset-conditions");
  list.replaceChildren(...dataset.conditions.map(value => element("li", "", value)));
  document.getElementById("dataset-caveat").textContent = dataset.caveat;
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
    if (request !== state.request) return;
    activeDataset = dataset;
    activeRows = rows;
    const chunks = [...new Set(rows.map(row => row.chunk))];
    if (!chunks.includes(state.chunk)) state.chunk = chunks[0];
    const contexts = [...new Set(rows.map(row => row.prompt))];
    state.contexts = state.contexts.filter(value => contexts.includes(value));
    if (!state.contexts.length) state.contexts = contexts;
    document.getElementById("dataset-overline").textContent = state.workload === "long" ? "CONTROLLED FULL-PROMPT TEST" : state.workload === "concurrent" ? "NATIVE BATCH TEST" : "SINGLE REQUEST TEST";
    document.getElementById("dataset-title").textContent = dataset.title;
    document.getElementById("dataset-intro").textContent = dataset.intro;
    document.getElementById("dataset-download").href = dataset.csv;
    renderMethod(dataset);
    renderDataset();
    available.hidden = false;
    status.textContent = rows.length + " measured rows loaded from the source CSV.";
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
  try {
    const response = await fetch(CATALOG_URL);
    if (!response.ok) throw new Error("Catalog returned HTTP " + response.status + ".");
    catalog = validateCatalog(await response.json());
    renderOptions();
    const core = await readCsv("data/q2-core-model-flow-2k8k.csv");
    const example = normalizedRows(catalog.datasets.find(item => item.id === "q2-promessi-single"), core).find(row => row.prompt === 2048);
    document.querySelector("[data-hero='prefill']").textContent = FORMAT.format(example.prefillSeconds) + " s";
    document.querySelector("[data-hero='decode']").textContent = FORMAT.format(example.decodeSeconds) + " s";
    await showSelection();
  } catch (error) {
    status.classList.add("error");
    status.textContent = "Could not load the benchmark explorer: " + error.message;
  }
}

initInstallTabs();
initCopyButtons();
initExplorer();
