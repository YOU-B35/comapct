function text(value) {
  return value === undefined || value === null ? "" : String(value).trim();
}

function money(value) {
  const cleaned = text(value).replace(/[^\d.-]/g, "");
  if (!cleaned) return "";
  const n = Number(cleaned);
  return Number.isFinite(n) ? n.toFixed(2) : "";
}

function isFormulaImage(value) {
  return /^=DISPIMG\(/i.test(text(value));
}

function looksLikeUsableImage(value) {
  const v = text(value);
  return /^https?:\/\//i.test(v) || /^[a-zA-Z]:[\\/]/.test(v) || v.startsWith("\\\\");
}

function slugify(input) {
  return text(input)
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function unique(values) {
  return [...new Set(values.map(text).filter(Boolean))];
}

function buildHtmlDescription(parent, columns) {
  const blocks = [];
  const description = text(parent[columns.description]);
  if (description) {
    blocks.push(
      ...description
        .split(/\n{2,}/)
        .map((part) => `<p>${escapeHtml(part).replace(/\n/g, "<br>")}</p>`)
    );
  }

  for (const col of columns.detailDescriptions || []) {
    const value = text(parent[col]);
    if (value) blocks.push(`<p>${escapeHtml(value).replace(/\n/g, "<br>")}</p>`);
  }

  return blocks.join("\n");
}

function escapeHtml(input) {
  return text(input)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function makeSku(row, columns) {
  const internal = text(row[columns.internalSku]);
  const variant = text(row[columns.variantTitle]);
  if (internal && variant) return `${internal}-${variant}`.replace(/\s+/g, "-");
  return internal || variant || "";
}

function ensureUniqueVariantTitles(variants) {
  const counts = new Map();
  for (const variant of variants) {
    counts.set(variant.title, (counts.get(variant.title) || 0) + 1);
  }
  const duplicated = new Set(
    [...counts].filter(([, count]) => count > 1).map(([title]) => title)
  );
  if (!duplicated.size) return variants;

  const used = new Map();
  for (const variant of variants) {
    if (!duplicated.has(variant.title)) {
      used.set(variant.title, true);
      continue;
    }
    const suffix =
      String(variant.internalSku || "")
        .split("-")
        .filter(Boolean)
        .pop() || "";
    let candidate = suffix ? `${variant.title} ${suffix}` : variant.title;
    let attempt = 2;
    while (used.has(candidate)) {
      candidate = suffix ? `${variant.title} ${suffix} ${attempt}` : `${variant.title} ${attempt}`;
      attempt += 1;
    }
    variant.title = candidate;
    used.set(candidate, true);
  }
  return variants;
}

function rowIsParent(row, columns) {
  return text(row[columns.rowType]).includes(columns.parentValue || "父体");
}

function rowIsVariant(row, columns) {
  return text(row[columns.rowType]).includes(columns.variantValue || "子体");
}

function collectImages(row, columns) {
  return (columns.productImages || []).map((col, index) => {
    const raw = text(row[col]);
    return {
      index: index + 1,
      column: col,
      raw,
      usable: looksLikeUsableImage(raw),
      generated: false,
      warning: isFormulaImage(raw)
        ? "检测到 WPS/表格内嵌图片公式，Node 工具无法直接读取图片文件；可用 AI 生成或填写图片 URL/本地路径。"
        : ""
    };
  });
}

export function mapRowsToProducts(parsed, fieldMap, defaults = {}) {
  const columns = fieldMap.columns;
  const groups = new Map();

  for (const row of parsed.rows) {
    const key = text(row[columns.groupKey]) || `row-${row.__rowNumber}`;
    if (!groups.has(key)) groups.set(key, { key, parent: null, variants: [], rowNumbers: [] });
    const group = groups.get(key);
    group.rowNumbers.push(row.__rowNumber);
    if (rowIsParent(row, columns)) group.parent = row;
    if (rowIsVariant(row, columns)) group.variants.push(row);
  }

  const products = [];
  for (const group of groups.values()) {
    const parent = group.parent || group.variants[0] || {};
    const title = text(parent[columns.title]);
    const variants = group.variants.length
      ? group.variants.map((row, index) => ({
          rowNumber: row.__rowNumber,
          title: text(row[columns.variantTitle]) || `Option ${index + 1}`,
          sku: makeSku(row, columns),
          internalSku: text(row[columns.internalSku]),
          price: money(row[columns.price]),
          sourcePrice: text(row[columns.price]),
          skuImage: text(row[columns.mainSkuImage])
        }))
      : [
          {
            rowNumber: parent.__rowNumber,
            title: "Default",
            sku: makeSku(parent, columns),
            internalSku: text(parent[columns.internalSku]),
            price: money(parent[columns.price]),
            sourcePrice: text(parent[columns.price]),
            skuImage: text(parent[columns.mainSkuImage])
          }
        ];
    ensureUniqueVariantTitles(variants);

    const collections = unique((columns.collections || []).map((col) => parent[col]));
    const images = collectImages(parent, columns);
    const warnings = [];
    const errors = [];

    if (!title) errors.push("父体行缺少产品标题");
    if (!variants.length) errors.push("没有找到子体/变体行");
    for (const variant of variants) {
      if (!variant.price) errors.push(`第 ${variant.rowNumber} 行价格无效`);
      if (!variant.sku) warnings.push(`第 ${variant.rowNumber} 行没有 SKU，Shopify 将难以追踪库存/订单`);
    }
    if (images.some((image) => image.warning)) {
      warnings.push("产品图片列包含内嵌图片公式，无法直接上传；建议勾选 AI 生图，或把图片列改为公开 URL/本地文件路径。");
    }

    products.push({
      id: String(group.key),
      sourceRows: group.rowNumbers,
      title,
      handle: slugify(title) || `product-${group.key}`,
      descriptionHtml: buildHtmlDescription(parent, columns),
      productType: text(parent[columns.productType]),
      collections,
      vendor: defaults.vendor || "",
      status: defaults.status || "DRAFT",
      optionName: defaults.optionName || "Style",
      variants,
      images,
      imagePromptBase: `${title}. ${text(parent[columns.description]).slice(0, 600)}`,
      errors,
      warnings
    });
  }

  return products;
}

export function summarizeBatch(products) {
  return {
    productCount: products.length,
    variantCount: products.reduce((sum, product) => sum + product.variants.length, 0),
    errorCount: products.reduce((sum, product) => sum + product.errors.length, 0),
    warningCount: products.reduce((sum, product) => sum + product.warnings.length, 0)
  };
}
