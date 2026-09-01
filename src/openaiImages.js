import fs from "node:fs/promises";
import path from "node:path";
import OpenAI from "openai";
import { paths } from "./config.js";

function imagePrompts(product) {
  const base = product.imagePromptBase || product.title;
  return [
    `${base}\nCreate a clean ecommerce product image on a pure white background. Centered product, realistic studio lighting, sharp edges, no text, no watermark, no logo, no hands.`,
    `${base}\nCreate a realistic lifestyle product image showing the product in a natural use scenario. No text and no watermark.`,
    `${base}\nCreate a close-up detail product image emphasizing material, texture, and build quality. No text and no watermark.`,
    `${base}\nCreate a comparison/scale product image with the product clearly visible and professionally lit. No text, no watermark, no fake labels.`,
    `${base}\nCreate an angled product hero shot with a clean ecommerce look and soft shadows. No text and no watermark.`,
    `${base}\nCreate a packaging/accessories product composition, clear and realistic, suitable for an online store gallery. No text and no watermark.`
  ];
}

export async function generateProductImages(product, cfg) {
  if (!cfg.openai.apiKey) {
    throw new Error("缺少 OPENAI_API_KEY，无法生成图片。");
  }

  const client = new OpenAI({ apiKey: cfg.openai.apiKey });
  const dir = path.join(paths.generated, product.handle || product.id);
  await fs.mkdir(dir, { recursive: true });

  const outputs = [];
  const prompts = imagePrompts(product);
  for (let index = 0; index < prompts.length; index += 1) {
    const response = await client.images.generate({
      model: cfg.openai.imageModel,
      prompt: prompts[index],
      size: cfg.openai.imageSize
    });

    const item = response.data?.[0];
    if (!item?.b64_json && !item?.url) {
      throw new Error(`OpenAI 没有返回第 ${index + 1} 张图片数据。`);
    }

    const fileName = `image-${index + 1}.png`;
    const filePath = path.join(dir, fileName);
    const imageBytes = item.b64_json
      ? Buffer.from(item.b64_json, "base64")
      : await downloadImage(item.url);
    await fs.writeFile(filePath, imageBytes);
    outputs.push({
      index: index + 1,
      filePath,
      generated: true,
      usable: true,
      prompt: prompts[index]
    });
  }

  return outputs;
}

async function downloadImage(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`下载 OpenAI 图片失败：HTTP ${response.status}`);
  return Buffer.from(await response.arrayBuffer());
}
