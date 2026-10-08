// SPDX-License-Identifier: MIT
// Pi client integration. The LIE server remains an ordinary OpenAI HTTP endpoint.
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const timeoutMs = 10000;
const maxCatalogBytes = 1024 * 1024;

function endpoint(raw: unknown): { provider: string; baseUrl: string } {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("Pi LIE endpoint must be an object");
  const item = raw as Record<string, unknown>;
  if (typeof item.provider !== "string" || !/^[a-z][a-z0-9-]*$/.test(item.provider)) {
    throw new Error("Pi LIE provider must contain lowercase letters, digits or hyphens");
  }
  if (typeof item.baseUrl !== "string") throw new Error(`Pi LIE ${item.provider}: baseUrl is required`);
  const url = new URL(item.baseUrl);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash ||
      !/^\/v1\/?$/.test(url.pathname)) {
    throw new Error(`Pi LIE ${item.provider}: baseUrl must be an HTTP(S) origin ending in /v1`);
  }
  return { provider: item.provider, baseUrl: `${url.origin}/v1` };
}

async function discover(baseUrl: string, signal?: AbortSignal) {
  const timeout = AbortSignal.timeout(timeoutMs);
  const response = await fetch(`${baseUrl}/models`, {
    headers: { Accept: "application/json" },
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Pi LIE ${baseUrl}/models: HTTP ${response.status}`);
  const body = await response.text();
  if (body.length > maxCatalogBytes) throw new Error(`Pi LIE ${baseUrl}/models: catalog too large`);
  const catalog = JSON.parse(body);
  if (!catalog || !Array.isArray(catalog.data) || !catalog.data.length || catalog.data.length > 256) {
    throw new Error(`Pi LIE ${baseUrl}/models: invalid catalog`);
  }
  const seen = new Set<string>();
  return catalog.data.map((item: any) => {
    if (!item || typeof item.id !== "string" || !item.id || seen.has(item.id) ||
        !Number.isSafeInteger(item.context_length) || item.context_length <= 0 ||
        !Number.isSafeInteger(item.max_output_tokens) || item.max_output_tokens <= 0) {
      throw new Error(`Pi LIE ${baseUrl}/models: invalid or duplicate model entry`);
    }
    seen.add(item.id);
    return {
      id: item.id,
      name: item.id,
      input: ["text"],
      reasoning: false,
      contextWindow: item.context_length,
      maxTokens: Math.min(item.max_output_tokens, item.context_length),
      inputLimits: { maxRequestBytes: 8388608 },
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      compat: { maxTokensField: "max_tokens", supportsReasoningEffort: false, supportsStrictMode: false },
    };
  });
}

export default async function (pi: any) {
  const agentDir = process.env.PI_CODING_AGENT_DIR;
  if (!agentDir) throw new Error("Set PI_CODING_AGENT_DIR to the private Pi profile directory");
  const configPath = process.env.PI_LIE_ENDPOINTS_FILE || join(agentDir, "lie-endpoints.json");
  const config = JSON.parse(await readFile(configPath, "utf8"));
  if (!config || !Array.isArray(config.endpoints) || !config.endpoints.length) {
    throw new Error("Pi LIE endpoints file must contain a nonempty endpoints array");
  }
  const entries = config.endpoints.map(endpoint);
  if (new Set(entries.map((entry: { provider: string }) => entry.provider)).size !== entries.length) {
    throw new Error("Pi LIE provider aliases must be unique");
  }
  for (const entry of entries) {
    pi.registerProvider(entry.provider, {
      name: entry.provider,
      baseUrl: entry.baseUrl,
      api: "openai-completions",
      apiKey: "local-development-not-a-secret",
      authHeader: false,
      models: await discover(entry.baseUrl),
      refreshModels: (context: { signal: AbortSignal }) => discover(entry.baseUrl, context.signal),
    });
  }
}
