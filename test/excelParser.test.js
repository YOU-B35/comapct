import test from "node:test";
import assert from "node:assert/strict";
import { validateWorkbookColumns } from "../src/excelParser.js";

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
    detailDescriptions: ["详情页描述1"],
    detailImages: ["详情页图片1"],
    reviews: [{ text: "评论1", image: "评论1图片" }]
  }
};

function headers(keys) {
  return keys.map((key, column) => ({ key, column, label: key.replace(/_\d+$/, "") }));
}

test("validateWorkbookColumns accepts complete required headers and reports missing optional headers", () => {
  const result = validateWorkbookColumns(
    headers([
      "链接指向",
      "状态",
      "价格",
      "SKU（给客户看的）",
      "产品编码（给自己看的）",
      "产品标题"
    ]),
    fieldMap
  );

  assert.equal(result.ok, true);
  assert.deepEqual(result.missingRequiredColumns, []);
  assert.ok(result.missingOptionalColumns.includes("产品图片1"));
  assert.ok(result.missingOptionalColumns.includes("评论1图片"));
});

test("validateWorkbookColumns rejects templates missing required headers", () => {
  const result = validateWorkbookColumns(
    headers(["链接指向", "状态", "SKU（给客户看的）", "产品标题"]),
    fieldMap
  );

  assert.equal(result.ok, false);
  assert.deepEqual(result.missingRequiredColumns, ["价格", "产品编码（给自己看的）"]);
});
