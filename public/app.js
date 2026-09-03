let currentBatch = null;
let selectedProductId = null;

const $ = (selector) => document.querySelector(selector);
const fileInput = $("#fileInput");
const uploadBtn = $("#uploadBtn");
const checkShopifyBtn = $("#checkShopifyBtn");
const dryRunBtn = $("#dryRunBtn");
const generateBtn = $("#generateBtn");
const publishBtn = $("#publishBtn");
const productList = $("#productList");
const detail = $("#detail");
const summary = $("#summary");
const logBox = $("#log");
const shopifyProductSearch = $("#shopifyProductSearch");
const loadShopifyProductsBtn = $("#loadShopifyProductsBtn");
const shopifyProductList = $("#shopifyProductList");
const selectAllShopifyProducts = $("#selectAllShopifyProducts");
const selectedShopifyCount = $("#selectedShopifyCount");
const productUpdateForm = $("#productUpdateForm");

let shopifyProducts = [];
let selectedShopifyProductIds = new Set();

function log(message, data) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  logBox.textContent = `${line}${data ? `\n${JSON.stringify(data, null, 2)}` : ""}\n\n${logBox.textContent}`;
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || "请求失败");
  return payload;
}

function renderSummary() {
  if (!currentBatch) {
    summary.innerHTML = "";
    return;
  }
  const items = [
    ["商品数", currentBatch.summary.productCount],
    ["变体数", currentBatch.summary.variantCount],
    ["错误", currentBatch.summary.errorCount],
    ["提醒", currentBatch.summary.warningCount]
  ];
  summary.innerHTML = items
    .map(([label, value]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
}

function renderProductList() {
  productList.innerHTML = currentBatch.products
    .map((product) => {
      const active = product.id === selectedProductId ? " active" : "";
      return `
        <article class="product-item${active}" data-id="${product.id}">
          <h3>${escapeHtml(product.title || "(缺少标题)")}</h3>
          <div class="badges">
            <span class="badge">${product.variants.length} 变体</span>
            <span class="badge">${product.images.length} 图位</span>
            ${product.errors.length ? `<span class="badge error">${product.errors.length} 错误</span>` : ""}
            ${product.warnings.length ? `<span class="badge warn">${product.warnings.length} 提醒</span>` : ""}
          </div>
        </article>`;
    })
    .join("");
  productList.querySelectorAll(".product-item").forEach((item) => {
    item.addEventListener("click", () => {
      selectedProductId = item.dataset.id;
      render();
    });
  });
}

function renderDetail() {
  const product = currentBatch?.products.find((item) => item.id === selectedProductId);
  if (!product) {
    detail.innerHTML = `<div class="empty">选择一个商品查看详情。</div>`;
    return;
  }

  const messages = [
    ...product.errors.map((message) => ({ type: "error", message })),
    ...product.warnings.map((message) => ({ type: "warn", message }))
  ];
  const imageSet = product.generatedImages?.length ? product.generatedImages : product.images;

  detail.innerHTML = `
    <div class="detail-grid">
      <section>
        <h2>${escapeHtml(product.title || "(缺少标题)")}</h2>
        <div class="badges">
          <span class="badge">Handle: ${escapeHtml(product.handle)}</span>
          <span class="badge">类型: ${escapeHtml(product.productType || "-")}</span>
          <span class="badge">状态: ${escapeHtml(product.status)}</span>
        </div>
      </section>
      ${messages.length ? `<section class="messages">${messages.map((item) => `<div class="message ${item.type}">${escapeHtml(item.message)}</div>`).join("")}</section>` : ""}
      <section class="two-col">
        <div>
          <h2>变体</h2>
          <table>
            <thead><tr><th>行号</th><th>规格</th><th>SKU</th><th>价格</th></tr></thead>
            <tbody>
              ${product.variants.map((variant) => `<tr><td>${variant.rowNumber || ""}</td><td>${escapeHtml(variant.title)}</td><td>${escapeHtml(variant.sku)}</td><td>${escapeHtml(variant.price || variant.sourcePrice)}</td></tr>`).join("")}
            </tbody>
          </table>
        </div>
        <div>
          <h2>产品图片</h2>
          <div class="gallery">
            ${imageSet.map(renderImageBox).join("")}
          </div>
        </div>
      </section>
      <section>
        <h2>描述预览</h2>
        <div>${product.descriptionHtml || "<p>无描述</p>"}</div>
      </section>
    </div>`;
}

function renderImageBox(image) {
  if (image.publicUrl) {
    return `<div class="image-box"><img src="${image.publicUrl}" alt="generated image ${image.index}"></div>`;
  }
  if (image.usable && /^https?:\/\//i.test(image.raw || image.filePath || "")) {
    return `<div class="image-box"><img src="${image.raw || image.filePath}" alt="product image ${image.index}"></div>`;
  }
  return `<div class="image-box">图片 ${image.index}<br>${escapeHtml(image.warning || "等待 AI 生成或填写 URL")}</div>`;
}

function renderShopifyProducts() {
  if (!shopifyProducts.length) {
    shopifyProductList.innerHTML = `<div class="empty small">没有找到商品。</div>`;
    updateSelectedShopifyCount();
    return;
  }

  shopifyProductList.innerHTML = shopifyProducts
    .map((product) => {
      const checked = selectedShopifyProductIds.has(product.id) ? " checked" : "";
      const tags = product.tags?.length ? product.tags.join(", ") : "-";
      return `
        <label class="shopify-product-row">
          <input type="checkbox" value="${escapeHtml(product.id)}"${checked}>
          <span>
            <strong>${escapeHtml(product.title || "(缺少标题)")}</strong>
            <small>${escapeHtml(product.handle)} · ${escapeHtml(product.status)} · ${escapeHtml(product.productType || "-")} · ${escapeHtml(tags)}</small>
          </span>
        </label>`;
    })
    .join("");

  shopifyProductList.querySelectorAll("input[type='checkbox']").forEach((checkbox) => {
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedShopifyProductIds.add(checkbox.value);
      else selectedShopifyProductIds.delete(checkbox.value);
      updateSelectedShopifyCount();
    });
  });
  updateSelectedShopifyCount();
}

function updateSelectedShopifyCount() {
  selectedShopifyCount.textContent = `已选 ${selectedShopifyProductIds.size} 个`;
  selectAllShopifyProducts.checked =
    shopifyProducts.length > 0 && shopifyProducts.every((product) => selectedShopifyProductIds.has(product.id));
}

async function loadShopifyProducts() {
  const query = shopifyProductSearch.value.trim();
  log(query ? `开始搜索 Shopify 商品：${query}` : "开始读取 Shopify 商品");
  const payload = await request(`/api/shopify/products?limit=50&query=${encodeURIComponent(query)}`);
  shopifyProducts = payload.products || [];
  selectedShopifyProductIds = new Set(
    [...selectedShopifyProductIds].filter((id) => shopifyProducts.some((product) => product.id === id))
  );
  renderShopifyProducts();
  log("Shopify 商品读取完成", { count: shopifyProducts.length });
}

function checkedField(form, checkboxName, valueName) {
  if (!form.elements[checkboxName].checked) return undefined;
  return form.elements[valueName].value.trim();
}

function buildUpdateFields(form) {
  const fields = {};
  const status = checkedField(form, "updateStatus", "status");
  const productType = checkedField(form, "updateProductType", "productType");
  const vendor = checkedField(form, "updateVendor", "vendor");
  const tags = checkedField(form, "updateTags", "tags");
  const variantPrice = checkedField(form, "updateVariantPrice", "variantPrice");
  const title = checkedField(form, "updateTitle", "title");
  const descriptionHtml = checkedField(form, "updateDescriptionHtml", "descriptionHtml");

  if (status !== undefined) fields.status = status;
  if (productType !== undefined) {
    if (!productType) throw new Error("已勾选产品类型，请填写产品类型。");
    fields.productType = productType;
  }
  if (vendor !== undefined) {
    if (!vendor) throw new Error("已勾选 Vendor，请填写 Vendor。");
    fields.vendor = vendor;
  }
  if (tags !== undefined) {
    if (!tags) throw new Error("已勾选标签，请填写至少一个标签。");
    fields.tags = tags;
  }
  if (variantPrice !== undefined) {
    if (!variantPrice) throw new Error("已勾选所有变体价格，请填写价格。");
    fields.variantPrice = variantPrice;
  }
  if (title !== undefined) {
    if (!title) throw new Error("已勾选标题，请填写标题。");
    fields.title = title;
  }
  if (descriptionHtml !== undefined) {
    if (!descriptionHtml) throw new Error("已勾选描述 HTML，请填写描述。");
    fields.descriptionHtml = descriptionHtml;
  }

  if (!Object.keys(fields).length) throw new Error("请选择至少一个要修改的属性。");
  return fields;
}

function render() {
  renderSummary();
  renderProductList();
  renderDetail();
  const enabled = Boolean(currentBatch);
  dryRunBtn.disabled = !enabled;
  generateBtn.disabled = !enabled;
  publishBtn.disabled = !enabled;
}

function escapeHtml(input) {
  return String(input ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

uploadBtn.addEventListener("click", async () => {
  try {
    if (!fileInput.files[0]) throw new Error("请先选择 Excel 文件。");
    const form = new FormData();
    form.append("file", fileInput.files[0]);
    log("开始解析 Excel");
    currentBatch = await request("/api/upload", { method: "POST", body: form });
    selectedProductId = currentBatch.products[0]?.id || null;
    render();
    log("解析完成", currentBatch.summary);
    const missingOptional = currentBatch.parsed?.templateValidation?.missingOptionalColumns || [];
    if (missingOptional.length) {
      log("模板可选字段缺失，相关内容会按空值处理", missingOptional);
    }
  } catch (error) {
    log(error.message);
  }
});

checkShopifyBtn.addEventListener("click", async () => {
  try {
    log("开始测试 Shopify 连接");
    const payload = await request("/api/shopify/check");
    log("Shopify 连接成功", payload);
  } catch (error) {
    log(`Shopify 连接失败：${error.message}`);
  }
});

dryRunBtn.addEventListener("click", async () => {
  try {
    const payload = await request(`/api/batches/${currentBatch.id}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dryRun: true })
    });
    log("Dry Run 完成", payload.results);
  } catch (error) {
    log(error.message);
  }
});

generateBtn.addEventListener("click", async () => {
  try {
    log("开始生成 AI 图片。每个商品 6 张，数量多时会比较久。");
    const payload = await request(`/api/batches/${currentBatch.id}/generate-images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    currentBatch.products = payload.products;
    render();
    log("AI 图片生成完成", payload.results);
  } catch (error) {
    log(error.message);
  }
});

publishBtn.addEventListener("click", async () => {
  try {
    const ok = window.confirm("确认把当前批次上架到 Shopify？默认会创建为草稿。");
    if (!ok) return;
    const payload = await request(`/api/batches/${currentBatch.id}/publish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dryRun: false, status: "DRAFT" })
    });
    log("Shopify 上架完成", payload.results);
    loadShopifyProducts().catch((error) => log(`刷新 Shopify 商品失败：${error.message}`));
  } catch (error) {
    log(error.message);
  }
});

loadShopifyProductsBtn.addEventListener("click", async () => {
  try {
    await loadShopifyProducts();
  } catch (error) {
    log(`读取 Shopify 商品失败：${error.message}`);
  }
});

shopifyProductSearch.addEventListener("keydown", async (event) => {
  if (event.key !== "Enter") return;
  try {
    await loadShopifyProducts();
  } catch (error) {
    log(`读取 Shopify 商品失败：${error.message}`);
  }
});

selectAllShopifyProducts.addEventListener("change", () => {
  if (selectAllShopifyProducts.checked) {
    selectedShopifyProductIds = new Set(shopifyProducts.map((product) => product.id));
  } else {
    selectedShopifyProductIds.clear();
  }
  renderShopifyProducts();
});

productUpdateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const productIds = [...selectedShopifyProductIds];
    if (!productIds.length) throw new Error("请先选择要修改的 Shopify 商品。");
    const fields = buildUpdateFields(productUpdateForm);
    const ok = window.confirm(`确认修改 ${productIds.length} 个 Shopify 商品？只会更新已勾选的属性。`);
    if (!ok) return;
    log("开始修改 Shopify 商品属性", { count: productIds.length, fields });
    const payload = await request("/api/shopify/products/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productIds, fields })
    });
    log("Shopify 商品属性修改完成", payload);
    await loadShopifyProducts();
  } catch (error) {
    log(`修改失败：${error.message}`);
  }
});

request("/api/status")
  .then((status) => {
    $("#configStatus").textContent = `店铺：${status.shopifyStoreDomain || "未配置"} · Shopify Token：${status.hasShopifyToken ? "已配置" : "未配置"} · OpenAI Key：${status.hasOpenAIKey ? "已配置" : "未配置"} · 图片模型：${status.openaiImageModel}`;
  })
  .catch((error) => {
    $("#configStatus").textContent = error.message;
  });
