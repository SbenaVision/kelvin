#!/usr/bin/env node
/**
 * Kelvin runner for the Envelop Pass 1 harness (Node.js version).
 *
 * Adapter between Kelvin's `run:` contract and the `harness_pass1_prose`
 * endpoint on the venture-assessment edge function. Reads a markdown file,
 * sends its contents as `prose`, extracts `factsheet.delivery_model`, writes
 * a JSON file Kelvin can score.
 *
 * Invocation (matches Kelvin's shell-template substitution):
 *   node harness/kelvin_runner.mjs --input <case.md> --output <out.json> [--variant <label>]
 *
 * Progress goes to stderr so Kelvin's output file stays clean. Errors to
 * stderr with non-zero exit.
 *
 * Requires Node 18+ for the built-in fetch.
 *
 * Exit codes:
 *   0 — wrote output successfully
 *   1 — bad args, missing .env key, file I/O, network, HTTP, or schema error
 */

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import process from "node:process";

const ENDPOINT =
  "https://vlddwuddnbugfqtjxcoi.supabase.co/functions/v1/venture-assessment";

function log(msg) {
  console.error(`kelvin_runner: ${msg}`);
}

function die(msg) {
  console.error(`kelvin_runner: ERROR: ${msg}`);
  process.exit(1);
}

function parseArgs(argv) {
  let input = null;
  let output = null;
  let variant = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--input") input = argv[++i] ?? null;
    else if (a === "--output") output = argv[++i] ?? null;
    else if (a === "--variant") variant = argv[++i] ?? null;
    else die(`unknown arg: ${a}`);
  }
  if (!input) die("missing --input <path>");
  if (!output) die("missing --output <path>");
  return { input, output, variant };
}

function extractEnvKey(envText, name) {
  // Match `NAME=value` or `NAME="value"` on its own line, ignoring comments.
  const re = new RegExp(
    `^[ \\t]*${name}[ \\t]*=[ \\t]*(?:"([^"]*)"|'([^']*)'|([^\\r\\n#]+?))[ \\t]*(?:#.*)?$`,
    "m",
  );
  const m = envText.match(re);
  if (!m) return null;
  return (m[1] ?? m[2] ?? m[3] ?? "").trim() || null;
}

async function main() {
  const { input, output, variant } = parseArgs(process.argv.slice(2));
  log(`input=${input} output=${output} variant=${variant ?? "-"}`);

  // Locate .env at the Envelop root, one level up from this script
  // (harness/kelvin_runner.mjs → ../.env).
  const envPath = fileURLToPath(new URL("../.env", import.meta.url));

  let envText;
  try {
    envText = await readFile(envPath, "utf-8");
  } catch (err) {
    die(`could not read ${envPath}: ${err.message}`);
  }

  const anonKey = extractEnvKey(envText, "SUPABASE_PUBLISHABLE_KEY");
  if (!anonKey) die(`SUPABASE_PUBLISHABLE_KEY not found in ${envPath}`);
  log(`loaded SUPABASE_PUBLISHABLE_KEY (${anonKey.length} chars)`);

  let prose;
  try {
    prose = await readFile(input, "utf-8");
  } catch (err) {
    die(`could not read --input ${input}: ${err.message}`);
  }
  if (prose.trim().length < 20) {
    die(`--input ${input} contains fewer than 20 non-whitespace chars`);
  }
  log(`read prose (${prose.length} chars)`);

  const body = {
    action: "harness_pass1_prose",
    prose,
    variant: variant ?? null,
    venture_name: variant ?? "kelvin-case",
  };

  // Retry on transient upstream 5xx (500/502/503/504) — these surfaced
  // as 2 of 14 failures in the initial Kelvin run and are Supabase/LLM
  // infrastructure noise, not content-dependent bugs. Exponential backoff
  // with jitter; give up after MAX_ATTEMPTS so a truly broken endpoint
  // doesn't hang the Kelvin run.
  const MAX_ATTEMPTS = 3;
  const TRANSIENT_STATUSES = new Set([500, 502, 503, 504]);

  log(`POST ${ENDPOINT}`);
  let resp;
  let rawBody;
  let lastErr;
  for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
    const t0 = Date.now();
    try {
      resp = await fetch(ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "apikey": anonKey,
          "Authorization": `Bearer ${anonKey}`,
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      lastErr = err;
      const elapsed = Date.now() - t0;
      log(`attempt ${attempt}/${MAX_ATTEMPTS} network error in ${elapsed} ms: ${err.message}`);
      if (attempt === MAX_ATTEMPTS) die(`network error after ${MAX_ATTEMPTS} attempts: ${err.message}`);
      const backoffMs = 500 * 2 ** (attempt - 1) + Math.floor(Math.random() * 300);
      log(`  backing off ${backoffMs} ms`);
      await new Promise((r) => setTimeout(r, backoffMs));
      continue;
    }

    const elapsed = Date.now() - t0;
    log(`attempt ${attempt}/${MAX_ATTEMPTS} HTTP ${resp.status} in ${elapsed} ms`);
    rawBody = await resp.text();

    if (resp.ok) break;

    if (TRANSIENT_STATUSES.has(resp.status) && attempt < MAX_ATTEMPTS) {
      const backoffMs = 500 * 2 ** (attempt - 1) + Math.floor(Math.random() * 300);
      log(`  transient ${resp.status}; backing off ${backoffMs} ms`);
      await new Promise((r) => setTimeout(r, backoffMs));
      continue;
    }
    // Non-transient error, or out of attempts — fall through to die below.
    break;
  }

  if (!resp || !resp.ok) {
    die(`HTTP ${resp ? resp.status : "?"} from harness after retries: ${(rawBody || String(lastErr || "")).slice(0, 500)}`);
  }

  let data;
  try {
    data = JSON.parse(rawBody);
  } catch (err) {
    die(`harness response was not valid JSON: ${err.message}`);
  }

  if (data.error) die(`harness returned error: ${data.error}`);

  const factsheet = data.factsheet;
  if (!factsheet || typeof factsheet !== "object") {
    die("harness response missing .factsheet object");
  }

  const deliveryModel = factsheet.delivery_model;
  if (typeof deliveryModel !== "string" || deliveryModel.length === 0) {
    const keys = Object.keys(factsheet).sort().join(", ");
    die(
      `factsheet.delivery_model missing or not a non-empty string; ` +
        `factsheet keys: [${keys}]`,
    );
  }
  log(`delivery_model=${deliveryModel}`);

  const stageAssessment = factsheet.stage_assessment ?? null;
  if (stageAssessment !== null) log(`stage_assessment=${stageAssessment}`);

  const out = {
    delivery_model: deliveryModel,
    stage_assessment: stageAssessment,
    raw: factsheet,
  };

  try {
    await writeFile(output, JSON.stringify(out, null, 2), "utf-8");
  } catch (err) {
    die(`could not write --output ${output}: ${err.message}`);
  }
  log(`wrote ${output}`);
}

await main();
