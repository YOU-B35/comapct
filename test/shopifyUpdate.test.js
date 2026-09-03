import test from "node:test";
import assert from "node:assert/strict";
import { listShopifyProducts, updateShopifyProducts } from "../src/shopify.js";

const cfg = {
  shopify: {
    storeDomain: "test.myshopify.com",
    accessToken: "token",
    apiVersion: "2026-07"
  },
  oauth: {}
};

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

test("listShopifyProducts returns normalized products", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return jsonResponse({
      data: {
        products: {
          edges: [
            {
              node: {
                id: "gid://shopify/Product/1",
                title: "A",
                handle: "a",
                status: "DRAFT",
                productType: "Fishing",
                vendor: "Vendor",
                tags: ["carp"],
                descriptionHtml: "<p>A</p>",
                variants: {
                  edges: [
                    {
                      node: {
                        id: "gid://shopify/ProductVariant/10",
                        title: "Default",
                        sku: "SKU",
                        price: "9.99"
                      }
                    }
                  ]
                }
              }
            }
          ]
        }
      }
    });
  };

  try {
    const products = await listShopifyProducts(cfg, { query: "title:A", limit: 10 });
    assert.equal(products.length, 1);
    assert.equal(products[0].title, "A");
    assert.equal(products[0].variants[0].sku, "SKU");
    assert.match(calls[0].url, /graphql\.json$/);
    assert.equal(calls[0].body.variables.query, "title:A");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("updateShopifyProducts updates selected product fields", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    return jsonResponse({
      data: {
        productUpdate: {
          product: {
            id: body.variables.product.id,
            title: body.variables.product.title || "A",
            handle: "a",
            status: body.variables.product.status || "DRAFT",
            productType: body.variables.product.productType || "",
            vendor: body.variables.product.vendor || "",
            tags: body.variables.product.tags || []
          },
          userErrors: []
        }
      }
    });
  };

  try {
    const result = await updateShopifyProducts(cfg, ["gid://shopify/Product/1"], {
      productType: "Fishing Tools",
      tags: "carp, rig",
      status: "ACTIVE"
    });
    assert.equal(result.updated, 1);
    assert.equal(calls[0].variables.product.productType, "Fishing Tools");
    assert.deepEqual(calls[0].variables.product.tags, ["carp", "rig"]);
    assert.equal(calls[0].variables.product.status, "ACTIVE");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("updateShopifyProducts can update all variant prices", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    calls.push(body);
    if (body.query.includes("query productVariants")) {
      return jsonResponse({
        data: {
          product: {
            id: body.variables.id,
            variants: {
              edges: [
                { node: { id: "gid://shopify/ProductVariant/10", title: "S", sku: "S", price: "1.00" } },
                { node: { id: "gid://shopify/ProductVariant/11", title: "M", sku: "M", price: "2.00" } }
              ]
            }
          }
        }
      });
    }
    return jsonResponse({
      data: {
        productVariantsBulkUpdate: {
          productVariants: [
            { id: "gid://shopify/ProductVariant/10", title: "S", sku: "S", price: "8.50" },
            { id: "gid://shopify/ProductVariant/11", title: "M", sku: "M", price: "8.50" }
          ],
          userErrors: []
        }
      }
    });
  };

  try {
    const result = await updateShopifyProducts(cfg, ["gid://shopify/Product/1"], { variantPrice: "8.5" });
    assert.equal(result.updated, 1);
    assert.equal(result.results[0].variantCount, 2);
    assert.equal(calls[1].variables.variants[0].price, "8.50");
    assert.equal(calls[1].variables.variants[1].price, "8.50");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
