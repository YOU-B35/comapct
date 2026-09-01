import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import express from "express";
import multer from "multer";
import { appConfig, ensureDataDirs, paths, publicConfigStatus, readFieldMap } from "./config.js";
import { parseWorkbook } from "./excelParser.js";
import { mapRowsToProducts, summarizeBatch } from "./mapper.js";
import { extractCellImages } from "./cellImages.js";
import { generateProductImages } from "./openaiImages.js";
import { checkShopifyConnection, createShopifyProduct } from "./shopify.js";

ensureDataDirs();

const app = express();
const cfg = appConfig();
const batches = new Map();
const upload = multer({
  dest: paths.uploads,
  limits: { fileSize: 300 * 1024 * 1024 }
});

app.use(express.json({ limit: "5mb" }));
app.use(express.static(path.join(paths.root, "public")));
app.use("/generated", express.static(paths.generated));

app.get("/api/status", (_req, res) => {
  res.json(publicConfigStatus());
});

app.get("/api/shopify/check", async (_req, res, next) => {
  try {
    res.json(await checkShopifyConnection(cfg));
  } catch (error) {
    next(error);
  }
});

app.post("/api/upload", upload.single("file"), async (req, res, next) => {
  try {
    if (!req.file) throw new Error("请上传 xlsx 文件。");
    const fieldMap = readFieldMap();
    const parsed = await parseWorkbook(req.file.path, fieldMap);
    const products = mapRowsToProducts(parsed, fieldMap, {
      vendor: cfg.shopify.defaultVendor,
      status: cfg.shopify.defaultStatus,
      optionName: cfg.shopify.defaultOptionName
    });
    const id = crypto.randomUUID();
    const extractedImages = await extractCellImages(
      req.file.path,
      products,
      path.join(paths.uploads, id)
    );
    const batch = {
      id,
      fileName: req.file.originalname,
      uploadedPath: req.file.path,
      parsed: {
        sheetNames: parsed.sheetNames,
        selectedSheet: parsed.selectedSheet,
        headers: parsed.headers
      },
      extractedImages,
      products,
      summary: summarizeBatch(products),
      createdAt: new Date().toISOString()
    };
    batches.set(id, batch);
    res.json(batch);
  } catch (error) {
    next(error);
  }
});

app.get("/api/batches/:id", (req, res, next) => {
  const batch = batches.get(req.params.id);
  if (!batch) return next(new Error("找不到这个批次，请重新上传 Excel。"));
  res.json(batch);
});

app.post("/api/batches/:id/generate-images", async (req, res, next) => {
  try {
    const batch = batches.get(req.params.id);
    if (!batch) throw new Error("找不到这个批次，请重新上传 Excel。");
    const productIds = Array.isArray(req.body.productIds) ? req.body.productIds : [];
    const selected = productIds.length
      ? batch.products.filter((product) => productIds.includes(product.id))
      : batch.products.slice(0, cfg.limits.maxProductsPerRun);

    const results = [];
    for (const product of selected) {
      if (product.errors.length) {
        results.push({ productId: product.id, title: product.title, skipped: true, errors: product.errors });
        continue;
      }
      const generatedImages = await generateProductImages(product, cfg);
      product.generatedImages = generatedImages.map((image) => ({
        ...image,
        publicUrl: `/generated/${encodeURIComponent(product.handle || product.id)}/${path.basename(image.filePath)}`
      }));
      results.push({ productId: product.id, title: product.title, imageCount: generatedImages.length });
    }
    res.json({ batchId: batch.id, results, products: batch.products });
  } catch (error) {
    next(error);
  }
});

app.post("/api/batches/:id/publish", async (req, res, next) => {
  try {
    const batch = batches.get(req.params.id);
    if (!batch) throw new Error("找不到这个批次，请重新上传 Excel。");
    const productIds = Array.isArray(req.body.productIds) ? req.body.productIds : [];
    const dryRun = Boolean(req.body.dryRun);
    const selected = productIds.length
      ? batch.products.filter((product) => productIds.includes(product.id))
      : batch.products.slice(0, cfg.limits.maxProductsPerRun);

    const results = [];
    for (const product of selected) {
      if (product.errors.length) {
        results.push({ productId: product.id, title: product.title, ok: false, skipped: true, errors: product.errors });
        continue;
      }
      if (dryRun) {
        results.push({
          productId: product.id,
          title: product.title,
          ok: true,
          dryRun: true,
          variants: product.variants.length,
          images: product.generatedImages?.length || product.images.filter((image) => image.usable).length
        });
        continue;
      }
      try {
        const created = await createShopifyProduct(cfg, product, { status: req.body.status });
        product.shopify = created;
        results.push({ productId: product.id, title: product.title, ok: true, shopify: created });
      } catch (error) {
        results.push({ productId: product.id, title: product.title, ok: false, error: error.message });
      }
    }

    const resultPath = path.join(paths.results, `${batch.id}.json`);
    await fs.mkdir(paths.results, { recursive: true });
    await fs.writeFile(resultPath, JSON.stringify({ batchId: batch.id, results }, null, 2), "utf8");

    res.json({ batchId: batch.id, dryRun, results });
  } catch (error) {
    next(error);
  }
});

app.use((error, _req, res, _next) => {
  console.error(error);
  res.status(400).json({ error: error.message || "请求失败" });
});

app.listen(cfg.port, () => {
  console.log(`Shopify bulk uploader running at http://localhost:${cfg.port}`);
});
