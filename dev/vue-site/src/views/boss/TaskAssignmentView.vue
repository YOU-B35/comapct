<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Bell, Delete, Grid, List, Plus, Refresh, View, WarningFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import {
  assignTask,
  assignTasksBatch,
  cancelAssignedTask,
  fetchAssignedTaskDetail,
  fetchAssignedTasks,
  nudgeAssignedTask,
  removeAssignedTask,
  updateAssignedTask,
} from '@/api/assignedTasks'
import { fetchEmployees } from '@/api/employees'
import { fetchWarehouseSites } from '@/api/warehouseSites'
import { fetchWarehouseStaff } from '@/api/warehouseStaff'
import { TASK_STATUS_META } from '@/constants/operations'
import { OUTCOME_MAP } from '@/constants/opsFeedbackDemo'
import {
  ASSIGNEE_TYPE_OPTIONS,
  TASK_CATEGORY_OPTIONS,
  TASK_PLATFORM_OPTIONS,
  TASK_PRIORITY_OPTIONS,
  TASK_STATUS_OPTIONS,
  WAREHOUSE_TASK_CATEGORY_OPTIONS,
  PLATFORM_LABELS,
} from '@/constants/assignedTasks'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import AssignedTaskDetailDrawer from '@/components/tasks/AssignedTaskDetailDrawer.vue'
import { fetchMyOpsTeam, fetchOpsTeams, fetchOpsTeamMembers } from '@/api/opsTeams'
import { DUE_SHORTCUTS, dueShortcut, formatDueDateTime, isTaskOverdue, parseTaskDue } from '@/utils/taskDue'

const props = defineProps({
  /** 部分主管：仅本组员工，不含仓库任务 */
  teamLeaderMode: { type: Boolean, default: false },
})

const auth = useAuthStore()
const loading = ref(false)
const employees = ref([])
const warehouseStaff = ref([])
const warehouseSites = ref([])
const opsTeams = ref([])
/** userId(string) -> { teamId, teamName } */
const userTeamMap = ref({})
const tasks = ref([])
const dialogVisible = ref(false)
const batchVisible = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const batchSubmitting = ref(false)
const nudgingId = ref('')
const editingId = ref(null)
/** list | board */
const viewMode = ref('list')
const filterAssigneeType = ref('all')
const filterAssigneeId = ref('all')
const filterStatus = ref('active')
const filterKeyword = ref('')
/** all | none | teamId */
const filterTeamId = ref('all')
const formTeamFilter = ref('all')
const batchTeamFilter = ref('all')
const activeTask = ref(null)
const activeFeedbacks = ref([])

const priorityMap = Object.fromEntries(TASK_PRIORITY_OPTIONS.map((item) => [item.value, item]))

const activeEmployees = computed(() => employees.value.filter((emp) => emp.status !== false))
const activeWarehouseStaff = computed(() => warehouseStaff.value.filter((item) => item.status !== false))
const activeOpsTeams = computed(() =>
  (opsTeams.value || []).filter((t) => String(t.status || 'active') === 'active'),
)

const teamFilterOptions = computed(() => {
  const opts = [
    { id: 'all', label: '全部小组' },
    { id: 'none', label: '未入组' },
  ]
  for (const t of activeOpsTeams.value) {
    opts.push({ id: String(t.id), label: t.name || `小组 ${t.id}` })
  }
  return opts
})

const formEmployeeOptions = computed(() => {
  let list = activeEmployees.value
  if (props.teamLeaderMode) return list
  if (form.assigneeType !== 'employee') return list
  if (formTeamFilter.value === 'all') return list
  if (formTeamFilter.value === 'none') {
    return list.filter((emp) => !userTeamMap.value[String(emp.id)])
  }
  const teamId = String(formTeamFilter.value)
  const team = activeOpsTeams.value.find((t) => String(t.id) === teamId)
  const memberIds = new Set((team?.memberUserIds || []).map(String))
  if (team?.leaderUserId != null) memberIds.add(String(team.leaderUserId))
  return list.filter((emp) => memberIds.has(String(emp.id)))
})

const assigneeFilterOptions = computed(() => {
  const options = [{ id: 'all', label: '全部负责人', type: 'all' }]
  for (const emp of activeEmployees.value) {
    const team = userTeamMap.value[String(emp.id)]
    const teamHint = team?.teamName ? ` · ${team.teamName}` : ''
    options.push({
      id: String(emp.id),
      label: `${emp.name} · ${emp.role || '运营'}${teamHint}`,
      type: 'employee',
    })
  }
  if (!props.teamLeaderMode) {
    for (const staff of activeWarehouseStaff.value) {
      options.push({
        id: String(staff.id),
        label: `${staff.name} · 仓库管理员`,
        type: 'warehouse',
      })
    }
  }
  return options
})

const filteredTasks = computed(() => {
  let list = tasks.value
  const kw = filterKeyword.value.trim().toLowerCase()
  if (kw) {
    list = list.filter(
      (task) =>
        String(task.title || '').toLowerCase().includes(kw)
        || String(task.description || '').toLowerCase().includes(kw)
        || String(task.assignee || '').toLowerCase().includes(kw),
    )
  }
  if (filterAssigneeType.value !== 'all') {
    list = list.filter((task) => (task.assigneeType || 'employee') === filterAssigneeType.value)
  }
  if (filterAssigneeId.value !== 'all') {
    list = list.filter((task) => String(task.assigneeId || task.employeeId) === String(filterAssigneeId.value))
  }
  if (!props.teamLeaderMode && filterTeamId.value !== 'all') {
    list = list.filter((task) => matchTeamFilter(task, filterTeamId.value))
  }
  if (filterStatus.value === 'active') {
    list = list.filter((task) => task.status !== '已完成' && task.status !== '已取消')
  } else if (filterStatus.value === 'need_help') {
    list = list.filter((task) => rowNeedsAttention(task))
  } else if (filterStatus.value === 'overdue') {
    list = list.filter((task) => isTaskOverdue(task))
  } else if (filterStatus.value === 'nudged') {
    list = list.filter((task) => isTaskNudged(task))
  } else if (filterStatus.value !== 'all') {
    list = list.filter((task) => task.status === filterStatus.value)
  }
  return list
})

const stats = computed(() => ({
  total: tasks.value.length,
  active: tasks.value.filter((t) => t.status !== '已完成' && t.status !== '已取消').length,
  done: tasks.value.filter((t) => t.status === '已完成').length,
  needHelp: tasks.value.filter((t) => rowNeedsAttention(t)).length,
  overdue: tasks.value.filter((t) => isTaskOverdue(t)).length,
  nudged: tasks.value.filter((t) => isTaskNudged(t)).length,
}))

const boardColumns = computed(() => {
  const base = filteredTasks.value
  return [
    {
      key: 'todo',
      title: '待处理',
      items: base.filter((t) => t.status === '待处理' && !isTaskOverdue(t) && !rowNeedsAttention(t)),
    },
    {
      key: 'doing',
      title: '进行中',
      items: base.filter((t) => t.status === '进行中' && !isTaskOverdue(t) && !rowNeedsAttention(t)),
    },
    {
      key: 'help',
      title: '需协助',
      items: base.filter((t) => rowNeedsAttention(t)),
    },
    {
      key: 'overdue',
      title: '已逾期',
      items: base.filter((t) => isTaskOverdue(t)),
    },
    {
      key: 'done',
      title: '已完成',
      items: base.filter((t) => t.status === '已完成'),
    },
  ]
})

const form = reactive({
  assigneeType: 'employee',
  assigneeId: '',
  title: '',
  description: '',
  platformKey: 'temu',
  category: '运营',
  priority: 'medium',
  due: dueShortcut('today18'),
  warehouseName: '',
})

const batchForm = reactive({
  assigneeType: 'employee',
  assigneeIds: [],
  title: '',
  description: '',
  platformKey: 'temu',
  category: '运营',
  priority: 'medium',
  due: dueShortcut('today18'),
  warehouseName: '',
})

const batchEmployeeOptions = computed(() => {
  let list = activeEmployees.value
  if (props.teamLeaderMode) return list
  if (batchTeamFilter.value === 'all') return list
  if (batchTeamFilter.value === 'none') {
    return list.filter((emp) => !userTeamMap.value[String(emp.id)])
  }
  const team = activeOpsTeams.value.find((t) => String(t.id) === String(batchTeamFilter.value))
  const memberIds = new Set((team?.memberUserIds || []).map(String))
  if (team?.leaderUserId != null) memberIds.add(String(team.leaderUserId))
  return list.filter((emp) => memberIds.has(String(emp.id)))
})

const formRules = computed(() => ({
  assigneeId: [{ required: true, message: '请选择负责人', trigger: 'change' }],
  title: [{ required: true, message: '请填写任务标题', trigger: 'blur' }],
  due: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
  platformKey: form.assigneeType === 'employee'
    ? [{ required: true, message: '请选择平台', trigger: 'change' }]
    : [],
}))

const categoryOptions = computed(() =>
  form.assigneeType === 'warehouse' ? WAREHOUSE_TASK_CATEGORY_OPTIONS : TASK_CATEGORY_OPTIONS,
)

const selectedWarehouseStaff = computed(() =>
  activeWarehouseStaff.value.find((item) => String(item.id) === String(form.assigneeId)),
)

const warehouseNameOptions = computed(() => {
  const staff = selectedWarehouseStaff.value
  if (!staff?.warehouseIds?.length) return []
  const nameMap = Object.fromEntries(warehouseSites.value.map((site) => [site.id, site.name]))
  return staff.warehouseIds.map((id) => nameMap[id] || id)
})

const formRef = ref(null)
const dialogTitle = computed(() => (editingId.value ? '编辑任务' : '分配任务'))

watch(formTeamFilter, () => {
  if (form.assigneeType !== 'employee') return
  const still = formEmployeeOptions.value.some((e) => String(e.id) === String(form.assigneeId))
  if (!still) {
    form.assigneeId = formEmployeeOptions.value[0]?.id || ''
  }
})

function matchTeamFilter(task, teamFilter) {
  if ((task.assigneeType || 'employee') === 'warehouse') {
    return teamFilter === 'none' ? false : teamFilter === 'all'
  }
  const uid = String(task.assigneeId || task.employeeId || '')
  const meta = userTeamMap.value[uid]
  if (teamFilter === 'none') return !meta
  return meta && String(meta.teamId) === String(teamFilter)
}

function buildUserTeamMap(teams) {
  const map = {}
  for (const t of teams || []) {
    if (String(t.status || 'active') !== 'active') continue
    const teamId = t.id
    const teamName = t.name || `小组 ${teamId}`
    if (t.leaderUserId != null) {
      map[String(t.leaderUserId)] = { teamId, teamName }
    }
    for (const mid of t.memberUserIds || []) {
      map[String(mid)] = { teamId, teamName }
    }
  }
  userTeamMap.value = map
}

function teamNameOfUser(userId) {
  return userTeamMap.value[String(userId)]?.teamName || ''
}

function resetForm() {
  form.assigneeType = 'employee'
  formTeamFilter.value = 'all'
  form.assigneeId = activeEmployees.value[0]?.id || activeWarehouseStaff.value[0]?.id || ''
  if (activeEmployees.value[0]?.id) form.assigneeType = 'employee'
  else if (!props.teamLeaderMode && activeWarehouseStaff.value[0]?.id) form.assigneeType = 'warehouse'
  form.title = ''
  form.description = ''
  form.platformKey = 'temu'
  form.category = '运营'
  form.priority = 'medium'
  form.due = dueShortcut('today18')
  form.warehouseName = ''
  editingId.value = null
  formRef.value?.clearValidate?.()
}

function onAssigneeTypeChange() {
  formTeamFilter.value = 'all'
  form.assigneeId = form.assigneeType === 'warehouse'
    ? (activeWarehouseStaff.value[0]?.id || '')
    : (formEmployeeOptions.value[0]?.id || '')
  form.category = form.assigneeType === 'warehouse' ? '出库' : '运营'
  form.warehouseName = warehouseNameOptions.value[0] || ''
}

function openEdit(row) {
  editingId.value = row.id
  form.assigneeType = row.assigneeType || 'employee'
  form.assigneeId = row.assigneeId || row.employeeId
  form.title = row.title
  form.description = row.description || ''
  form.platformKey = row.platformKey
  form.category = row.category
  form.priority = row.priority
  {
    const parsed = parseTaskDue(row.due)
    form.due = parsed ? formatDueDateTime(parsed) : dueShortcut('today18')
  }
  form.warehouseName = row.warehouseName || ''
  const team = userTeamMap.value[String(form.assigneeId)]
  formTeamFilter.value = team ? String(team.teamId) : 'all'
  dialogVisible.value = true
}

async function openDetail(row) {
  try {
    const res = await fetchAssignedTaskDetail(row.id, auth)
    activeTask.value = res.data.task
    activeFeedbacks.value = res.data.feedbacks
    detailVisible.value = true
  } catch (err) {
    ElMessage.error(err.message || '加载详情失败')
  }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openBatch() {
  batchTeamFilter.value = 'all'
  batchForm.assigneeType = 'employee'
  batchForm.assigneeIds = []
  batchForm.title = ''
  batchForm.description = ''
  batchForm.platformKey = 'temu'
  batchForm.category = '运营'
  batchForm.priority = 'medium'
  batchForm.due = dueShortcut('today18')
  batchForm.warehouseName = ''
  batchVisible.value = true
}

watch(batchTeamFilter, () => {
  const allowed = new Set(batchEmployeeOptions.value.map((e) => String(e.id)))
  batchForm.assigneeIds = batchForm.assigneeIds.filter((id) => allowed.has(String(id)))
})

function onAssigneeChange(assigneeId) {
  if (form.assigneeType === 'employee') {
    onEmployeeChange(assigneeId)
    return
  }
  form.warehouseName = warehouseNameOptions.value[0] || ''
}

function onEmployeeChange(employeeId) {
  const employee = activeEmployees.value.find((emp) => String(emp.id) === String(employeeId))
  if (!employee?.platforms?.length) return
  if (!employee.platforms.includes(form.platformKey)) {
    const key = employee.platforms[0]
    form.platformKey = key === 'shopify' || key === 'wordpress' ? 'dtc' : key
  }
}

function applyDueShortcut(key) {
  form.due = dueShortcut(key)
}

function latestFeedbackLabel(task) {
  if (!task.lastOutcome) return ''
  return OUTCOME_MAP[task.lastOutcome]?.label || ''
}

function rowNeedsAttention(row) {
  if (row.status === '已完成' || row.status === '已取消') return false
  return row.lastOutcome === 'need_help' || row.lastOutcome === 'blocked'
}

function isTaskNudged(row) {
  if (!row) return false
  if (row.status === '已完成' || row.status === '已取消') return false
  return Boolean(String(row.nudgedAt || '').trim())
}

function assigneeTypeLabel(type) {
  return ASSIGNEE_TYPE_OPTIONS.find((item) => item.value === (type || 'employee'))?.label || '运营人员'
}

function platformLabel(row) {
  return PLATFORM_LABELS[row.platformKey] || row.platformKey
}

function tableRowClass({ row }) {
  if (isTaskOverdue(row)) return 'is-overdue-row'
  if (isTaskNudged(row)) return 'is-nudged-row'
  if (rowNeedsAttention(row)) return 'is-attention-row'
  return ''
}

async function loadBossTeams() {
  const teams = await fetchOpsTeams()
  const list = Array.isArray(teams) ? teams : []
  // 若后端尚未带 memberUserIds，按组补拉成员
  const enriched = await Promise.all(
    list.map(async (t) => {
      if (Array.isArray(t.memberUserIds)) return t
      if (String(t.status || 'active') !== 'active') {
        return { ...t, memberUserIds: [] }
      }
      try {
        const members = await fetchOpsTeamMembers(t.id)
        return {
          ...t,
          memberUserIds: (members || []).map((m) => m.userId).filter((id) => id != null),
        }
      } catch {
        return { ...t, memberUserIds: [] }
      }
    }),
  )
  opsTeams.value = enriched
  buildUserTeamMap(enriched)
}

async function loadData() {
  loading.value = true
  try {
    if (props.teamLeaderMode) {
      const [team, taskRes] = await Promise.all([
        fetchMyOpsTeam(),
        fetchAssignedTasks({}, auth),
      ])
      const members = Array.isArray(team?.members) ? team.members : []
      const selfId = auth.backendUserId || auth.employee?.id
      const selfName = auth.employee?.name || auth.displayName || '我'
      const list = members.map((m) => ({
        id: String(m.userId),
        name: m.name,
        role: m.role || '运营',
        status: m.status !== false,
        platforms: m.platforms || [],
      }))
      if (selfId && !list.some((e) => String(e.id) === String(selfId))) {
        list.unshift({ id: String(selfId), name: selfName, role: '主管', status: true, platforms: [] })
      }
      employees.value = list
      warehouseStaff.value = []
      warehouseSites.value = []
      opsTeams.value = team
        ? [{
            id: team.id,
            name: team.name,
            status: 'active',
            leaderUserId: team.leaderUserId,
            memberUserIds: members.map((m) => m.userId),
          }]
        : []
      buildUserTeamMap(opsTeams.value)
      tasks.value = (taskRes.data || []).map((t) => ({
        ...t,
        assigneeId: t.assigneeId != null ? String(t.assigneeId) : t.assigneeId,
      }))
      form.assigneeType = 'employee'
    } else {
      const [empRes, staffRes, sitesRes, taskRes] = await Promise.all([
        fetchEmployees(auth),
        fetchWarehouseStaff(auth),
        fetchWarehouseSites(auth, { activeOnly: true }),
        fetchAssignedTasks({}, auth),
      ])
      employees.value = (empRes.data || []).map((e) => ({ ...e, id: String(e.id) }))
      warehouseStaff.value = (staffRes.data || []).map((s) => ({ ...s, id: String(s.id) }))
      warehouseSites.value = sitesRes.data || []
      tasks.value = (taskRes.data || []).map((t) => ({
        ...t,
        assigneeId: t.assigneeId != null ? String(t.assigneeId) : t.assigneeId,
      }))
      try {
        await loadBossTeams()
      } catch {
        opsTeams.value = []
        userTeamMap.value = {}
      }
    }
  } catch {
    employees.value = []
    warehouseStaff.value = []
    warehouseSites.value = []
    tasks.value = []
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const assignee = form.assigneeType === 'warehouse'
      ? activeWarehouseStaff.value.find((item) => String(item.id) === String(form.assigneeId))
      : activeEmployees.value.find((item) => String(item.id) === String(form.assigneeId))
    if (!assignee) {
      ElMessage.error('请选择有效的负责人')
      return
    }
    const dueText = parseTaskDue(form.due) ? form.due : formatDueDateTime(new Date(form.due))
    const actorName = auth.displayName || auth.employee?.name || '企业管理员'
    const payload = {
      assigneeType: form.assigneeType,
      assigneeId: String(form.assigneeId),
      assignee: assignee.name,
      title: form.title.trim(),
      description: form.description.trim(),
      platformKey: form.assigneeType === 'warehouse' ? 'warehouse' : form.platformKey,
      category: form.category,
      priority: form.priority,
      due: dueText || form.due,
      warehouseName: form.warehouseName,
      assignedBy: actorName,
    }
    if (editingId.value) {
      await updateAssignedTask(editingId.value, {
        assigneeType: form.assigneeType,
        assigneeId: payload.assigneeId,
        employeeId: payload.assigneeId,
        assignee: assignee.name,
        title: payload.title,
        description: payload.description,
        platformKey: payload.platformKey,
        category: form.category,
        priority: form.priority,
        due: payload.due,
        warehouseName: form.warehouseName,
      }, auth)
      ElMessage.success('任务已更新')
      dialogVisible.value = false
      await loadData()
    } else {
      const res = await assignTask(payload, {
        employees: employees.value,
        warehouseStaff: warehouseStaff.value,
      }, auth)
      ElMessage.success(`任务已分配给 ${assignee.name}`)
      dialogVisible.value = false
      await loadData()
      if (res.data?.id) {
        await openDetail(res.data)
      }
    }
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function submitBatch() {
  if (!batchForm.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  if (!batchForm.assigneeIds.length) {
    ElMessage.warning('请至少选择一个负责人')
    return
  }
  batchSubmitting.value = true
  try {
    const assignees = batchForm.assigneeIds.map((id) => {
      const emp = activeEmployees.value.find((e) => String(e.id) === String(id))
      return {
        assigneeType: 'employee',
        assigneeId: String(id),
        assignee: emp?.name || String(id),
      }
    })
    const actorName = auth.displayName || auth.employee?.name || '企业管理员'
    const res = await assignTasksBatch({
      title: batchForm.title.trim(),
      description: batchForm.description.trim(),
      platformKey: batchForm.platformKey,
      category: batchForm.category,
      priority: batchForm.priority,
      due: batchForm.due,
      assignedBy: actorName,
      assigneeType: 'employee',
      assignees,
    }, auth)
    const ok = res.data?.successCount || 0
    const fail = res.data?.failCount || 0
    if (fail) {
      ElMessage.warning(`批量完成：成功 ${ok}，失败 ${fail}`)
    } else {
      ElMessage.success(`已批量分配 ${ok} 条任务`)
    }
    batchVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message || '批量分配失败')
  } finally {
    batchSubmitting.value = false
  }
}

async function handleNudge(row) {
  if (row.status === '已完成' || row.status === '已取消') return
  nudgingId.value = row.id
  try {
    await nudgeAssignedTask(row.id, auth)
    ElMessage.success('已催办，负责人任务列表将高亮显示')
    await loadData()
  } catch (err) {
    ElMessage.error(err.message || '催办失败')
  } finally {
    nudgingId.value = ''
  }
}

async function handleCancel(row) {
  try {
    await ElMessageBox.confirm(`确定取消任务「${row.title}」？`, '取消任务', { type: 'warning' })
    await cancelAssignedTask(row.id, auth)
    ElMessage.success('任务已取消')
    detailVisible.value = false
    await loadData()
  } catch {
    /* user dismissed */
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除任务「${row.title}」？`, '删除任务', { type: 'warning' })
    await removeAssignedTask(row.id, auth)
    ElMessage.success('任务已删除')
    detailVisible.value = false
    await loadData()
  } catch {
    /* user dismissed */
  }
}

onMounted(loadData)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        :title="teamLeaderMode ? '任务分配（本组）' : '任务分配'"
        eyebrow="协作"
        :description="
          teamLeaderMode
            ? '向本组员工（含自己）指派任务并跟踪进度'
            : '向运营人员或仓库管理员指派任务；支持按运营小组筛选、逾期关注'
        "
      >
        <template #actions>
          <el-button-group class="view-switch">
            <el-button :type="viewMode === 'list' ? 'primary' : 'default'" :icon="List" @click="viewMode = 'list'">
              列表
            </el-button>
            <el-button :type="viewMode === 'board' ? 'primary' : 'default'" :icon="Grid" @click="viewMode = 'board'">
              看板
            </el-button>
          </el-button-group>
          <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
          <el-button @click="openBatch">批量分配</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">分配任务</el-button>
        </template>
      </PageHeader>
    </template>

    <div v-loading="loading" class="assign-page">
      <PageSection title="概览">
      <div class="metrics-bar metrics-bar--5">
        <div class="metric-item">
          <div class="metric-value">{{ stats.total }}</div>
          <div class="metric-label">全部分配</div>
        </div>
        <div class="metric-item">
          <div class="metric-value is-warning">{{ stats.active }}</div>
          <div class="metric-label">进行中</div>
        </div>
        <div class="metric-item is-clickable" @click="filterStatus = 'need_help'">
          <div class="metric-value is-danger">{{ stats.needHelp }}</div>
          <div class="metric-label">需协助</div>
        </div>
        <div class="metric-item is-clickable" @click="filterStatus = 'overdue'">
          <div class="metric-value is-danger">{{ stats.overdue }}</div>
          <div class="metric-label">已逾期</div>
        </div>
        <div class="metric-item is-clickable" @click="filterStatus = 'nudged'">
          <div class="metric-value is-warning">{{ stats.nudged }}</div>
          <div class="metric-label">已催办</div>
        </div>
      </div>
      </PageSection>

      <PageSection title="筛选与任务">
      <div class="filter-bar">
        <el-input
          v-model="filterKeyword"
          clearable
          size="small"
          placeholder="搜索标题 / 说明 / 负责人"
          style="width: 220px"
        />
        <el-select
          v-if="!teamLeaderMode"
          v-model="filterTeamId"
          placeholder="运营小组"
          style="width: 150px"
          size="small"
        >
          <el-option v-for="item in teamFilterOptions" :key="item.id" :label="item.label" :value="item.id" />
        </el-select>
        <el-select
          v-if="!teamLeaderMode"
          v-model="filterAssigneeType"
          placeholder="负责人类型"
          style="width: 130px"
          size="small"
        >
          <el-option label="全部类型" value="all" />
          <el-option
            v-for="item in ASSIGNEE_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="filterAssigneeId" placeholder="负责人" style="width: 200px" size="small">
          <el-option label="全部负责人" value="all" />
          <el-option
            v-for="item in assigneeFilterOptions.filter((opt) => opt.id !== 'all')"
            :key="`${item.type}-${item.id}`"
            :label="item.label"
            :value="item.id"
          />
        </el-select>
        <el-select v-model="filterStatus" placeholder="状态" style="width: 130px" size="small">
          <el-option label="进行中" value="active" />
          <el-option label="需协助" value="need_help" />
          <el-option label="已逾期" value="overdue" />
          <el-option label="已催办" value="nudged" />
          <el-option label="全部状态" value="all" />
          <el-option v-for="status in TASK_STATUS_OPTIONS" :key="status" :label="status" :value="status" />
        </el-select>
      </div>

      <el-empty v-if="!loading && !filteredTasks.length" description="暂无分配任务" :image-size="88">
        <el-button type="primary" :icon="Plus" @click="openCreate">分配第一个任务</el-button>
      </el-empty>

      <div v-else-if="viewMode === 'board'" class="task-board">
        <div v-for="col in boardColumns" :key="col.key" class="board-col">
          <header class="board-col__head">
            <strong>{{ col.title }}</strong>
            <el-tag size="small" effect="plain">{{ col.items.length }}</el-tag>
          </header>
          <div class="board-col__body">
            <button
              v-for="row in col.items"
              :key="row.id"
              type="button"
              class="board-card"
              :class="{ 'is-nudged': isTaskNudged(row), 'is-overdue': isTaskOverdue(row) }"
              @click="openDetail(row)"
            >
              <div class="board-card__title">
                {{ row.title }}
                <el-tag v-if="isTaskNudged(row)" type="warning" size="small" effect="plain">催办</el-tag>
              </div>
              <div class="board-card__meta">{{ row.assignee }} · {{ row.due || '—' }}</div>
              <div class="board-card__tags">
                <el-tag size="small" :type="priorityMap[row.priority]?.type || 'info'">
                  {{ priorityMap[row.priority]?.label || '中' }}
                </el-tag>
                <el-tag size="small" effect="plain">
                  {{ row.assigneeType === 'warehouse' ? (row.warehouseName || '仓储') : platformLabel(row) }}
                </el-tag>
              </div>
            </button>
            <el-empty v-if="!col.items.length" description="暂无" :image-size="48" />
          </div>
        </div>
      </div>

      <el-table
        v-else
        :data="filteredTasks"
        stripe
        size="small"
        class="task-table"
        :row-class-name="tableRowClass"
      >
        <el-table-column label="任务" min-width="220">
          <template #default="{ row }">
            <div class="task-title">
              {{ row.title }}
              <el-tag v-if="isTaskOverdue(row)" type="danger" size="small" effect="plain" class="overdue-tag">
                逾期
              </el-tag>
              <el-tag v-if="isTaskNudged(row)" type="warning" size="small" effect="plain">催办</el-tag>
            </div>
            <div v-if="row.description" class="task-desc">{{ row.description }}</div>
          </template>
        </el-table-column>
        <el-table-column label="负责人" width="140">
          <template #default="{ row }">
            <div>{{ row.assignee }}</div>
            <div class="task-desc">
              {{ assigneeTypeLabel(row.assigneeType) }}
              <template v-if="(row.assigneeType || 'employee') === 'employee' && teamNameOfUser(row.assigneeId)">
                · {{ teamNameOfUser(row.assigneeId) }}
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="范围" width="110">
          <template #default="{ row }">
            {{ row.assigneeType === 'warehouse' ? (row.warehouseName || '仓储作业') : platformLabel(row) }}
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类型" width="80" />
        <el-table-column label="优先级" width="72" align="center">
          <template #default="{ row }">
            <el-tag :type="priorityMap[row.priority]?.type || 'info'" size="small">
              {{ priorityMap[row.priority]?.label || '中' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最新反馈" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.lastFeedback">
              <el-tag
                v-if="latestFeedbackLabel(row)"
                size="small"
                :type="OUTCOME_MAP[row.lastOutcome]?.type || 'info'"
                effect="plain"
                style="margin-right: 6px"
              >
                {{ latestFeedbackLabel(row) }}
              </el-tag>
              <span class="feedback-snippet">{{ row.lastFeedback }}</span>
            </template>
            <el-text v-else type="info" size="small">待负责人反馈</el-text>
          </template>
        </el-table-column>
        <el-table-column prop="due" label="截止" width="140" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-space :size="4">
              <el-tag :type="TASK_STATUS_META[row.status]?.type || 'info'" size="small">
                {{ row.status }}
              </el-tag>
              <el-icon
                v-if="rowNeedsAttention(row)"
                class="need-help-icon"
                color="var(--el-color-warning)"
              >
                <WarningFilled />
              </el-icon>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="assignedAt" label="分配时间" width="150" />
        <el-table-column label="操作" width="230" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :icon="View" @click="openDetail(row)">
              详情
            </el-button>
            <el-button
              v-if="row.status !== '已完成' && row.status !== '已取消'"
              link
              type="warning"
              size="small"
              :icon="Bell"
              :loading="nudgingId === row.id"
              @click="handleNudge(row)"
            >
              催办
            </el-button>
            <el-button
              v-if="row.status !== '已完成' && row.status !== '已取消'"
              link
              type="primary"
              size="small"
              @click="openEdit(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="row.status !== '已完成' && row.status !== '已取消'"
              link
              type="warning"
              size="small"
              @click="handleCancel(row)"
            >
              取消
            </el-button>
            <el-button link type="danger" size="small" :icon="Delete" @click="handleDelete(row)" />
          </template>
        </el-table-column>
      </el-table>
      </PageSection>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="96px">
        <el-form-item v-if="!teamLeaderMode" label="负责人类型">
          <el-radio-group v-model="form.assigneeType" @change="onAssigneeTypeChange">
            <el-radio v-for="item in ASSIGNEE_TYPE_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item
          v-if="!teamLeaderMode && form.assigneeType === 'employee'"
          label="按小组"
        >
          <el-select v-model="formTeamFilter" style="width: 100%" placeholder="筛选可选负责人">
            <el-option label="全部员工" value="all" />
            <el-option label="未入组" value="none" />
            <el-option
              v-for="t in activeOpsTeams"
              :key="t.id"
              :label="t.name"
              :value="String(t.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人" prop="assigneeId">
          <el-select
            v-model="form.assigneeId"
            placeholder="选择负责人"
            style="width: 100%"
            filterable
            @change="onAssigneeChange"
          >
            <template v-if="form.assigneeType === 'warehouse'">
              <el-option
                v-for="staff in activeWarehouseStaff"
                :key="staff.id"
                :label="`${staff.name}（仓库管理员）`"
                :value="staff.id"
              />
            </template>
            <template v-else>
              <el-option
                v-for="emp in formEmployeeOptions"
                :key="emp.id"
                :label="`${emp.name}（${emp.role || '运营'}${teamNameOfUser(emp.id) ? ' · ' + teamNameOfUser(emp.id) : ''}）`"
                :value="emp.id"
              />
            </template>
          </el-select>
        </el-form-item>
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="form.title" placeholder="简明描述需完成的事项" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="补充背景、要求或验收标准"
          />
        </el-form-item>
        <el-form-item v-if="form.assigneeType === 'employee'" label="关联平台" prop="platformKey">
          <el-select v-model="form.platformKey" style="width: 100%">
            <el-option
              v-for="item in TASK_PLATFORM_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="关联仓库">
          <el-select v-model="form.warehouseName" placeholder="选填，默认不限定" clearable style="width: 100%">
            <el-option v-for="name in warehouseNameOptions" :key="name" :label="name" :value="name" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务类型">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="item in categoryOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="form.priority">
            <el-radio v-for="item in TASK_PRIORITY_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止时间" prop="due">
          <div class="due-field">
            <el-date-picker
              v-model="form.due"
              type="datetime"
              placeholder="选择日期时间"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm"
              style="width: 100%"
            />
            <div class="due-shortcuts">
              <el-button
                v-for="item in DUE_SHORTCUTS"
                :key="item.key"
                size="small"
                text
                type="primary"
                @click="applyDueShortcut(item.key)"
              >
                {{ item.label }}
              </el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ editingId ? '保存' : '确认分配' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="batchVisible"
      title="批量分配任务"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="96px">
        <el-form-item v-if="!teamLeaderMode" label="按小组">
          <el-select v-model="batchTeamFilter" style="width: 100%">
            <el-option label="全部员工" value="all" />
            <el-option label="未入组" value="none" />
            <el-option
              v-for="t in activeOpsTeams"
              :key="t.id"
              :label="t.name"
              :value="String(t.id)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人" required>
          <el-select
            v-model="batchForm.assigneeIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="可多选"
            style="width: 100%"
          >
            <el-option
              v-for="emp in batchEmployeeOptions"
              :key="emp.id"
              :label="`${emp.name}（${emp.role || '运营'}）`"
              :value="emp.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="任务标题" required>
          <el-input v-model="batchForm.title" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="任务说明">
          <el-input v-model="batchForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="关联平台">
          <el-select v-model="batchForm.platformKey" style="width: 100%">
            <el-option
              v-for="item in TASK_PLATFORM_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="任务类型">
          <el-select v-model="batchForm.category" style="width: 100%">
            <el-option v-for="item in TASK_CATEGORY_OPTIONS" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="batchForm.priority">
            <el-radio v-for="item in TASK_PRIORITY_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="batchForm.due"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchSubmitting" @click="submitBatch">确认批量分配</el-button>
      </template>
    </el-dialog>

    <AssignedTaskDetailDrawer
      v-model="detailVisible"
      :task="activeTask"
      :feedbacks="activeFeedbacks"
    />
  </PageScroll>
</template>

<style scoped>
.assign-page {
  display: grid;
  gap: 16px;
}

.metrics-bar--5 {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.metric-item {
  cursor: default;
}

.metric-item.is-clickable {
  cursor: pointer;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.task-table {
  border-radius: var(--ch-radius-lg);
}

.task-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.task-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ch-text-muted);
  line-height: 1.4;
}

.feedback-snippet {
  font-size: 12px;
  color: var(--ch-text-secondary);
}

.need-help-icon {
  font-size: 14px;
}

.overdue-tag {
  font-weight: 500;
}

:deep(.is-overdue-row) > td {
  background: color-mix(in srgb, var(--el-color-danger) 8%, transparent) !important;
}

:deep(.is-attention-row) > td {
  background: color-mix(in srgb, var(--el-color-warning) 7%, transparent) !important;
}

:deep(.is-nudged-row) > td {
  background: color-mix(in srgb, var(--el-color-warning) 10%, transparent) !important;
}

.due-field {
  width: 100%;
  display: grid;
  gap: 6px;
}

.due-shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.view-switch {
  margin-right: 4px;
}

.task-board {
  display: grid;
  grid-template-columns: repeat(5, minmax(180px, 1fr));
  gap: 12px;
  overflow-x: auto;
  align-items: start;
}

.board-col {
  background: var(--ch-surface-muted, #f5f7fa);
  border-radius: var(--ch-radius-lg, 10px);
  padding: 10px;
  min-height: 280px;
}

.board-col__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-size: 13px;
}

.board-col__body {
  display: grid;
  gap: 8px;
}

.board-card {
  text-align: left;
  border: 1px solid var(--ch-border, #e5e7eb);
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  display: grid;
  gap: 6px;
}

.board-card:hover {
  border-color: var(--el-color-primary-light-5);
}

.board-card.is-nudged {
  border-color: var(--el-color-warning-light-5);
  background: color-mix(in srgb, var(--el-color-warning) 8%, #fff);
}

.board-card.is-overdue {
  border-color: var(--el-color-danger-light-5);
}

.board-card__title {
  font-size: 13px;
  font-weight: 600;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.board-card__meta {
  font-size: 12px;
  color: var(--ch-text-muted, #909399);
}

.board-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

@media (max-width: 1100px) {
  .task-board {
    grid-template-columns: repeat(5, minmax(200px, 1fr));
  }
}
</style>
