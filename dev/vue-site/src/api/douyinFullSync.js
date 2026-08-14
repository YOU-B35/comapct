export const FULL_SYNC_STEP_IDS = [
  'compass',
  'compass_product_rank',
  'opportunity',
  'products',
  'orders',
  'issues',
]

export const FULL_SYNC_STEP_LABELS = {
  compass: '数据罗盘',
  compass_product_rank: '罗盘商品榜',
  opportunity: '商机中心',
  products: '商品',
  orders: '订单',
  issues: '内容预警',
}

export async function runDouyinFullSync(ctx, runners, onProgress) {
  const results = []
  const total = FULL_SYNC_STEP_IDS.length
  for (let i = 0; i < total; i++) {
    const id = FULL_SYNC_STEP_IDS[i]
    const label = FULL_SYNC_STEP_LABELS[id] || id
    onProgress?.({ index: i, total, stepId: id, label, status: 'running' })
    const fn = runners[id]
    let row
    try {
      if (typeof fn !== 'function') throw new Error(`missing runner: ${id}`)
      const r = await fn(ctx)
      row = { id, ok: !!r?.ok, message: r?.message, error: r?.error }
    } catch (e) {
      row = { id, ok: false, error: e?.message || String(e) }
    }
    results.push(row)
    onProgress?.({
      index: i,
      total,
      stepId: id,
      label,
      status: row.ok ? 'success' : 'failed',
      message: row.message || null,
      error: row.error || null,
    })
  }
  const failed = results.filter((r) => !r.ok)
  const partial = failed.length > 0
  const message = partial
    ? `全量同步部分完成：失败 ${failed.map((f) => FULL_SYNC_STEP_LABELS[f.id] || f.id).join('、')}`
    : `全量同步完成（${total}/${total}）`
  return { partial, results, message }
}
