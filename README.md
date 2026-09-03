# Shopify 批量上货工具

这是一个本地运行的 Shopify 批量上货工具，支持上传 Excel 模板、预览校验商品、用 OpenAI 生成产品图，并通过 Shopify Admin GraphQL API 创建商品和变体。

## 目录

```text
E:\新建文件夹\shopify-bulk-uploader
```

## 准备配置

复制 `.env.example` 为 `.env`，明天拿到密钥后填入：

```env
SHOPIFY_STORE_DOMAIN=41bi0z-hk.myshopify.com
SHOPIFY_ADMIN_ACCESS_TOKEN=shpat_xxxxxxxxxxxxxxxxx
SHOPIFY_API_VERSION=2026-07

OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxx
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024

DEFAULT_PRODUCT_STATUS=DRAFT
DEFAULT_OPTION_NAME=Style
MAX_PRODUCTS_PER_RUN=20
PORT=3000
```

`SHOPIFY_STORE_DOMAIN` 必须是 `.myshopify.com` 域名，不是 `admin.shopify.com/store/...` 后台链接。

## 安装和启动

```powershell
cd E:\新建文件夹\shopify-bulk-uploader
npm install
npm run dev
```

打开：

```text
http://localhost:3000
```

## Excel 模板映射

默认读取 `Sheet1`，第一行为表头。当前模板按这个结构处理：

- `链接指向`：同一个商品组编号
- `状态`：`父体` 行保存商品主信息，`子体` 行保存变体
- `产品标题`：Shopify 商品标题
- `描述`、`详情页描述1-5`：合并为 Shopify HTML 描述
- `类别`：Shopify productType
- `产品系列`、`产品系列_2`：作为 Shopify tags 保存，后续可扩展成自动加入 collection
- `SKU（给客户看的）`：变体规格名
- `产品编码（给自己看的）` + `SKU（给客户看的）`：组合成变体 SKU
- `价格`：变体价格
- `产品图片1-6`：图片 URL、本地绝对路径，或由 AI 生成替代

如果你后面改了模板列名，可以编辑：

```text
config\field-map.json
```

上传 Excel 时会先校验模板字段。缺少必填字段会停止解析并在页面日志里列出字段名；缺少图片、详情、评论等可选字段时会继续解析，并把对应内容按空值处理。

当前必填字段：

- `链接指向`
- `状态`
- `产品标题`
- `SKU（给客户看的）`
- `产品编码（给自己看的）`
- `价格`

## 图片说明

模板里的 `=DISPIMG(...)` 是表格软件的内嵌图片公式，普通 Node 后端无法直接拿到真实图片文件。工具会识别并提醒。可选方案：

1. 勾选 AI 生图，让工具按标题和描述生成 6 张图。
2. 把图片列改成公开图片 URL。
3. 把图片列改成本机图片绝对路径，例如 `E:\产品图\sku-a\1.png`。

AI 生图规则：

- 第 1 张：白底主图
- 第 2-6 张：场景、细节、尺度、角度、包装/配件图

## 安全建议

首次运行建议先点击 `Dry Run`。确认商品数量、变体、价格和图片数量没问题后，再点击 `上架为草稿`。

默认创建为 `DRAFT`，不会直接公开到前台商城。

## 上架后修改商品

页面内置“已上架商品属性修改”面板，可直接从 Shopify 读取商品并更新指定属性。

操作流程：

1. 点击 `刷新商品`，或输入标题、handle、标签关键词后回车搜索。
2. 勾选一个或多个 Shopify 商品。
3. 在右侧表单里勾选要修改的属性，并填写新值。
4. 点击 `修改选中商品`，确认后提交到 Shopify。

当前支持修改：

- 商品状态：草稿、公开、归档
- 产品类型
- Vendor
- 标签
- 标题
- 描述 HTML
- 所有变体价格

表单只会更新已勾选的属性，未勾选的字段不会被覆盖。批量选择多个商品时要谨慎使用“标题”和“描述 HTML”，因为它会把选中商品改成同一个值。
