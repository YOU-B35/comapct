import path from "node:path";
import readExcelFile, { readSheet } from "read-excel-file/node";

function normalizeHeaderName(name, seen) {
  const base = String(name || "").trim();
  if (!base) return null;
  seen[base] = (seen[base] || 0) + 1;
  return seen[base] === 1 ? base : `${base}_${seen[base]}`;
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
    rows
  };
}
