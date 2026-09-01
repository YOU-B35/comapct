import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

dotenv.config();

const normalizedRootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export const paths = {
  root: normalizedRootDir,
  data: path.join(normalizedRootDir, "data"),
  uploads: path.join(normalizedRootDir, "data", "uploads"),
  generated: path.join(normalizedRootDir, "data", "generated"),
  results: path.join(normalizedRootDir, "data", "results"),
  fieldMap: path.join(normalizedRootDir, "config", "field-map.json")
};

export function ensureDataDirs() {
  for (const dir of [paths.uploads, paths.generated, paths.results]) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

export function readFieldMap() {
  return JSON.parse(fs.readFileSync(paths.fieldMap, "utf8"));
}

export function appConfig() {
  return {
    port: Number(process.env.PORT || 3000),
    shopify: {
      storeDomain: process.env.SHOPIFY_STORE_DOMAIN || "",
      accessToken: process.env.SHOPIFY_ADMIN_ACCESS_TOKEN || "",
      apiVersion: process.env.SHOPIFY_API_VERSION || "2026-07",
      defaultVendor: process.env.DEFAULT_VENDOR || "",
      defaultStatus: process.env.DEFAULT_PRODUCT_STATUS || "DRAFT",
      defaultInventoryPolicy: process.env.DEFAULT_INVENTORY_POLICY || "DENY",
      defaultOptionName: process.env.DEFAULT_OPTION_NAME || "Style"
    },
    openai: {
      apiKey: process.env.OPENAI_API_KEY || "",
      imageModel: process.env.OPENAI_IMAGE_MODEL || "gpt-image-1",
      imageSize: process.env.OPENAI_IMAGE_SIZE || "1024x1024"
    },
    limits: {
      maxProductsPerRun: Number(process.env.MAX_PRODUCTS_PER_RUN || 20)
    }
  };
}

export function publicConfigStatus() {
  const cfg = appConfig();
  return {
    shopifyStoreDomain: cfg.shopify.storeDomain,
    hasShopifyToken: Boolean(cfg.shopify.accessToken),
    shopifyApiVersion: cfg.shopify.apiVersion,
    hasOpenAIKey: Boolean(cfg.openai.apiKey),
    openaiImageModel: cfg.openai.imageModel,
    maxProductsPerRun: cfg.limits.maxProductsPerRun
  };
}
