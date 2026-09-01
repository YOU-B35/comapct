import fs from "node:fs/promises";
import path from "node:path";
import { unzipSync } from "fflate";

const ID_RE = /ID_[A-F0-9]+/;
const CELL_IMAGE_RE = /<xdr:cNvPr[^>]*name="(ID_[A-F0-9]+)"[^>]*\/>[\s\S]*?r:embed="(rId\d+)"/g;
const RELS_RE = /Id="(rId\d+)"[^>]*Target="(media\/[^"]+)"/g;

function formulaId(raw) {
  const match = ID_RE.exec(String(raw || ""));
  return match ? match[0] : "";
}

/**
 * 从 WPS/Excel 的 DISPIMG 内嵌图片公式中提取真实图片文件。
 *
 * xlsx 内 `xl/cellimages.xml` 记录了 图片ID -> rId 的映射，
 * `xl/_rels/cellimages.xml.rels` 记录 rId -> media 文件名。
 * 对每个 product.images 中带 DISPIMG 公式的图片位，把对应媒体文件解压到 destDir，
 * 并回填 image.filePath / usable，使后续上传流程可以当作本地图片处理。
 */
export async function extractCellImages(xlsxPath, products, destDir) {
  const bytes = new Uint8Array(await fs.readFile(xlsxPath));
  let files;
  try {
    files = unzipSync(bytes);
  } catch (error) {
    throw new Error(`无法解析 Excel 内嵌图片：${error.message}`);
  }

  const decode = (name) => {
    const data = files[`xl/${name}`];
    return data ? new TextDecoder().decode(data) : "";
  };

  const idToRid = new Map();
  let match;
  const cellImagesXml = decode("cellimages.xml");
  CELL_IMAGE_RE.lastIndex = 0;
  while ((match = CELL_IMAGE_RE.exec(cellImagesXml))) {
    idToRid.set(match[1], match[2]);
  }

  const ridToMedia = new Map();
  const relsXml = decode("_rels/cellimages.xml.rels");
  RELS_RE.lastIndex = 0;
  while ((match = RELS_RE.exec(relsXml))) {
    ridToMedia.set(match[1], match[2]);
  }

  const missing = [];
  let extracted = 0;
  let skuImagesExtracted = 0;

  const extractOne = async (id, target, label) => {
    if (!id) return false;
    const rid = idToRid.get(id);
    const media = rid && ridToMedia.get(rid);
    if (!media) {
      missing.push({ label, id });
      return false;
    }
    const data = files[`xl/${media}`];
    if (!data) {
      missing.push({ label, id, media });
      return false;
    }
    const ext = path.extname(media) || ".png";
    const filePath = path.join(destDir, label, `image-${target.index || "sku"}${ext}`);
    await fs.mkdir(path.dirname(filePath), { recursive: true });
    await fs.writeFile(filePath, data);
    target.filePath = filePath;
    target.extracted = true;
    target.usable = true;
    target.warning = "";
    target.media = media;
    return true;
  };

  for (const product of products) {
    for (const image of product.images) {
      const id = formulaId(image.raw);
      if (await extractOne(id, image, product.handle || product.id)) extracted += 1;
    }
    const variants = product.variants || [];
    for (let vi = 0; vi < variants.length; vi += 1) {
      const variant = variants[vi];
      const id = formulaId(variant.skuImage);
      if (!id) continue;
      const label = `${product.handle || product.id}-sku-${vi + 1}`;
      const target = { index: vi + 1 };
      if (await extractOne(id, target, label)) {
        variant.skuImageFilePath = target.filePath;
        variant.skuImageExtracted = true;
        variant.skuImageUsable = true;
        variant.skuImageWarning = "";
        variant.skuImageMedia = target.media;
        skuImagesExtracted += 1;
      }
    }
  }

  return {
    extracted,
    skuImagesExtracted,
    missing,
    mediaCount: Object.keys(files).filter((name) => name.startsWith("xl/media/")).length
  };
}
