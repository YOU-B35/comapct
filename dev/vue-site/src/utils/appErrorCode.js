/** 与后端 AppErrorCode 对齐的用户提示 */
export const APP_ERROR_MESSAGES = {
  SERVER_ERROR: '服务器繁忙，请稍后重试',
  BAD_REQUEST: '请求参数有误',
  NOT_FOUND: '资源不存在',
  FORBIDDEN: '无权执行此操作',
  UNAUTHORIZED: '请先登录',
  UNKNOWN: '操作失败，请稍后重试',

  CRAWL_IN_PROGRESS: '已有爬取任务进行中，请稍后再试',
  CRAWL_NOT_LOGGED_IN: 'Temu 卖家后台未登录，请联系运维在肉机完成登录；数据由定时任务自动同步',
  CRAWL_AE_NOT_LOGGED_IN: 'AliExpress 卖家后台未登录，请联系运维处理',
  CRAWL_MALL_NOT_SELECTED: '卖家后台未选择店铺，请联系运维在肉机选店后等待定时同步',
  CRAWL_SCRIPT_MISSING: '爬虫环境未配置，请联系管理员',
  CRAWL_TIMEOUT: '数据同步超时，请稍后查看侧栏同步状态或等待下次定时同步',
  CRAWL_PYTHON_ENV: '爬虫运行环境异常，请检查 Python 与依赖',
  CRAWL_PROCESS_FAILED: '数据同步失败，请稍后查看同步状态或联系运维',
  CRAWL_SEED_DISABLED: '当前环境不允许演示数据同步',
  CRAWL_JOB_NOT_FOUND: '同步任务不存在',
  CRAWL_INTERRUPTED: '同步任务已中断，请等待下次定时同步或联系运维',
  CRAWL_COOLDOWN: '同步冷却中，请稍后再查看；日常数据由运维机定时同步',
  TEMU_AGENT_OFFLINE: '运维同步节点未在线，请联系运维启动 CrossHub-Sync-Helper.exe',
  TEMU_REGION_NO_PERMISSION: 'Temu 页面提示「该区暂无权限」：请留在全球商家中心，打开侧栏「销售管理」（全托管），不要进美区/欧区',

  COMPETITOR_LOGIN_REQUIRED: 'Temu 前台需要登录或验证，已打开登录窗口，请完成后关闭窗口再重试',
  COMPETITOR_FRONTEND_LOGIN_REQUIRED: 'Temu 前台需要登录或验证，已打开登录窗口，请完成后关闭窗口再重试',
  COMPETITOR_STORE_UNAVAILABLE: '该竞店在当前地区或账号下不可访问，请更换可访问的店铺链接',
  COMPETITOR_NO_PRODUCTS: '未识别到竞店商品，请确认填写的是店铺页或商品列表页',
  COMPETITOR_DISCOVERY_NO_RESULTS: '南非站未找到渔具候选，可稍后重试或手动输入链接',
  COMPETITOR_CRAWL_TIMEOUT: '竞店爬取超时，请关闭登录窗口或稍后重试',
  COMPETITOR_BROWSER_PROFILE_UNAVAILABLE: 'Temu 前台浏览器配置无法打开，请关闭已弹出的 Chrome 登录窗口后重试',
  COMPETITOR_CRAWL_FAILED: '竞店爬取失败，请检查链接、登录状态或页面是否可访问',

  MONITOR_NO_PRODUCTS: '未抓到竞店商品',
  MONITOR_INVALID_URL: '竞店链接无效',
  MONITOR_TARGET_URL_INVALID: '请填写 Temu 店铺链接（含 mall_id），商品详情页无法作为竞店抓取',
  MONITOR_SOURCE_UNAVAILABLE: '缺少页面卡片证据',
  MONITOR_PARSER_CHANGED: '页面卡片解析规则已变化',
  MONITOR_AUTH_REQUIRED: '数据来源需要授权',
  MONITOR_RISK_BLOCKED: '数据来源被风控拦截',
  MONITOR_TIMEOUT: '竞店快照任务超时',
  MONITOR_JOB_FAILED: '竞店快照任务失败',
  MONITOR_LEGACY_ANALYZE_DISABLED: '旧竞店分析入口已停用',

  AUTH_MISSING_USER: '登录状态无效，请重新登录',
  AUTH_MISSING_TENANT: '缺少企业上下文，请重新登录',
  AUTH_NOT_LOGGED_IN: '未登录',

  ACCOUNT_STORE_NAME_REQUIRED: '店铺名称不能为空',
  ACCOUNT_LOGIN_REQUIRED: '登录账号不能为空',
  ACCOUNT_PASSWORD_REQUIRED: '登录密码不能为空',
  ACCOUNT_NOT_FOUND: '店铺不存在',
  ACCOUNT_PLATFORM_IMMUTABLE: '不允许修改店铺所属平台',
  ACCOUNT_NAME_CONFLICT: '该平台下已存在同名店铺',
  ACCOUNT_BATCH_EMPTY: '请至少提交一个店铺',
  ACCOUNT_UNSUPPORTED_PLATFORM: '不支持的平台',

  TASK_NOT_FOUND: '任务不存在',
  TASK_FORBIDDEN: '无权查看该任务',
  TASK_BOSS_ONLY: '仅企业管理员可管理任务',

  FEEDBACK_TASK_ID_REQUIRED: '缺少任务 ID',

  HOT_BROADCAST_NOT_FOUND: '通报记录不存在',
  RESTOCK_STATUS_NOT_FOUND: '备货状态不存在',

  WAREHOUSE_ORDER_NOT_FOUND: '订单不存在',
  WAREHOUSE_ORDER_ALREADY_PUSHED: '该订单已推送至仓库',
  WAREHOUSE_ORDER_FORBIDDEN: '无权查看该订单',
  WAREHOUSE_SCOPE_FORBIDDEN: '未分配仓库管理权限',
  WAREHOUSE_ORDER_SCOPE_FORBIDDEN: '无权操作该仓库订单',
  WAREHOUSE_CANCEL_FORBIDDEN: '仓库用户不可取消订单',
  WAREHOUSE_CANCEL_SCOPE_FORBIDDEN: '无权取消该订单',
  WAREHOUSE_OUTBOUND_FORBIDDEN: '无权创建出库单',
  WAREHOUSE_FEATURE_FORBIDDEN: '未授权仓库下单功能',
  WAREHOUSE_USER_ONLY: '仅仓库用户可操作',
  WAREHOUSE_BOSS_DELETE_ONLY: '仅企业管理员可删除订单',
  WAREHOUSE_JSON_ERROR: '数据保存失败，请稍后重试',

  MEMBER_PLATFORM_REQUIRED: '请至少选择一个负责平台',
  MEMBER_INVALID_MENU: '存在无效的菜单权限',
  MEMBER_SHOP_PLATFORM_MISMATCH: '所选店铺与平台不匹配',
  MEMBER_SHOP_PLATFORM_UNKNOWN: '无法识别店铺所属平台',

  AMAZON_AGENT_OFFLINE: '本机同步程序未运行，请联系运维启动 CrossHub-Sync-Helper.exe',
  AMAZON_ZINIAO_OFFLINE: '紫鸟 WebDriver 未就绪，请确认开发者模式已启动',
  AMAZON_SYNC_IN_PROGRESS: '已有 Amazon 同步任务进行中，请稍后再试',
  AMAZON_SYNC_JOB_NOT_FOUND: 'Amazon 同步任务不存在',
  AMAZON_SYNC_FAILED: 'Amazon 数据同步失败，请稍后重试',
  AMAZON_LOGIN_REQUIRED: 'Amazon 卖家后台未登录，请在紫鸟浏览器中重新登录 Seller Central',
  AMAZON_NO_PRODUCT_ROWS: '同步完成，但未解析到带 ASIN 的产品行',
  AMAZON_WRITE_IN_PROGRESS: '已有 Amazon 写操作任务进行中，请稍后再试',
  AMAZON_WRITE_JOB_NOT_FOUND: 'Amazon 写操作任务不存在',
  AMAZON_WRITE_FAILED: 'Amazon 写操作失败，请稍后重试',
  AMAZON_WRITE_DOM_FAILED: 'Seller Central 页面结构变化或未找到操作入口，请手动确认后重试',
}

const CRAWL_ERROR_UI = {
  CRAWL_COOLDOWN: {
    title: '同步冷却中',
    summary: '请稍后再查看侧栏同步状态。日常数据由运维机定时自动同步，网页不提供手动强制刷新。',
    steps: [],
  },
  TEMU_AGENT_OFFLINE: {
    title: '运维同步节点离线',
    summary: '未检测到当前企业的运维机同步心跳。登录与爬取只在运维肉机执行，运营网页不提供助手下载。',
    steps: [
      '联系运维确认已启动 CrossHub-Sync-Helper.exe（运维机常驻）。',
      '等待服务端定时同步完成后刷新本页查看数据。',
    ],
  },
  CRAWL_NOT_LOGGED_IN: {
    title: 'Temu 卖家后台未登录',
    summary: '运维肉机上的 Temu 会话未就绪，无法完成同步。运营成员无需在网页操作登录或同步。',
    steps: [
      '联系运维在肉机完成 Temu 卖家后台登录并选择店铺。',
      '确认运维机 CrossHub-Sync-Helper.exe 常驻在线。',
      '等待每天定时同步完成后刷新本页查看数据。',
    ],
  },
  CRAWL_MALL_NOT_SELECTED: {
    title: '请在卖家后台选择店铺',
    summary: '运维肉机已登录 Temu，但尚未选定要同步的店铺。',
    steps: [
      '联系运维在肉机浏览器左上角选择正确店铺。',
      '等待定时同步完成后刷新本页。',
    ],
  },
  CRAWL_PYTHON_ENV: {
    title: '爬虫环境异常',
    summary: '请确认已安装 Python 依赖与 Playwright 浏览器，或联系管理员检查服务器配置。',
    steps: [],
  },
  CRAWL_SCRIPT_MISSING: {
    title: '爬虫环境未配置',
    summary: '服务器未找到爬虫脚本目录，请联系管理员处理。',
    steps: [],
  },
  CRAWL_TIMEOUT: {
    title: '数据同步超时',
    summary: '同步耗时过长已自动停止，请等待下次定时同步或联系运维。',
    steps: [],
  },
  CRAWL_IN_PROGRESS: {
    title: '同步进行中',
    summary: '已有爬取任务正在执行，请稍后再查看本页数据。',
    steps: [],
  },
  CRAWL_INTERRUPTED: {
    title: '同步任务已中断',
    summary: '上次同步未完成，请等待下次定时同步或联系运维。',
    steps: [],
  },
  CRAWL_PROCESS_FAILED: {
    title: '数据同步失败',
    summary: '请稍后查看同步状态；若持续失败，请联系运维检查 Temu 登录与网络配置。',
    steps: [],
  },
  COMPETITOR_LOGIN_REQUIRED: {
    title: '需要完成 Temu 前台登录或验证',
    summary: '系统已打开普通 Chrome（非 Playwright）登录窗口。请在该窗口完成 Temu/Google 登录或验证，确认回到 www.temu.com 后关闭该 Chrome，再点击「发现渔具 Top10」。卖家后台登录不能代替买家前台登录。',
    steps: [
      '在弹出的普通 Chrome 窗口完成买家前台登录或验证。',
      '确认页面不再是 about:blank、login.html 空白页或验证页。',
      '完全关闭该 Chrome 窗口，释放租户 profile。',
      '回到本页再次点击「发现渔具 Top10」。',
    ],
  },
  COMPETITOR_FRONTEND_LOGIN_REQUIRED: {
    title: '需要完成 Temu 前台登录或验证',
    summary: '系统已打开普通 Chrome（非 Playwright）登录窗口。请在该窗口完成 Temu/Google 登录或验证，确认回到 www.temu.com 后关闭该 Chrome，再点击「发现渔具 Top10」。卖家后台登录不能代替买家前台登录。',
    steps: [
      '在弹出的普通 Chrome 窗口完成买家前台登录或验证。',
      '确认页面不再是 about:blank、login.html 空白页或验证页。',
      '完全关闭该 Chrome 窗口，释放租户 profile。',
      '回到本页再次点击「发现渔具 Top10」。',
    ],
  },
  COMPETITOR_STORE_UNAVAILABLE: {
    title: '竞店不可访问',
    summary: 'Temu 返回该店铺在当前地区或账号下不可用。请换一个能在当前 Chrome 中正常打开且有商品列表的店铺链接。',
    steps: [],
  },
  COMPETITOR_NO_PRODUCTS: {
    title: '未识别到竞店商品',
    summary: '当前链接没有可识别的商品卡。请确认填写的是店铺页、分类页或搜索列表页，不要填写单个商品详情页；如果页面能看到商品，可能需要补充页面选择器。',
    steps: [],
  },
  COMPETITOR_DISCOVERY_NO_RESULTS: {
    title: '南非站未找到渔具候选',
    summary: 'Temu ZA 当前搜索结果里没有抓到可用的渔具候选。可以稍后重试，或在下方手动输入你确认能打开的店铺/列表链接。',
    steps: [],
  },
  COMPETITOR_CRAWL_TIMEOUT: {
    title: '竞店爬取超时',
    summary: '可能是页面加载过慢、登录窗口未关闭或 Temu 风控卡住。请关闭弹出的登录 Chrome 后重试。',
    steps: [],
  },
  COMPETITOR_BROWSER_PROFILE_UNAVAILABLE: {
    title: 'Temu 前台浏览器配置被占用或无法打开',
    summary: '当前租户的 Temu 前台登录状态保存在独立 Chrome profile 中。这个 profile 现在可能被已打开的登录窗口占用，或上次 Chrome 异常退出后还未释放。',
    steps: [
      '关闭系统里刚弹出的 Temu/Chrome 登录窗口。',
      '如果任务管理器里还有 chrome.exe 占用该登录窗口，也请结束对应进程。',
      '回到本页重新点击「执行今日爬取分析」。',
      '如果仍然失败，重新触发一次登录窗口并完成 Temu 前台登录，系统会复用保存后的登录态。',
    ],
  },
  COMPETITOR_CRAWL_FAILED: {
    title: '竞店爬取失败',
    summary: '请检查链接是否可访问、登录状态是否有效，或更换一个商品列表页后重试。',
    steps: [],
  },
  MONITOR_SOURCE_UNAVAILABLE: {
    title: '缺少页面卡片证据',
    summary: '当前竞店快照链路只消费 boards/ctf-website 产出的页面卡片证据。请先把该店铺的 raw_products.json 放到 worker 的证据目录，再重新触发分析。',
    steps: [
      '用 boards/ctf-website 路线生成该竞店的页面卡片证据。',
      '将 raw_products.json 放入 CROSSHUB_MONITOR_EVIDENCE_DIR 对应 target id 或 mall id 目录。',
      '确认 Python worker 能读取证据目录后，重新点击「执行今日爬取分析」。',
    ],
  },
  MONITOR_INVALID_URL: {
    title: '竞店链接无效',
    summary: '请填写有效的 Temu 店铺链接，通常应为 temu.com 的 mall 页面或包含 mall_id 的店铺 URL。',
    steps: [],
  },
  MONITOR_TARGET_URL_INVALID: {
    title: '竞店链接格式不正确',
    summary: '请填写含 mall_id 的 Temu 店铺链接，或从「发现竞店」选入可用店铺；商品详情页无法作为竞店抓取。',
    steps: [
      '将链接改为 https://www.temu.com/mall.html?mall_id=... 形式。',
      '或使用「发现渔具 Top10」从候选列表选入。',
    ],
  },
  MONITOR_NO_PRODUCTS: {
    title: '未抓到竞店商品',
    summary: '页面卡片证据存在，但没有商品列表。请确认 raw_products.json 里包含商品卡片数组。',
    steps: [],
  },
  MONITOR_PARSER_CHANGED: {
    title: '页面卡片解析规则已变化',
    summary: '证据文件里有商品卡片，但当前解析器无法标准化必要字段。请检查 goods_id、标题、价格、销量、链接字段是否仍匹配。',
    steps: [],
  },
  MONITOR_AUTH_REQUIRED: {
    title: '数据来源需要授权',
    summary: '当前数据来源需要授权或登录后才能读取。请切换到已授权的数据来源或补齐采集侧授权。',
    steps: [],
  },
  MONITOR_RISK_BLOCKED: {
    title: '数据来源被风控拦截',
    summary: '数据来源触发了访问风控。当前 SaaS 链路不会启动浏览器兜底，请更换授权证据来源后重试。',
    steps: [],
  },
  MONITOR_TIMEOUT: {
    title: '竞店快照任务超时',
    summary: 'worker 在限定时间内没有完成快照处理。请稍后重试，或检查证据文件大小和 worker 状态。',
    steps: [],
  },
  MONITOR_JOB_FAILED: {
    title: '竞店快照任务失败',
    summary: 'worker 执行竞店快照任务失败。请查看任务错误详情或服务器日志。',
    steps: [],
  },
  MONITOR_LEGACY_ANALYZE_DISABLED: {
    title: '旧竞店分析入口已停用',
    summary: '竞店分析已经收口到 /api/monitor 任务链路。请通过当前竞店页面重新触发分析，不再调用旧 /api/temu/competitors/analyze。',
    steps: [],
  },
}

export function formatUserMessage(message, fallback = '操作失败，请稍后重试') {
  const text = String(message || '').trim()
  if (!text) return fallback

  if (/[\u4e00-\u9fff]/.test(text) && !isTechnicalEnglish(text)) {
    return text
  }

  if (isTechnicalEnglish(text)) {
    return fallback
  }

  if (!/[\u4e00-\u9fff]/.test(text)) {
    return fallback
  }

  return text
}

function isTechnicalEnglish(text) {
  return /is not defined|undefined is not|cannot read propert|network error|failed to fetch|timeout of \d+ms|unexpected token/i.test(text)
    || /^[A-Za-z_$][\w$.[\]'"]*$/.test(text)
}

export function formatCaughtError(err, fallback = '操作失败，请稍后重试') {
  if (err?.errorCode) {
    return getAppErrorMessage(err.errorCode, err.message)
  }
  return formatUserMessage(err?.message, fallback)
}

export function getAppErrorMessage(errorCode, fallback = '') {
  if (!errorCode) return fallback || APP_ERROR_MESSAGES.UNKNOWN
  return APP_ERROR_MESSAGES[errorCode] || fallback || APP_ERROR_MESSAGES.UNKNOWN
}

export function resolveAppError({ errorCode, message } = {}, tenantId = null) {
  const code = errorCode || ''
  const userMessage = getAppErrorMessage(code, message)
  const preset = CRAWL_ERROR_UI[code]

  if (preset) {
    return {
      errorCode: code,
      title: preset.title,
      summary: preset.summary,
      steps: typeof preset.steps === 'function' ? preset.steps(tenantId) : preset.steps,
    }
  }

  return {
    errorCode: code || 'UNKNOWN',
    title: userMessage,
    summary: message && message !== userMessage ? userMessage : '',
    steps: [],
  }
}

export class AppApiError extends Error {
  constructor(message, errorCode = 'UNKNOWN') {
    super(message || getAppErrorMessage(errorCode))
    this.name = 'AppApiError'
    this.errorCode = errorCode
  }
}

export function toAppApiError(payload, fallbackMessage = '请求失败') {
  const errorCode = payload?.error_code || payload?.data?.error_code || ''
  const message = getAppErrorMessage(errorCode, payload?.msg || payload?.message || fallbackMessage)
  return new AppApiError(message, errorCode || 'UNKNOWN')
}
