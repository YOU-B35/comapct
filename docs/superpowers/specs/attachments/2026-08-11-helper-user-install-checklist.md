# CrossHub Sync Helper — 用户本机安装 checklist

> 日期：2026-08-11  
> 适用：Boss 端口 / 员工端口（凡要用 Temu **同步** 或 **重新登录** 的电脑）  
> 设计：`docs/superpowers/specs/2026-08-11-user-local-helper-temu-sync-design.md`

**原则（写死）：**

| 场景 | 做法 |
|------|------|
| 谁要装 | Boss / 员工，本机要用同步或重登就必须装 |
| 同一人多台电脑 | **每台分别安装** |
| 同一台电脑多账号 | **只装一次**；换 CrossHub 账号时在助手内切换绑定，不必重装 |
| 安装粒度 | **按电脑安装，不按账号安装** |

本清单**不包含**真实二进制产物；发版前由 releaser 按下方 SHA256 步骤补齐。

---

## 下载地址（网站钩子）

| 项 | 值 |
|----|-----|
| 前端环境变量 | `VITE_HELPER_DOWNLOAD_URL`（`dev/vue-site/.env*`） |
| 未配置时默认占位 | `/crosshub/downloads/CrossHub-Sync-Helper.zip` |
| 显式关闭下载 | 设为空白或 `none` → 横幅提示 **请联系管理员获取安装包** |
| 线上静态建议路径 | `https://www.yoto.work/crosshub/downloads/CrossHub-Sync-Helper.zip` |

Nginx / 静态目录需实际放置安装包后，默认占位链接才会可用；在此之前可将 `VITE_HELPER_DOWNLOAD_URL=none` 强制走「联系管理员」。

---

## Boss 安装步骤

- [ ] 使用 **Boss 账号**登录 `https://www.yoto.work/crosshub/`（或本地 Vue）
- [ ] 进入 **Temu** 模块；若提示「本机同步助手未在线」，点击 **下载 Sync Helper**
- [ ] 若按钮提示「请联系管理员获取安装包」，向管理员索取 zip/安装包，并按下方「完整性校验」核对 SHA256
- [ ] 在本机解压/安装并启动 **CrossHub Sync Helper**（保持运行；建议开机自启）
- [ ] 回到网站点击 **生成绑定码**，复制约 10 分钟有效的一次性码
- [ ] 在 Helper 面板粘贴绑定码完成绑定；网站应变为「助手在线」
- [ ] 在 Temu 模块试一次 **重新登录**（本机弹出浏览器完成账密/短信/滑块）与 **同步数据**
- [ ] 若 Boss 另有笔记本/台式机要用同步：在那台机器上 **重复本清单**（不可共用一台 Helper 冒充多机）

---

## 员工安装步骤

- [ ] 使用 **员工账号**登录员工端口（与 Boss 同一套助手模型，不走运维肉机）
- [ ] 进入 **Temu** 模块；离线横幅出现时 **下载 Sync Helper**（或向管理员取包）
- [ ] 本机安装并启动 Helper
- [ ] 网站 **生成绑定码** → Helper 内粘贴绑定 → 确认「助手在线」
- [ ] 完成一次本机 Temu **重新登录** 与 **同步**（仅能操作本人数据范围内店铺）
- [ ] 换电脑办公时：新电脑重新安装并重新绑定（绑定码按当前登录用户生成）

---

## 同机换账号（不必重装）

- [ ] 在 Helper 内 **退出绑定 / 重新绑定**
- [ ] 用新账号在网站生成绑定码并粘贴
- [ ] 确认 Profile 已按用户隔离（避免 Temu Cookie 串号）
- [ ] **不要**为换账号而卸载重装

---

## Releaser：发版与 SHA256（占位）

发版人在上传安装包前填写并勾选：

| 字段 | 填写 |
|------|------|
| 版本号 | `_TBD_`（如 `1.0.0`） |
| 产物文件名 | `CrossHub-Sync-Helper.zip`（或签名安装包名） |
| 发布路径 | `/crosshub/downloads/`（相对站点）或对象存储 URL |
| `VITE_HELPER_DOWNLOAD_URL` | 与实际上线 URL 一致 |
| SHA256 | `_TBD_REPLACE_WITH_sha256sum_OUTPUT_` |
| 代码签名 | `_TBD_`（有则填证书/拇指印；无则注明「仅哈希校验」） |
| 发布日期 | `_TBD_` |

### Windows（PowerShell）生成哈希

```powershell
Get-FileHash -Algorithm SHA256 .\CrossHub-Sync-Helper.zip | Format-List
```

### 校验（用户或运维）

```powershell
(Get-FileHash -Algorithm SHA256 .\CrossHub-Sync-Helper.zip).Hash
# 应与发版清单中的 SHA256 一致（忽略大小写）
```

### 发版勾选

- [ ] 产物已上传到约定下载路径（或内部分发渠道）
- [ ] 本清单 SHA256 / 版本号已从 `_TBD_` 更新为真实值
- [ ] 前端构建已设置正确的 `VITE_HELPER_DOWNLOAD_URL`（或确认默认占位路径已由 Nginx 提供文件）
- [ ] 抽检：未安装用户点击「下载 Sync Helper」可得到该产物；空 URL / `none` 时文案为 **请联系管理员获取安装包**
- [ ] **未**把未签名的临时调试包标为生产正式版

---

## 验收勾选（安装侧）

- [ ] Boss 本机：绑定后可同步 / 重登
- [ ] 员工本机：绑定后可同步 / 重登，无需接触运维肉机
- [ ] 同一人第二台电脑：需第二次安装 + 绑定
- [ ] 同一台电脑换 CrossHub 账号：重绑即可，无需重装
- [ ] 助手离线时网站有明确引导（下载或联系管理员），而非笼统「登录过期」

---

## 相关链接

| 文档 / 代码 | 说明 |
|-------------|------|
| 设计规格 | `docs/superpowers/specs/2026-08-11-user-local-helper-temu-sync-design.md` |
| 实现计划 Task 8 | `docs/superpowers/plans/2026-08-11-user-local-helper-temu-sync.md` |
| 下载 URL 解析 | `dev/vue-site/src/api/agentHelper.js` → `resolveHelperDownloadUrl` |
| 离线横幅 | `dev/vue-site/src/components/temu/TemuHelperBanner.vue` |
| 环境变量示例 | `dev/vue-site/.env.example` |
