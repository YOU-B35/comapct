import fs from "node:fs/promises";
import path from "node:path";
import { paths } from "./config.js";

const MIN_INTERVAL_MS = 5 * 60 * 1000;
const LAST_REFRESH = Symbol("lastTokenRefreshAt");

export function isTokenRefreshConfigured(cfg) {
  return Boolean(cfg?.oauth?.clientId && cfg?.oauth?.clientSecret);
}

async function updateEnvToken(envFile, token) {
  let content;
  try {
    content = await fs.readFile(envFile, "utf8");
  } catch {
    content = "";
  }
  const lines = content.split(/\r?\n/);
  let found = false;
  const updated = lines.map((line) => {
    if (/^SHOPIFY_ADMIN_ACCESS_TOKEN=/.test(line)) {
      found = true;
      return `SHOPIFY_ADMIN_ACCESS_TOKEN=${token}`;
    }
    return line;
  });
  if (!found) updated.push(`SHOPIFY_ADMIN_ACCESS_TOKEN=${token}`);
  await fs.writeFile(envFile, updated.join("\n"), "utf8");
}

export async function refreshAdminToken(cfg, options = {}) {
  const now = options.now ?? Date.now();
  if (!isTokenRefreshConfigured(cfg)) {
    throw new Error("未配置 TOKEN_CLIENT_ID / TOKEN_CLIENT_SECRET，无法自动刷新令牌");
  }
  const last = cfg[LAST_REFRESH] || 0;
  if (last && now - last < MIN_INTERVAL_MS) {
    const waitSeconds = Math.ceil((MIN_INTERVAL_MS - (now - last)) / 1000);
    throw new Error(`令牌刚刚刷新过，${waitSeconds} 秒后再试`);
  }
  const resp = await fetch(`https://${cfg.shopify.storeDomain}/admin/oauth/access_token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: cfg.oauth.clientId,
      client_secret: cfg.oauth.clientSecret
    })
  });
  const text = await resp.text();
  let payload = {};
  try {
    payload = JSON.parse(text);
  } catch {
    payload = {};
  }
  if (!resp.ok || !payload.access_token) {
    throw new Error(`令牌刷新失败：HTTP ${resp.status} ${text.slice(0, 200)}`);
  }
  const token = String(payload.access_token);
  if (!token.startsWith("shpat_")) {
    throw new Error("令牌刷新失败：返回的 access_token 格式异常");
  }
  cfg[LAST_REFRESH] = now;
  cfg.shopify.accessToken = token;
  await updateEnvToken(options.envFile || path.join(paths.root, ".env"), token);
  return token;
}

export async function withTokenRefresh(cfg, requestFn, options = {}) {
  const result = await requestFn(cfg.shopify.accessToken);
  if (result.status === 401 && isTokenRefreshConfigured(cfg)) {
    try {
      await refreshAdminToken(cfg, options);
      return requestFn(cfg.shopify.accessToken);
    } catch {
      return result;
    }
  }
  return result;
}
