// SPDX-License-Identifier: MIT
"use strict";

const DATA_URL = "data/q2-core-model-flow-2k8k.csv";
const NUMBER_COLUMNS = ["tokens", "users", "prefill_tps", "decode_tps", "wall_output_tps", "prefill_seconds", "decode_seconds", "wall_seconds"];
const REQUIRED_COLUMNS = [...NUMBER_COLUMNS, "decode_batches", "decode_batch_rows", "decode_single_calls", "physical_ids_sha256", "result_sha256"];
const COLORS = new Map([[2048, "#1b9f9a"], [4096, "#e88147"], [6144, "#5272d8"], [8192, "#9472d9"]]);
const FORMAT = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const FORMAT_INT = new Intl.NumberFormat("en-US");
const SVG_NS = "http://www.w3.org/2000/svg";
let benchmarkRows = [];

function parseBenchmarkCsv(csv) {
  const lines = csv.trim().split(/\r?\n/);
  if (lines.length < 2) throw new Error("The benchmark CSV contains no data rows.");
  const headers = lines.shift().split(",");
  if (REQUIRED_COLUMNS.some(column => !headers.includes(column))) throw new Error("The benchmark CSV schema is incomplete.");
  const seen = new Set();
  return lines.map((line, index) => {
    const cells = line.split(",");
    if (cells.length !== headers.length) throw new Error(`Invalid CSV row ${index + 2}.`);
    const row = Object.fromEntries(headers.map((key, i) => [key, cells[i]]));
    for (const column of NUMBER_COLUMNS) {
      row[column] = Number(row[column]);
      if (!Number.isFinite(row[column]) || row[column] <= 0) throw new Error(`Invalid ${column} in CSV row ${index + 2}.`);
    }
    if (!Number.isInteger(row.tokens) || !Number.isInteger(row.users)) throw new Error(`Invalid token or user count in CSV row ${index + 2}.`);
    const key = `${row.tokens}:${row.users}`;
    if (seen.has(key)) throw new Error(`Duplicate benchmark arm ${key}.`);
    seen.add(key);
    return row;
  }).sort((a, b) => a.tokens - b.tokens || a.users - b.users);
}

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, String(value));
  return node;
}

function textElement(tag, content, attributes = {}) {
  const node = svgElement(tag, attributes);
  node.textContent = content;
  return node;
}

function selectedContexts() {
  return [...document.querySelectorAll(".context-filter[aria-pressed='true']")].map(button => Number(button.dataset.context));
}

function updateHighlights(rows) {
  const find = (tokens, users, key) => rows.find(row => row.tokens === tokens && row.users === users)?.[key];
  for (const [metric, value] of Object.entries({
    prefill: find(2048, 1, "prefill_tps"),
    decode: find(2048, 8, "decode_tps"),
    wall: find(8192, 8, "wall_output_tps")
  })) {
    const target = document.querySelector(`[data-metric='${metric}']`);
    target.textContent = value === undefined ? "—" : FORMAT.format(value);
  }
}

function renderChart(surface, rows, metric) {
  surface.replaceChildren();
  const selected = selectedContexts();
  const visible = rows.filter(row => selected.includes(row.tokens));
  const users = [...new Set(rows.map(row => row.users))].sort((a, b) => a - b);
  const values = visible.map(row => row[metric]);
  if (!users.length || !values.length) return;

  const width = 760, height = 305;
  const margin = { top: 15, right: 20, bottom: 43, left: 65 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const minimum = Math.min(...values), maximum = Math.max(...values);
  const yMin = metric === "prefill_tps" ? Math.max(0, Math.floor((minimum - 35) / 50) * 50) : 0;
  const yMax = metric === "prefill_tps" ? Math.ceil((maximum + 35) / 50) * 50 : Math.ceil(maximum / 10) * 10 + 10;
  const x = user => margin.left + (users.indexOf(user) / Math.max(1, users.length - 1)) * plotWidth;
  const y = value => margin.top + plotHeight * (1 - (value - yMin) / (yMax - yMin));
  const svg = svgElement("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": `${surface.closest(".chart-card").querySelector("h3").textContent} by user count and context length` });

  for (let i = 0; i <= 4; i++) {
    const value = yMin + (yMax - yMin) * i / 4;
    const py = y(value);
    svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: py, y2: py, class: "grid-line" }));
    svg.append(textElement("text", FORMAT_INT.format(Math.round(value)), { x: margin.left - 12, y: py + 4, "text-anchor": "end", class: "axis-text" }));
  }
  svg.append(svgElement("line", { x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: "axis-line" }));
  for (const user of users) {
    svg.append(textElement("text", `C${user}`, { x: x(user), y: height - margin.bottom + 21, "text-anchor": "middle", class: "axis-text" }));
  }
  svg.append(textElement("text", "CONCURRENT USERS", { x: margin.left + plotWidth / 2, y: height - 3, "text-anchor": "middle", class: "axis-title" }));
  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  tooltip.hidden = true;
  tooltip.setAttribute("aria-hidden", "true");

  for (const context of selected) {
    const points = visible.filter(row => row.tokens === context).sort((a, b) => a.users - b.users);
    if (!points.length) continue;
    const color = COLORS.get(context) || "#506371";
    const path = points.map((row, index) => `${index ? "L" : "M"}${x(row.users).toFixed(2)},${y(row[metric]).toFixed(2)}`).join(" ");
    svg.append(svgElement("path", { d: path, stroke: color, class: "series-line" }));
    for (const row of points) {
      const label = `${FORMAT_INT.format(row.tokens)} prompt tokens, C${row.users}: ${FORMAT.format(row[metric])} tokens per second`;
      const circle = svgElement("circle", { cx: x(row.users), cy: y(row[metric]), r: 5.2, fill: color, class: "data-point", tabindex: "0", "aria-label": label });
      circle.append(textElement("title", label));
      const show = () => {
        tooltip.textContent = `${FORMAT_INT.format(row.tokens)} tokens · C${row.users} · ${FORMAT.format(row[metric])} tok/s`;
        tooltip.hidden = false;
        const pointBounds = circle.getBoundingClientRect();
        const surfaceBounds = surface.getBoundingClientRect();
        tooltip.style.left = `${pointBounds.left + pointBounds.width / 2 - surfaceBounds.left + surface.scrollLeft}px`;
        tooltip.style.top = `${pointBounds.top - surfaceBounds.top + surface.scrollTop - 4}px`;
      };
      circle.addEventListener("pointerenter", show);
      circle.addEventListener("focus", show);
      circle.addEventListener("pointerleave", () => { tooltip.hidden = true; });
      circle.addEventListener("blur", () => { tooltip.hidden = true; });
      svg.append(circle);
    }
  }
  surface.append(svg, tooltip);
  const legend = document.createElement("div");
  legend.className = "chart-legend";
  legend.setAttribute("aria-hidden", "true");
  for (const context of selected) {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("i");
    swatch.style.background = COLORS.get(context) || "#506371";
    item.append(swatch, document.createTextNode(`${context / 1024}K`));
    legend.append(item);
  }
  surface.append(legend);
}

function renderTable(rows) {
  const body = document.querySelector("#benchmark-table tbody");
  body.replaceChildren();
  for (const row of rows.filter(item => selectedContexts().includes(item.tokens))) {
    const tr = document.createElement("tr");
    for (const value of [FORMAT_INT.format(row.tokens), `C${row.users}`, FORMAT.format(row.prefill_tps), FORMAT.format(row.decode_tps), FORMAT.format(row.wall_output_tps), `${FORMAT.format(row.prefill_seconds)} s`, `${FORMAT.format(row.decode_seconds)} s`]) {
      const td = document.createElement("td");
      td.textContent = value;
      tr.append(td);
    }
    body.append(tr);
  }
}

function renderData() {
  for (const surface of document.querySelectorAll("[data-chart]")) renderChart(surface, benchmarkRows, surface.dataset.chart);
  renderTable(benchmarkRows);
}

function initFilters() {
  for (const button of document.querySelectorAll(".context-filter")) {
    button.addEventListener("click", () => {
      const isSelected = button.getAttribute("aria-pressed") === "true";
      if (isSelected && selectedContexts().length === 1) return;
      button.setAttribute("aria-pressed", String(!isSelected));
      if (benchmarkRows.length) renderData();
    });
  }
}

function initTabs() {
  const tabs = [...document.querySelectorAll("[role='tab'][data-distro]")];
  function activate(tab) {
    for (const candidate of tabs) {
      const active = candidate === tab;
      candidate.setAttribute("aria-selected", String(active));
      candidate.tabIndex = active ? 0 : -1;
      document.getElementById(candidate.getAttribute("aria-controls")).hidden = !active;
    }
  }
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
  if (navigator.clipboard?.writeText) {
    try { await navigator.clipboard.writeText(value); return; } catch { /* Fall back below. */ }
  }
  const input = document.createElement("textarea");
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
      const code = button.closest(".code-block").querySelector("code").textContent;
      try {
        await copyText(code);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Select text";
      }
      setTimeout(() => { button.textContent = "Copy"; }, 2200);
    });
  }
}

async function loadBenchmark() {
  const status = document.getElementById("load-status");
  try {
    const response = await fetch(DATA_URL);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    benchmarkRows = parseBenchmarkCsv(await response.text());
    updateHighlights(benchmarkRows);
    renderData();
    document.getElementById("chart-grid").hidden = false;
    status.textContent = `${benchmarkRows.length} measured arms loaded from the linked CSV. Hover or focus a point to inspect it.`;
  } catch (error) {
    status.classList.add("error");
    status.textContent = `Could not load benchmark data (${error.message}). Open the site through HTTP or download the CSV directly.`;
  }
}

initFilters();
initTabs();
initCopyButtons();
loadBenchmark();
