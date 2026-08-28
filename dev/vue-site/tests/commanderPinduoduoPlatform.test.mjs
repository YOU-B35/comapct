import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const storeSrc = readFileSync(join(root, 'src/modules/commander/stores/autoUpload.js'), 'utf8')
const viewSrc = readFileSync(join(root, 'src/modules/commander/views/AutoUploadView.vue'), 'utf8')

// 平台选项：真实后端（Commander）拼多多平台 id 为 pinduoduo，而非 pdd
assert.match(storeSrc, /value:\s*'pinduoduo'/)
assert.match(storeSrc, /label:\s*'拼多多'/)
assert.doesNotMatch(storeSrc, /value:\s*'pdd'\s*,/)

// 提交上货前对拼多多执行真实后端预检（登录 + 店铺）
assert.match(storeSrc, /platform\s*===\s*'temu'\s*\|\|\s*platform\s*===\s*'douyin'\s*\|\|\s*platform\s*===\s*'1688'\s*\|\|\s*platform\s*===\s*'pinduoduo'/)
assert.match(storeSrc, /正在预检拼多多登录与店铺/)

// 模板：拼多多下载模板指向真实模板文件
assert.match(viewSrc, /pinduoduo:\s*\{/)
assert.match(viewSrc, /templates\/pinduoduo-publish-template\.xlsx/)
assert.match(viewSrc, /拼多多批量上货表单\.xlsx/)
assert.match(viewSrc, /请按拼多多批量上货表单填写后上传/)

// 模板文件必须真实存在（打包后会随 public/ 一起部署）
assert.equal(
  existsSync(join(root, 'public/templates/pinduoduo-publish-template.xlsx')),
  true,
  '缺少拼多多模板文件 public/templates/pinduoduo-publish-template.xlsx',
)

console.log('commanderPinduoduoPlatform.test.mjs ok')
