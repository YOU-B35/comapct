import test from "node:test";
import assert from "node:assert/strict";
import os from "node:os";
import path from "node:path";
import fs from "node:fs/promises";
import {
  refreshAdminToken,
  isTokenRefreshConfigured,
  withTokenRefresh
} from "../src/tokenRefresh.js";

async function tempEnv(initial = "SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_old\nPORT=3001\n") {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "tok-"));
  const envFile = path.join(dir, ".env");
  await fs.writeFile(envFile, initial, "utf8");
  return { dir, envFile };
}

function cfg(oauth = { clientId: "cid", clientSecret: "cs" }) {
  return {
    shopify: { storeDomain: "s.myshopify.com", accessToken: "shpat_old" },
    oauth
  };
}

test("refreshAdminToken 换新令牌并更新 cfg 与 .env", async () => {
  const { dir, envFile } = await tempEnv();
  const calls = [];
  globalThis.fetch = async (url, opts) => {
    calls.push({ url, body: String(opts?.body || "") });
    return new Response(JSON.stringify({ access_token: "shpat_new123", scope: "write_products" }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };
  const token = await refreshAdminToken(cfg(), { envFile, now: 1 });
  assert.equal(token, "shpat_new123");
  assert.equal(calls[0].url.includes("/admin/oauth/access_token"), true);
  assert.ok(calls[0].body.includes("grant_type=client_credentials"));
  const env = await fs.readFile(envFile, "utf8");
  assert.match(env, /^SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_new123$/m);
  assert.match(env, /PORT=3001/);
  delete globalThis.fetch;
  await fs.rm(dir, { recursive: true, force: true });
});

test("5 分钟内重复刷新被拒绝", async () => {
  const { dir, envFile } = await tempEnv();
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ access_token: "shpat_x" }), { status: 200 });
  const c = cfg();
  await refreshAdminToken(c, { envFile, now: 1000 });
  await assert.rejects(() => refreshAdminToken(c, { envFile, now: 2000 }), /刷新过/);
  delete globalThis.fetch;
  await fs.rm(dir, { recursive: true, force: true });
});

test("刷新失败抛出可读错误且不更新 .env", async () => {
  const { dir, envFile } = await tempEnv();
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ error: "invalid_grant" }), { status: 400 });
  await assert.rejects(() => refreshAdminToken(cfg(), { envFile, now: 300000 }), /刷新失败/);
  const env = await fs.readFile(envFile, "utf8");
  assert.match(env, /SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_old/);
  delete globalThis.fetch;
  await fs.rm(dir, { recursive: true, force: true });
});

test("isTokenRefreshConfigured 仅在配置完整时为真", () => {
  assert.equal(isTokenRefreshConfigured(cfg()), true);
  assert.equal(isTokenRefreshConfigured(cfg({})), false);
  assert.equal(isTokenRefreshConfigured({}), false);
});

test("withTokenRefresh 在 401 时刷新令牌并重试一次", async () => {
  const { dir, envFile } = await tempEnv();
  const tokensUsed = [];
  let oauthCalls = 0;
  globalThis.fetch = async (url, opts = {}) => {
    if (String(opts.body || "").includes("grant_type")) {
      oauthCalls += 1;
      return new Response(JSON.stringify({ access_token: "shpat_new123" }), { status: 200 });
    }
    tokensUsed.push(opts.headers["X-Shopify-Access-Token"]);
    return tokensUsed.length === 1
      ? new Response(JSON.stringify({ errors: "Invalid API key" }), { status: 401 })
      : new Response(JSON.stringify({ ok: true }), { status: 200 });
  };
  const requestFn = (token) =>
    fetch("https://s.myshopify.com/x", { headers: { "X-Shopify-Access-Token": token } });
  const result = await withTokenRefresh(cfg(), requestFn, { envFile, now: 100 });
  assert.equal(result.status, 200);
  assert.deepEqual(tokensUsed, ["shpat_old", "shpat_new123"]);
  assert.equal(oauthCalls, 1);
  delete globalThis.fetch;
  await fs.rm(dir, { recursive: true, force: true });
});

test("withTokenRefresh 未配置时不刷新并返回原 401", async () => {
  let oauthCalls = 0;
  globalThis.fetch = async (url, opts = {}) => {
    if (String(opts.body || "").includes("grant_type")) {
      oauthCalls += 1;
      return new Response(JSON.stringify({ access_token: "shpat_x" }), { status: 200 });
    }
    return new Response(JSON.stringify({ errors: "Invalid API key" }), { status: 401 });
  };
  const requestFn = (token) =>
    fetch("https://s.myshopify.com/x", { headers: { "X-Shopify-Access-Token": token } });
  const result = await withTokenRefresh(cfg({}), requestFn);
  assert.equal(result.status, 401);
  assert.equal(oauthCalls, 0);
  delete globalThis.fetch;
});
