// Tests for cloudflare/worker.js. Run: node --test tests/worker.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import worker from "../cloudflare/worker.js";

const SCRIPT = "https://script.google.com/macros/s/abc/exec";

function run(url, env = { APPS_SCRIPT_URL: SCRIPT }) {
  const pings = [];
  const waits = [];
  globalThis.fetch = async (u) => { pings.push(u); return new Response("ok"); };
  const ctx = { waitUntil: (p) => waits.push(p) };
  return worker.fetch(new Request(url), env, ctx).then(async (res) => {
    await Promise.all(waits);
    return { res, pings };
  });
}

// A Workday-style link with its own query string, encoded the way
// pipeline/tracking.py::tracking_link does (quote(..., safe="")).
const JOB = "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Remote/SWE-Intern_R123?source=simplify&a=1";
const TRACKED = `https://apply-redirect.example.workers.dev?link=${encodeURIComponent(JOB)}`;

test("redirects straight to the job posting", async () => {
  const { res } = await run(TRACKED);
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), JOB);
});

test("pings Apps Script in the background to mark Applied", async () => {
  const { pings } = await run(TRACKED);
  assert.equal(pings.length, 1);
  const ping = new URL(pings[0]);
  assert.equal(ping.origin + ping.pathname, SCRIPT);
  assert.equal(ping.searchParams.get("link"), JOB);
  assert.equal(ping.searchParams.get("mode"), "mark");
});

test("still redirects if the Apps Script ping fails", async () => {
  globalThis.fetch = async () => { throw new Error("down"); };
  const waits = [];
  const res = await worker.fetch(new Request(TRACKED), { APPS_SCRIPT_URL: SCRIPT }, { waitUntil: (p) => waits.push(p) });
  await Promise.all(waits); // must not reject
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), JOB);
});

test("redirects without pinging when APPS_SCRIPT_URL is unset", async () => {
  const { res, pings } = await run(TRACKED, {});
  assert.equal(res.status, 302);
  assert.equal(pings.length, 0);
});

test("rejects missing and non-http links", async () => {
  for (const link of ["", "not a url", "javascript:alert(1)", "data:text/html,hi"]) {
    const { res, pings } = await run(`https://w.dev/?link=${encodeURIComponent(link)}`);
    assert.equal(res.status, 400, link);
    assert.equal(pings.length, 0);
  }
});
