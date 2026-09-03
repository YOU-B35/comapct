import path from "node:path";
import readExcelFile, { readSheet } from "read-excel-file/node";

const REQUIRED_COLUMN_KEYS = new Set([
  "groupKey",
  "rowType",
  "title",
  "price",
  "variantTitle",
  "internalSku"
]);

function normalizeHeaderName(name, seen) {
  const base = String(name || "").trim();
  if (!base) return null;
  seen[base] = (seen[base] || 0) + 1;
  return seen[base] === 1 ? base : `${base}_${seen[base]}`;
}

function addColumn(entries, key, column, required) {
  if (!column || typeof column !== "string") return;
  entries.push({ key, column, required });
}

function configuredColumns(fieldMap) {
  const columns = fieldMap.columns || {};
  const entries = [];

  for (const [key, value] of Object.entries(columns)) {
    if (key === "parentValue" || key === "variantValue") continue;
    if (key === "reviews" && Array.isArray(value)) {
      for (const review of value) {
        addColumn(entries, "reviews.text", review.text, false);
        addColumn(entries, "reviews.image", review.image, false);
      }
      continue;
    }

    const required = REQUIRED_COLUMN_KEYS.has(key);
    if (Array.isArray(value)) {
      for (const column of value) addColumn(entries, key, column, required);
      continue;
    }
    addColumn(entries, key, value, required);
  }

  const seen = new Set();
  return entries.filter((entry) => {
    const id = `${entry.key}:${entry.column}`;
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}

export function validateWorkbookColumns(headers, fieldMap) {
  const available = new Set((headers || []).map((header) => header.key));
  const missingRequiredColumns = [];
  const missingOptionalColumns = [];

  for (const entry of configuredColumns(fieldMap)) {
    if (available.has(entry.column)) continue;
    const target = entry.required ? missingRequiredColumns : missingOptionalColumns;
    target.push(entry.column);
  }

  return {
    ok: missingRequiredColumns.length === 0,
    missingRequiredColumns,
    missingOptionalColumns
  };
}

export async function parseWorkbook(filePath, fieldMap) {
  const sheets = await readExcelFile(filePath);
  const sheetNames = sheets.map((sheet) => sheet.sheet);
  const sheetName = fieldMap.sheetName || sheetNames[0];

  if (!sheetNames.includes(sheetName)) {
    throw new Error(`找不到工作表：${sheetName}`);
  }

  const matrix = sheets.find((sheet) => sheet.sheet === sheetName)?.data || (await readSheet(filePath, sheetName));
  const headerIndex = Math.max(0, Number(fieldMap.headerRow || 1) - 1);
  const seen = {};
  const headers = [];
  const headerRow = matrix[headerIndex] || [];

  for (let col = 0; col < headerRow.length; col += 1) {
    const key = normalizeHeaderName(headerRow[col], seen);
    if (key) headers.push({ key, column: col, label: key.replace(/_\d+$/, "") });
  }

  const templateValidation = validateWorkbookColumns(headers, fieldMap);
  if (!templateValidation.ok) {
    const optional = templateValidation.missingOptionalColumns.length
      ? `；同时缺少可选字段：${templateValidation.missingOptionalColumns.join("、")}`
      : "";
    throw new Error(
      `Excel 模板缺少必填字段：${templateValidation.missingRequiredColumns.join("、")}${optional}。请检查 ${sheetName} 第 ${headerIndex + 1} 行表头，或修改 config\\field-map.json。`
    );
  }

  const rows = [];
  for (let r = headerIndex + 1; r < matrix.length; r += 1) {
    const row = {};
    let hasValue = false;
    for (const header of headers) {
      const value = matrix[r]?.[header.column] ?? "";
      const normalized = value instanceof Date ? value.toISOString().slice(0, 10) : value;
      if (normalized !== "" && normalized !== null && normalized !== undefined) hasValue = true;
      row[header.key] = normalized;
    }
    if (hasValue) {
      row.__rowNumber = r + 1;
      rows.push(row);
    }
  }

  return {
    sourceFile: path.basename(filePath),
    sheetNames,
    selectedSheet: sheetName,
    headers,
    templateValidation,
    rows
  };
}
