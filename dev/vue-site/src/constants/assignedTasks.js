/** 管理员分配任务 — 选项与 Demo 种子 */

export const TASK_CATEGORY_OPTIONS = ['库存', '订单', 'Listing', '定价', '运营', '采购', '客服', '合规', '其他']

export const TASK_PRIORITY_OPTIONS = [
  { value: 'high', label: '高', type: 'danger' },
  { value: 'medium', label: '中', type: 'warning' },
  { value: 'low', label: '低', type: 'info' },
]

export const TASK_DUE_OPTIONS = [
  '今天 18:00',
  '今天 20:00',
  '今天 23:59',
  '明天 12:00',
  '明天 18:00',
  '本周五',
]

export const TASK_PLATFORM_OPTIONS = [
  { value: 'temu', label: 'Temu' },
  { value: 'aliexpress', label: 'AliExpress' },
  { value: 'amazon', label: 'Amazon' },
  { value: 'walmart', label: 'Walmart' },
  { value: 'pdd', label: '拼多多' },
  { value: 'taobao', label: '淘宝' },
  { value: 'douyin', label: '抖音' },
  { value: 'channels', label: '视频号' },
  { value: '1688', label: '1688' },
  { value: 'dtc', label: '独立站' },
]

export const TASK_STATUS_OPTIONS = ['待处理', '进行中', '已完成', '已取消']

export const ASSIGNEE_TYPE_OPTIONS = [
  { value: 'employee', label: '运营人员' },
  { value: 'warehouse', label: '仓库管理员' },
]

export const WAREHOUSE_TASK_CATEGORY_OPTIONS = ['出库', '入库', '盘点', '拣货', '包装', '物流', '其他']

export const ASSIGNED_TASKS_SEED = [
  {
    id: 'assign_seed_1',
    assigneeType: 'employee',
    assigneeId: 'demo_emp_1',
    employeeId: 'demo_emp_1',
    assignee: '王一鸣',
    title: '整理 Temu 爆款通报材料并同步仓储',
    description: '碳纤维登山杖、轻量帐篷近 7 日增幅超 50%，需输出通报 PPT 并确认补货节奏。',
    platformKey: 'temu',
    category: '运营',
    priority: 'high',
    status: '进行中',
    progress: 60,
    due: '今天 20:00',
    assignedBy: '企业管理员',
    assignedAt: '2026-06-25 09:00:00',
    updatedAt: '2026-06-25 15:10:00',
    lastOutcome: 'in_progress',
    lastFeedback: '通报 PPT 初稿已完成 60%，已与仓储确认碳纤维登山杖补货节奏，预计今日 20:00 前提交终稿。',
    lastFeedbackAt: '2026-06-25 15:10:00',
    lastFeedbackBy: '王一鸣',
  },
  {
    id: 'assign_seed_2',
    assigneeType: 'employee',
    assigneeId: 'demo_emp_7',
    employeeId: 'demo_emp_7',
    assignee: '周婷',
    title: '跟进 Walmart 主图审核异常工单',
    description: '户外保温壶 Listing 未发布，需联系平台支持并同步处理结果。',
    platformKey: 'walmart',
    category: 'Listing',
    priority: 'high',
    status: '待处理',
    progress: 0,
    due: '今天 18:00',
    assignedBy: '企业管理员',
    assignedAt: '2026-06-25 10:30:00',
    updatedAt: '2026-06-25 10:30:00',
  },
  {
    id: 'assign_seed_wh_1',
    assigneeType: 'warehouse',
    assigneeId: 'wh_user_1',
    employeeId: 'wh_user_1',
    assignee: '张仓管',
    title: '泰州1号仓今日出库单优先复核',
    description: '运营侧有多笔加急出库，请在 18:00 前完成待审核订单复核并反馈异常。',
    platformKey: 'warehouse',
    category: '出库',
    priority: 'high',
    status: '待处理',
    progress: 0,
    due: '今天 18:00',
    warehouseName: '泰州1号仓',
    assignedBy: '企业管理员',
    assignedAt: '2026-06-25 11:00:00',
    updatedAt: '2026-06-25 11:00:00',
  },
]

export const PLATFORM_LABELS = {
  warehouse: '仓储作业',
  ...Object.fromEntries(TASK_PLATFORM_OPTIONS.map((item) => [item.value, item.label])),
}
