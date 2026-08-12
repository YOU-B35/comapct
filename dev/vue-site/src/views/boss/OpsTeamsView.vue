<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import { fetchEmployees } from '@/api/employees'
import {
  addOpsTeamMember,
  archiveOpsTeam,
  createOpsTeam,
  fetchOpsTeamMembers,
  fetchOpsTeams,
  fetchUnassignedEmployees,
  removeOpsTeamMember,
  updateOpsTeam,
} from '@/api/opsTeams'

const loading = ref(false)
const teams = ref([])
const employees = ref([])
const unassigned = ref([])
const dialogVisible = ref(false)
const memberDialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const activeTeam = ref(null)
const members = ref([])
const addUserId = ref(null)

const form = reactive({
  name: '',
  leaderUserId: null,
})

async function load() {
  loading.value = true
  try {
    const [teamRows, empRows, freeRows] = await Promise.all([
      fetchOpsTeams(),
      fetchEmployees(),
      fetchUnassignedEmployees(),
    ])
    teams.value = Array.isArray(teamRows) ? teamRows : []
    employees.value = (Array.isArray(empRows) ? empRows : []).filter((e) => e.status !== false)
    unassigned.value = Array.isArray(freeRows) ? freeRows : []
  } catch (e) {
    ElMessage.error(e?.message || '加载运营小组失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.leaderUserId = null
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name || ''
  form.leaderUserId = row.leaderUserId
  dialogVisible.value = true
}

async function submitTeam() {
  if (!form.name?.trim()) {
    ElMessage.warning('请填写小组名称')
    return
  }
  if (!form.leaderUserId) {
    ElMessage.warning('请选择主管')
    return
  }
  submitting.value = true
  try {
    if (editingId.value) {
      await updateOpsTeam(editingId.value, {
        name: form.name.trim(),
        leaderUserId: form.leaderUserId,
      })
      ElMessage.success('已更新小组')
    } else {
      await createOpsTeam({
        name: form.name.trim(),
        leaderUserId: form.leaderUserId,
      })
      ElMessage.success('已创建小组（指定员工已升级为部分主管）')
    }
    dialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function onArchive(row) {
  try {
    await ElMessageBox.confirm(`确认归档「${row.name}」？组员将释放，主管降级。`, '归档小组', {
      type: 'warning',
    })
    await archiveOpsTeam(row.id)
    ElMessage.success('已归档')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.message || '归档失败')
  }
}

async function openMembers(row) {
  activeTeam.value = row
  addUserId.value = null
  memberDialogVisible.value = true
  try {
    members.value = await fetchOpsTeamMembers(row.id)
    unassigned.value = await fetchUnassignedEmployees()
  } catch (e) {
    ElMessage.error(e?.message || '加载成员失败')
  }
}

async function onAddMember() {
  if (!activeTeam.value || !addUserId.value) return
  try {
    await addOpsTeamMember(activeTeam.value.id, addUserId.value)
    ElMessage.success('已加入小组')
    members.value = await fetchOpsTeamMembers(activeTeam.value.id)
    unassigned.value = await fetchUnassignedEmployees()
    addUserId.value = null
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '加人失败')
  }
}

async function onRemoveMember(userId) {
  if (!activeTeam.value) return
  try {
    await removeOpsTeamMember(activeTeam.value.id, userId)
    ElMessage.success('已移出')
    members.value = await fetchOpsTeamMembers(activeTeam.value.id)
    unassigned.value = await fetchUnassignedEmployees()
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '移出失败')
  }
}

const leaderOptions = () => {
  // 创建时：未入组且非其他组主管；编辑时额外包含当前主管
  const currentLeader = editingId.value
    ? employees.value.find((e) => e.id === form.leaderUserId)
    : null
  const free = unassigned.value.slice()
  if (currentLeader && !free.some((e) => e.id === currentLeader.id)) {
    free.unshift(currentLeader)
  }
  // also allow any employee not leading another active team: use unassigned + current
  return free.length ? free : employees.value
}

onMounted(load)
</script>

<template>
  <PageScroll>
    <PageHeader
      title="运营小组"
      eyebrow="团队"
      description="创建小组并指定主管，将员工升级为部分主管，管理其组员与任务"
    >
      <template #actions>
        <el-button type="primary" @click="openCreate">新建小组</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </template>
    </PageHeader>
    <PageSection flush>
    <el-table v-loading="loading" :data="teams" stripe>
      <el-table-column prop="name" label="小组" min-width="140" />
      <el-table-column label="主管" min-width="160">
        <template #default="{ row }">
          {{ row.leaderName || '-' }}
          <span class="muted">（{{ row.leaderAccount || row.leaderUserId }}）</span>
        </template>
      </el-table-column>
      <el-table-column prop="memberCount" label="组员数" width="90" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '活跃' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="row.status !== 'active'" @click="openMembers(row)">
            成员
          </el-button>
          <el-button link type="primary" :disabled="row.status !== 'active'" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button link type="danger" :disabled="row.status !== 'active'" @click="onArchive(row)">
            归档
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    </PageSection>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑小组' : '新建小组'" width="480px">
      <el-form label-width="88px">
        <el-form-item label="小组名称" required>
          <el-input v-model="form.name" placeholder="如：运营一组" maxlength="40" />
        </el-form-item>
        <el-form-item label="主管" required>
          <el-select v-model="form.leaderUserId" filterable placeholder="选择员工升级为主管" style="width: 100%">
            <el-option
              v-for="emp in leaderOptions()"
              :key="emp.id || emp.userId"
              :label="`${emp.name || emp.nickname}（${emp.account}）`"
              :value="emp.id || emp.userId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitTeam">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="memberDialogVisible"
      :title="`成员管理 · ${activeTeam?.name || ''}`"
      width="640px"
    >
      <div class="member-add">
        <el-select v-model="addUserId" filterable clearable placeholder="从未入组员工中选择" style="flex: 1">
          <el-option
            v-for="emp in unassigned"
            :key="emp.userId || emp.id"
            :label="`${emp.name}（${emp.account}）`"
            :value="emp.userId || emp.id"
          />
        </el-select>
        <el-button type="primary" :disabled="!addUserId" @click="onAddMember">加入</el-button>
      </div>
      <el-table :data="members" size="small" style="margin-top: 12px">
        <el-table-column prop="name" label="姓名" />
        <el-table-column prop="account" label="账号" />
        <el-table-column prop="role" label="岗位" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="danger" @click="onRemoveMember(row.userId)">移出</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </PageScroll>
</template>

<style scoped>
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.member-add {
  display: flex;
  gap: 8px;
}
</style>
