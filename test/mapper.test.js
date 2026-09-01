import test from "node:test";
import assert from "node:assert/strict";
import { mapRowsToProducts, summarizeBatch } from "../src/mapper.js";

const fieldMap = {
  columns: {
    groupKey: "链接指向",
    rowType: "状态",
    parentValue: "父体",
    variantValue: "子体",
    mainSkuImage: "SKU 图片",
    collections: ["产品系列", "产品系列_2"],
    productType: "类别",
    price: "价格",
    variantTitle: "SKU（给客户看的）",
    internalSku: "产品编码（给自己看的）",
    title: "产品标题",
    description: "描述",
    productImages: ["产品图片1", "产品图片2"],
    detailDescriptions: [],
    detailImages: [],
    reviews: []
  }
};

test("maps parent and child rows into Shopify products", () => {
  const parsed = {
    rows: [
      {
        __rowNumber: 2,
        链接指向: 1,
        状态: "父体",
        产品系列: "A",
        产品系列_2: "B",
        类别: "钓鱼用具",
        产品标题: "Test Product",
        描述: "Line one\n\nLine two",
        产品图片1: "=DISPIMG(\"ID\",1)"
      },
      {
        __rowNumber: 3,
        链接指向: 1,
        状态: "子体",
        价格: 2.99,
        "SKU（给客户看的）": "Green 20PCS",
        "产品编码（给自己看的）": "Code"
      }
    ]
  };

  const products = mapRowsToProducts(parsed, fieldMap, { status: "DRAFT", optionName: "Style" });
  assert.equal(products.length, 1);
  assert.equal(products[0].title, "Test Product");
  assert.equal(products[0].variants[0].sku, "Code-Green-20PCS");
  assert.equal(products[0].variants[0].price, "2.99");
  assert.equal(products[0].collections.join(","), "A,B");
  assert.match(products[0].descriptionHtml, /Line one/);
  assert.equal(products[0].warnings.length, 1);
  assert.deepEqual(summarizeBatch(products), {
    productCount: 1,
    variantCount: 1,
    errorCount: 0,
    warningCount: 1
  });
});

test("deduplicates duplicated variant titles using internal sku", () => {
  const parsed = {
    rows: [
      {
        __rowNumber: 2,
        链接指向: 1,
        状态: "父体",
        产品标题: "Test Product",
        描述: "desc"
      },
      {
        __rowNumber: 3,
        链接指向: 1,
        状态: "子体",
        价格: 2.99,
        "SKU（给客户看的）": "2PCS",
        "产品编码（给自己看的）": "TZ-001-L"
      },
      {
        __rowNumber: 4,
        链接指向: 1,
        状态: "子体",
        价格: 3.99,
        "SKU（给客户看的）": "2PCS",
        "产品编码（给自己看的）": "TZ-001-S"
      }
    ]
  };

  const products = mapRowsToProducts(parsed, fieldMap, { status: "DRAFT", optionName: "Style" });
  const titles = products[0].variants.map((variant) => variant.title);
  assert.equal(titles.length, new Set(titles).size, "variant titles should be unique");
  assert.deepEqual(titles, ["2PCS L", "2PCS S"]);
});
