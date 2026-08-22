import { defineStore } from 'pinia'
import { nowUtc8String } from '@/utils/time'
import { computed, ref } from 'vue'
import { runPlatformAutoSync, buildPlatformSyncTargets, hydratePlatformSyncFromBackend } from '@/api/platformSync'
import { canUseTemuBackend, fetchPlatformSyncStatus, formatCrawlError } from '@/api/temuApi'
import {
  formatCooldownRemaining,
  getCooldownRemainingMs,
  isPlatformCrawlInCooldown,
  isPlatformHydrateInCooldown,
  markPlatformHydrateCompleted,
  PLATFORM_SYNC_COOLDOWN_MS,
} from '@/utils/platformSyncCooldown'
import { canUseOpsManualSync } from '@/utils/opsSyncPolicy'

const SESSION_SYNC_KEY = 'crosshub_platform_sync_done'

const PLATFORM_LABELS = {
  temu: 'Temu',
  aliexpress: '速卖通',
  amazon: 'Amazon',
}

export const usePlatformSyncStore = defineStore('platformSync', () => {
  const items = ref([])
  const running = ref(false)
  const expanded = ref(true)
  const lastFinishedAt = ref('')
  const lastError = ref('')
  const cooldownSkippedAt = ref('')
  const boundAuth = ref(null)
  const platformSyncStatus = ref(null)

  const cooldownRemainingMs = computed(() => (
    boundAuth.value ? getCooldownRemainingMs(boundAuth.value) : 0
  ))
  const inCooldown = computed(() => cooldownRemainingMs.value > 0)
  const cooldownHint = computed(() => {
    if (!inCooldown.value) return ''
    return `同步冷却中，${formatCooldownRemaining(cooldownRemainingMs.value)}后可自动同步`
  })

  const hasItems = computed(() => items.value.length > 0)
  const successCount = computed(() => items.value.filter(
    (item) => item.status === 'success' || item.status === 'partial',
  ).length)
  const failedCount = computed(() => items.value.filter((item) => item.status === 'failed').length)
  const skippedCount = computed(() => items.value.filter((item) => item.status === 'skipped').length)
  const emptyCount = computed(() => items.value.filter((item) => item.status === 'empty').length)
  const syncingCount = computed(() => items.value.filter((item) => item.status === 'syncing').length)

  const scheduleText = computed(() => {
    const schedule = platformSyncStatus.value?.schedule
    if (!schedule) return ''
    const label = schedule.time_label || '每天 09:30'
    const scope = schedule.scope_label || '全平台'
    const next = schedule.next_run_hint ? ` · 下次约 ${schedule.next_run_hint}` : ''
    return schedule.enabled === false
      ? `${scope} ${label}（已关闭）`
      : `${scope} ${label}${next}`
  })

  const platformStatusRows = computed(() => {
    const platforms = platformSyncStatus.value?.platforms || {}
    return ['temu', 'aliexpress', 'amazon'].map((key) => {
      const row = platforms[key] || {}
      const job = row.last_job
      return {
        key,
        label: PLATFORM_LABELS[key] || key,
        hasError: Boolean(row.has_error),
        errorMessage: row.error_message || '',
        lastJobText: job
          ? `${job.trigger === 'daily_schedule' ? '日批' : '手动'} ${job.status || ''}${job.finished_at || job.created_at ? ` · ${job.finished_at || job.created_at}` : ''}`
          : '尚无同步记录',
      }
    })
  })

  const summaryText = computed(() => {
    if (running.value) return '正在同步店铺数据...'
    const temuPlatform = platformSyncStatus.value?.platforms?.temu
    const temuItem = items.value.find((item) => item.platform === 'temu')
    const temuOk = temuPlatform && !temuPlatform.has_error
      || temuItem && (temuItem.status === 'success' || temuItem.status === 'partial')
    if (!temuOk && platformSyncStatus.value?.has_error) {
      return platformSyncStatus.value.error_message
        || formatCrawlError(platformSyncStatus.value.error_code, '平台同步失败')
    }
    if (scheduleText.value && !items.value.length) {
      return scheduleText.value
    }
    if (!items.value.length) return '暂无绑定店铺'
    if (failedCount.value > 0) {
      return emptyCount.value > 0
        ? `${successCount.value} 成功 · ${failedCount.value} 失败 · ${emptyCount.value} 无数据`
        : `${successCount.value} 成功 · ${failedCount.value} 待处理`
    }
    if (skippedCount.value > 0) {
      return `${successCount.value} 成功 · ${skippedCount.value} 已跳过`
    }
    if (emptyCount.value > 0) return `${successCount.value} 成功 · ${emptyCount.value} 无数据`
    if (scheduleText.value) {
      return `${successCount.value} 个店铺已同步 · ${scheduleText.value}`
    }
    return `${successCount.value} 个店铺已同步`
  })

  function updateItems(nextItems = []) {
    items.value = nextItems.map((item) => ({ ...item }))
  }

  function updateStoreStatus({
    platform,
    storeId = '',
    storeName = '',
    externalShopId = '',
    status,
    message = '',
    rowCount = 0,
    syncedAt = '',
  }) {
    const keyCandidates = new Set()
    if (platform && storeId) keyCandidates.add(`${platform}:${storeId}`)
    if (platform && externalShopId) keyCandidates.add(`${platform}:${externalShopId}`)

    let matched = false
    items.value = items.value.map((item) => {
      const keyHit = keyCandidates.has(item.key)
      const metaHit =
        item.platform === platform
        && (
          (storeId && (item.storeId === storeId || item.externalShopId === storeId))
          || (externalShopId && (item.externalShopId === externalShopId || item.storeId === externalShopId))
          || (storeName && item.storeName === storeName)
        )
      if (!keyHit && !metaHit) return item
      matched = true
      return {
        ...item,
        status,
        message,
        rowCount,
        syncedAt: syncedAt || item.syncedAt,
      }
    })

    if (!matched && platform && (storeId || storeName)) {
      items.value = [
        ...items.value,
        {
          key: `${platform}:${storeId || externalShopId || storeName}`,
          platform,
          storeId: storeId || externalShopId || storeName,
          storeName: storeName || storeId || externalShopId,
          externalShopId,
          platformLabel: platform,
          status,
          message,
          rowCount,
          syncedAt,
        },
      ]
    }
  }

  function bindAuth(auth) {
    boundAuth.value = auth
  }

  async function loadPlatformSyncStatus(auth) {
    if (!auth?.backendLinked || auth.isWarehouse || !canUseTemuBackend(auth)) {
      platformSyncStatus.value = null
      return null
    }
    try {
      const status = await fetchPlatformSyncStatus()
      platformSyncStatus.value = status || null
      if (status?.has_error) {
        lastError.value = formatCrawlError(status.error_code, status.error_message || '平台同步失败')
        expanded.value = true
      } else if (status?.error_message) {
        // no-op
      }
      const finishedCandidates = []
      for (const row of Object.values(status?.platforms || {})) {
        const job = row?.last_job
        if (job?.finished_at) finishedCandidates.push(job.finished_at)
        else if (job?.created_at) finishedCandidates.push(job.created_at)
      }
      if (finishedCandidates.length) {
        finishedCandidates.sort()
        lastFinishedAt.value = finishedCandidates[finishedCandidates.length - 1]
      }
      return status
    } catch {
      return platformSyncStatus.value
    }
  }

  function shouldAutoSync(auth) {
    if (!auth?.backendLinked || auth.isWarehouse) return false
    if (sessionStorage.getItem(SESSION_SYNC_KEY) === '1') return false
    if (isPlatformCrawlInCooldown(auth)) return false
    return true
  }

  async function seedFromBackend(auth, { forceHydrate = false } = {}) {
    if (!auth?.backendLinked || auth.isWarehouse) return
    bindAuth(auth)
    try {
      await loadPlatformSyncStatus(auth)
      const nextItems = await buildPlatformSyncTargets(auth)
      updateItems(nextItems)
      const skipHydrate = !forceHydrate && isPlatformHydrateInCooldown(auth) && hasItems.value
      if (!skipHydrate) {
        await hydratePlatformSyncFromBackend(auth, nextItems)
        updateItems(nextItems)
        markPlatformHydrateCompleted(auth)
      }
    } catch {
      // best effort
    }
  }

  async function runSync(auth, { force = false } = {}) {
    if (!canUseOpsManualSync()) return
    if (running.value) return
    if (!auth?.backendLinked || auth.isWarehouse) return
    bindAuth(auth)

    if (!force && isPlatformCrawlInCooldown(auth)) {
      cooldownSkippedAt.value = nowUtc8String()
      lastError.value = `同步冷却中，${formatCooldownRemaining(getCooldownRemainingMs(auth))}后可再次同步`
      sessionStorage.setItem(SESSION_SYNC_KEY, '1')
      await loadPlatformSyncStatus(auth)
      return
    }

    running.value = true
    lastError.value = ''
    cooldownSkippedAt.value = ''
    try {
      const result = await runPlatformAutoSync(auth, {
        onProgress: updateItems,
        force,
      })
      updateItems(result.items || [])
      lastFinishedAt.value = nowUtc8String()
      if (result.cooldown) {
        lastError.value = result.message || lastError.value
      } else if (!result.skipped) {
        markPlatformHydrateCompleted(auth)
      }
      sessionStorage.setItem(SESSION_SYNC_KEY, '1')
      await loadPlatformSyncStatus(auth)
    } catch (err) {
      if (!/后端暂不可用|已跳过|进行中|冷却/i.test(err.message || '')) {
        lastError.value = err.message || '自动同步失败'
      }
    } finally {
      running.value = false
    }
  }

  async function runAutoSyncOnLogin(auth) {
    bindAuth(auth)
    await loadPlatformSyncStatus(auth)
    if (!shouldAutoSync(auth)) {
      if (isPlatformCrawlInCooldown(auth)) {
        cooldownSkippedAt.value = nowUtc8String()
      }
      sessionStorage.setItem(SESSION_SYNC_KEY, '1')
      return
    }
    // 打开应用：读库 + 展示全平台日批状态；不 force 爬（日批负责）
    await runSync(auth, { force: false })
  }

  async function retry(auth) {
    await runSync(auth, { force: true })
  }

  function resetSession() {
    sessionStorage.removeItem(SESSION_SYNC_KEY)
    items.value = []
    running.value = false
    lastFinishedAt.value = ''
    lastError.value = ''
    cooldownSkippedAt.value = ''
    platformSyncStatus.value = null
  }

  return {
    items,
    running,
    expanded,
    lastFinishedAt,
    lastError,
    cooldownSkippedAt,
    cooldownRemainingMs,
    inCooldown,
    cooldownHint,
    PLATFORM_SYNC_COOLDOWN_MS,
    hasItems,
    successCount,
    failedCount,
    skippedCount,
    syncingCount,
    summaryText,
    platformSyncStatus,
    scheduleText,
    platformStatusRows,
    // 兼容旧字段名
    temuSyncStatus: platformSyncStatus,
    temuScheduleText: scheduleText,
    loadPlatformSyncStatus,
    loadTemuSyncStatus: loadPlatformSyncStatus,
    updateStoreStatus,
    updateItems,
    runAutoSyncOnLogin,
    seedFromBackend,
    retry,
    resetSession,
    shouldAutoSync,
    bindAuth,
  }
})
