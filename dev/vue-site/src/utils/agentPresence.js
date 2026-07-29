/**
 * Agent 在线判定（P0）
 *
 * 本机 :18765/health 只能说明「有进程」，不能说明「当前登录企业的助手在线」。
 * 业务「可同步 / 可打开登录」必须以 Java 当前租户心跳 agent_online 为准。
 */

export function resolveAgentPresence({ tenantOnline = false, localProcessOnline = false } = {}) {
  const tenant = Boolean(tenantOnline)
  const local = Boolean(localProcessOnline)
  const tenantMismatch = local && !tenant

  return {
    /** 当前企业心跳在线 —— 业务唯一可信「在线」 */
    tenantOnline: tenant,
    /** 本机健康口有进程 —— 仅辅助排障 */
    localProcessOnline: local,
    /** @deprecated 语义易混；请用 tenantOnline。保留兼容旧绑定名 */
    agentOnline: tenant,
    /** 本机有进程，但心跳不属于当前企业 */
    tenantMismatch,
    primaryLabel: tenant ? '当前企业助手 在线' : '当前企业助手 离线',
    primaryType: tenant ? 'success' : 'danger',
    localLabel: local ? '本机进程 有' : '本机进程 无',
    localType: local ? 'success' : 'info',
    mismatchTitle: '本机助手进程与当前企业不匹配',
    mismatchDescription:
      '检测到本机 :18765 有同步助手进程，但当前登录企业没有收到心跳。' +
      '通常是启动了其他企业的 CrossHub-Sync-Helper.exe（config.json 里 agent_token 绑错租户）。' +
      '请联系运维关闭旧进程，用当前企业 token 重写 config.json 后重启。',
  }
}

/** Amazon / 一键同步等：是否允许对本企业下发 Agent 任务 */
export function canUseTenantAgent(presence) {
  return Boolean(presence?.tenantOnline ?? presence?.agentOnline)
}
