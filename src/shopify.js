import fs from "node:fs/promises";
import path from "node:path";
import mime from "mime-types";
import { withTokenRefresh } from "./tokenRefresh.js";

function assertShopifyConfig(cfg) {
  if (!cfg.shopify.storeDomain) throw new Error("缺少 SHOPIFY_STORE_DOMAIN。");
  if (!cfg.shopify.accessToken) throw new Error("缺少 SHOPIFY_ADMIN_ACCESS_TOKEN。");
}

async function graphql(cfg, query, variables = {}) {
  assertShopifyConfig(cfg);
  const url = `https://${cfg.shopify.storeDomain}/admin/api/${cfg.shopify.apiVersion}/graphql.json`;
  const response = await withTokenRefresh(cfg, (token) =>
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token
      },
      body: JSON.stringify({ query, variables })
    })
  );

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.errors) {
    throw new Error(JSON.stringify(payload.errors || payload, null, 2));
  }
  return payload.data;
}

function remoteImageSource(image) {
  const raw = image?.url || image?.filePath || image?.raw || "";
  if (/^https?:\/\//i.test(raw)) return raw;
  return "";
}

async function uploadLocalImage(cfg, filePath) {
  const filename = path.basename(filePath);
  const mimeType = mime.lookup(filePath) || "image/png";
  const size = (await fs.stat(filePath)).size.toString();

  const staged = await graphql(
    cfg,
    `mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
      stagedUploadsCreate(input: $input) {
        stagedTargets {
          url
          resourceUrl
          parameters { name value }
        }
        userErrors { field message }
      }
    }`,
    {
      input: [
        {
          filename,
          mimeType,
          resource: "IMAGE",
          fileSize: size,
          httpMethod: "POST"
        }
      ]
    }
  );

  const errors = staged.stagedUploadsCreate?.userErrors || [];
  if (errors.length) throw new Error(`Shopify staged upload 失败：${errors.map((e) => e.message).join("; ")}`);

  const target = staged.stagedUploadsCreate.stagedTargets[0];
  const form = new FormData();
  for (const parameter of target.parameters) {
    form.append(parameter.name, parameter.value);
  }
  const bytes = await fs.readFile(filePath);
  form.append("file", new Blob([bytes], { type: mimeType }), filename);

  const upload = await fetch(target.url, { method: "POST", body: form });
  if (!upload.ok) {
    throw new Error(`图片上传到 Shopify 存储失败：HTTP ${upload.status} ${await upload.text()}`);
  }

  return target.resourceUrl;
}

async function imageSourcesForProduct(cfg, product) {
  const sources = [];
  const images = product.generatedImages?.length ? product.generatedImages : product.images || [];
  let index = 0;
  for (const image of images) {
    const remote = remoteImageSource(image);
    if (remote) {
      index += 1;
      sources.push({ source: remote, alt: `${product.title} image ${index}` });
      continue;
    }
    const filePath = image?.filePath || image?.raw;
    if (filePath && /^[a-zA-Z]:[\\/]|^\\\\/.test(filePath)) {
      index += 1;
      sources.push({ source: await uploadLocalImage(cfg, filePath), alt: `${product.title} image ${index}` });
    }
  }
  for (const variant of product.variants || []) {
    const raw = variant.skuImageFilePath || variant.skuImage || "";
    if (!raw) continue;
    let source = "";
    if (/^https?:\/\//i.test(raw)) {
      source = raw;
    } else if (/^[a-zA-Z]:[\\/]|^\\\\/.test(raw)) {
      source = await uploadLocalImage(cfg, raw);
    }
    if (source) {
      sources.push({ source, alt: `${product.title} - ${variant.title || "SKU"}` });
    }
  }
  return sources;
}

export async function createShopifyProduct(cfg, product, options = {}) {
  const imageSources = await imageSourcesForProduct(cfg, product);
  const optionValues = product.variants.map((variant) => ({ name: variant.title }));
  const productInput = {
    title: product.title,
    handle: product.handle,
    descriptionHtml: product.descriptionHtml || "",
    productType: product.productType || undefined,
    vendor: product.vendor || cfg.shopify.defaultVendor || undefined,
    tags: product.collections || [],
    status: options.status || product.status || cfg.shopify.defaultStatus || "DRAFT",
    productOptions: [
      {
        name: product.optionName || cfg.shopify.defaultOptionName || "Style",
        values: optionValues
      }
    ]
  };

  const media = imageSources.map((item) => ({
    originalSource: item.source,
    alt: item.alt,
    mediaContentType: "IMAGE"
  }));

  const created = await graphql(
    cfg,
    `mutation productCreate($product: ProductCreateInput!, $media: [CreateMediaInput!]) {
      productCreate(product: $product, media: $media) {
        product {
          id
          title
          handle
        }
        userErrors { field message }
      }
    }`,
    { product: productInput, media }
  );

  const createErrors = created.productCreate?.userErrors || [];
  if (createErrors.length) throw new Error(`Shopify 创建商品失败：${createErrors.map((e) => e.message).join("; ")}`);

  const shopifyProduct = created.productCreate.product;
  const variants = product.variants.map((variant) => ({
    price: variant.price,
    inventoryPolicy: cfg.shopify.defaultInventoryPolicy || "DENY",
    inventoryItem: {
      sku: variant.sku,
      tracked: false
    },
    optionValues: [
      {
        optionName: product.optionName || cfg.shopify.defaultOptionName || "Style",
        name: variant.title
      }
    ]
  }));

  const variantsResult = await graphql(
    cfg,
    `mutation productVariantsBulkCreate($productId: ID!, $variants: [ProductVariantsBulkInput!]!) {
      productVariantsBulkCreate(
        productId: $productId,
        variants: $variants,
        strategy: REMOVE_STANDALONE_VARIANT
      ) {
        productVariants {
          id
          title
          sku
          price
        }
        userErrors { field message }
      }
    }`,
    { productId: shopifyProduct.id, variants }
  );

  const variantErrors = variantsResult.productVariantsBulkCreate?.userErrors || [];
  if (variantErrors.length) {
    throw new Error(`Shopify 创建变体失败：${variantErrors.map((e) => e.message).join("; ")}`);
  }

  return {
    id: shopifyProduct.id,
    title: shopifyProduct.title,
    handle: shopifyProduct.handle,
    variantCount: variantsResult.productVariantsBulkCreate.productVariants.length,
    imageCount: media.length
  };
}

export async function checkShopifyConnection(cfg) {
  const data = await graphql(
    cfg,
    `query shopInfo {
      shop {
        name
        myshopifyDomain
        primaryDomain { url }
      }
    }`
  );
  return data.shop;
}
