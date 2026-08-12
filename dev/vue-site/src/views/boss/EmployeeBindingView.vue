<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import {
  deleteEmployee,
  fetchEmployees,
  saveEmployee,
  toggleEmployeeStatus,
} from '@/api/employees'
import { fetchAllPlatformStores } from '@/api/platformAccounts'
import {
  PLATFORM_OPTION_GROUPS,
  ROLE_OPTIONS,
  OTHER_ROLE_OPTIONS,
  WAREHOUSE_MENU_CODE,
  platformLabels,
} from '@/constants/employees'
import { collapsePlatformsForForm, storeMatchesPlatforms } from '@/constants/platforms'

const props = defineProps({
  /** 部分主管模式：仅编辑本组绑定，不可建号/删号/重置密码/停用 */
  teamLeaderMode: { type: Boolean, default: false },
})

const auth = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const employees = ref([])
const boundStores = ref([])
const dialogVisible = ref(false)
const keyword = ref('')
const statusFilter = ref('all')

const storeNameMap = computed(() =>
  Object.fromEntries(boundStores.value.map((store) => [store.id, store.storeName])),
)

const stats = computed(() => ({
  total: employees.value.length,
  active: employees.value.filter((e) => e.status !== false).length,
  warehouse: employees.value.filter((e) => hasWarehouseOrdering(e)).length,
}))

const filteredEmployees = computed(() => {
  let list = employees.value
  if (statusFilter.value === 'active') {
    list = list.filter((e) => e.status !== false)
  } else if (statusFilter.value === 'inactive') {
    list = list.filter((e) => e.status === false)
  }
  const q = keyword.value.trim().toLowerCase()
  if (q) {
    list = list.filter(
      (e) =>
        e.name?.toLowerCase().includes(q)
        || e.account?.toLowerCase().includes(q)
        || e.role?.toLowerCase().includes(q),
    )
  }
  return list
})

const emptyForm = () => ({
  id: '',
  name: '',
  account: '',
  password: '',
  phone: '',
  role: '',
  otherRole: '',
  platforms: [],
  assignedStoreIds: [],
  warehouseOrdering: false,
  status: true,
})

const form = reactive(emptyForm())
const formRef = ref(null)

const dialogTitle = computed(() => (form.id ? '编辑运营' : '添加运营'))

const availableStores = computed(() => {
  if (!form.platforms.length) return []
  return boundStores.value.filter((store) => storeMatchesPlatforms(store.platform, form.platforms))
})

const formRules = computed(() => ({
  name: [{ required: true, message: '请填写员工姓名', trigger: 'blur' }],
  account: [{ required: true, message: '请填写登录账号', trigger: 'blur' }],
  role: [{ required: true, message: '请选择岗位角色', trigger: 'change' }],
  platforms: [{ type: 'array', required: true, min: 1, message: '请至少选择一个负责平台', trigger: 'change' }],
  password: form.id
    ? []
    : [{ required: true, message: '请设置初始登录密码', trigger: 'blur' }],
}))

function hasWarehouseOrdering(row) {
  const codes = row.menuCodes || row.menu_codes || []
  return codes.includes(WAREHOUSE_MENU_CODE)
}

function warehouseMenuCodes(enabled) {
  return enabled ? [WAREHOUSE_MENU_CODE] : []
}

function storeSummary(row) {
  const ids = row.assignedStoreIds || []
  if (!ids.length) return '未分配'
  if (ids.length === 1) return storeNameMap.value[ids[0]] || ids[0]
  const first = storeNameMap.value[ids[0]] || ids[0]
  return `${first} 等 ${ids.length} 家`
}

async function loadEmployees() {
  loading.value = true
  try {
    const [empRes, storeRes] = await Promise.all([
      fetchEmployees(auth),
      fetchAllPlatformStores(),
    ])
    employees.value = empRes.data || []
    boundStores.value = storeRes.data || []
  } catch {
    employees.value = []
    boundStores.value = []
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, emptyForm())
  formRef.value?.clearValidate?.()
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name,
    account: row.account,
    password: '',
    phone: row.phone || '',
    role: row.role,
    otherRole: row.otherRole || '',
    platforms: collapsePlatformsForForm(row.platforms || []),
    assignedStoreIds: [...(row.assignedStoreIds || [])],
    warehouseOrdering: hasWarehouseOrdering(row),
    status: row.status !== false,
  })
  dialogVisible.value = true
}

function closeDialog() {
  dialogVisible.value = false
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await saveEmployee(auth, {
      id: form.id || undefined,
      name: form.name.trim(),
      account: form.account.trim(),
      password: form.password,
      phone: form.phone.trim(),
      role: form.role,
      otherRole: form.otherRole || '',
      platforms: form.platforms,
      assignedStoreIds: form.assignedStoreIds,
      menuCodes: warehouseMenuCodes(form.warehouseOrdering),
      status: form.status,
    })
    ElMessage.success(form.id ? '运营信息已更新' : '运营绑定成功')
    closeDialog()
    await loadEmployees()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function removeEmployee(row) {
  try {
    await ElMessageBox.confirm(`确定解除「${row.name}」的运营绑定？`, '解除绑定', {
      type: 'warning',
      confirmButtonText: '解除',
      cancelButtonText: '取消',
    })
    await deleteEmployee(auth, row.id)
    ElMessage.success('已解除绑定')
    await loadEmployees()
  } catch {
    // cancelled
  }
}

async function handleStatusChange(row, status) {
  try {
    await toggleEmployeeStatus(auth, row.id, status)
    row.status = status
    ElMessage.success(status ? '已启用' : '已停用')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
    await loadEmployees()
  }
}

watch(
  () => form.platforms.slice(),
  () => {
    const allowed = new Set(availableStores.value.map((store) => store.id))
    form.assignedStoreIds = form.assignedStoreIds.filter((id) => allowed.has(id))
  },
)

onMounted(loadEmployees)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        :title="teamLeaderMode ? '运营绑定（本组）' : '运营绑定'"
        eyebrow="组织"
        :description="
          teamLeaderMode
            ? '管理本组员工的平台/店铺绑定、岗位与其他角色；不可建号或重置密码'
            : '管理运营员工账号；运营模块按负责平台自动显示，仓库下单单独开通'
        "
      >
        <template #actions>
          <el-button :icon="Refresh" :loading="loading" @click="loadEmployees">刷新</el-button>
          <el-button v-if="!teamLeaderMode" type="primary" :icon="Plus" @click="openCreate">
            添加运营
          </el-button>
        </template>
      </PageHeader>
    </template>

    <div v-loading="loading" class="employee-page">
      <PageSection title="人员概览">
      <div class="metrics-bar metrics-bar--3">
        <div class="metric-item">
          <div class="metric-value">{{ stats.total }}</div>
          <div class="metric-label">全部员工</div>
        </div>
        <div class="metric-item">
          <div class="metric-value is-success">{{ stats.active }}</div>
          <div class="metric-label">启用中</div>
        </div>
        <div class="metric-item">
          <div class="metric-value is-primary">{{ stats.warehouse }}</div>
          <div class="metric-label">可仓库下单</div>
        </div>
      </div>
      </PageSection>

      <PageSection title="员工列表">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          placeholder="搜索姓名、账号、岗位"
          clearable
          class="toolbar-search"
        />
        <el-radio-group v-model="statusFilter" size="small">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="active">启用</el-radio-button>
          <el-radio-button value="inactive">停用</el-radio-button>
        </el-radio-group>
      </div>

      <el-empty
        v-if="!loading && !filteredEmployees.length"
        :description="employees.length ? '没有匹配的运营人员' : '暂无绑定运营'"
        :image-size="88"
      >
        <el-button
          v-if="!employees.length && !teamLeaderMode"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          添加第一位运营
        </el-button>
      </el-empty>

      <el-table v-else :data="filteredEmployees" stripe size="small" class="employee-table">
        <el-table-column label="员工" min-width="140">
          <template #default="{ row }">
            <div class="cell-name">{{ row.name }}</div>
            <div class="cell-sub">{{ row.role }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="account" label="登录账号" min-width="180" show-overflow-tooltip />
        <el-table-column label="负责平台" min-width="160">
          <template #default="{ row }">
            <el-space wrap :size="4">
              <el-tag
                v-for="p in row.platforms"
                :key="p"
                size="small"
                effect="plain"
              >
                {{ platformLabels([p]) }}
              </el-tag>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column label="负责店铺" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'text-muted': !row.assignedStoreIds?.length }">
              {{ storeSummary(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="仓库下单" width="88" align="center">
          <template #default="{ row }">
            <el-tag
              :type="hasWarehouseOrdering(row) ? 'success' : 'info'"
              size="small"
              effect="light"
            >
              {{ hasWarehouseOrdering(row) ? '已开通' : '未开通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="!teamLeaderMode" label="状态" width="72" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status !== false"
              size="small"
              @change="(val) => handleStatusChange(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="!teamLeaderMode"
              link
              type="danger"
              :icon="Delete"
              @click="removeEmployee(row)"
            />
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
      class="employee-dialog"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="88px"
        label-position="right"
        class="dialog-form"
      >
        <p class="form-section-title">账号信息</p>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="真实姓名" maxlength="20" />
        </el-form-item>
        <el-form-item label="登录账号" prop="account">
          <el-input
            v-model="form.account"
            placeholder="邮箱或手机号"
            :disabled="teamLeaderMode"
          />
        </el-form-item>
        <el-form-item
          v-if="!teamLeaderMode"
          :label="form.id ? '重置密码' : '登录密码'"
          prop="password"
        >
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="form.id ? '留空则不修改' : '员工端登录密码'"
          />
        </el-form-item>
        <el-form-item v-if="!teamLeaderMode" label="联系电话">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item v-if="!teamLeaderMode" label="账号状态">
          <el-switch v-model="form.status" active-text="启用" inactive-text="停用" />
        </el-form-item>

        <p class="form-section-title">业务范围</p>
        <el-form-item label="岗位角色" prop="role">
          <el-select v-model="form.role" placeholder="选择岗位" style="width: 100%">
            <el-option v-for="role in ROLE_OPTIONS" :key="role" :label="role" :value="role" />
          </el-select>
        </el-form-item>
        <el-form-item label="其他角色">
          <el-select
            v-model="form.otherRole"
            clearable
            placeholder="选填：自媒体运营 / 其他"
            style="width: 100%"
          >
            <el-option
              v-for="item in OTHER_ROLE_OPTIONS"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
          <p class="form-hint">仅选择「自媒体运营」时，员工端显示自媒体运营菜单</p>
        </el-form-item>
        <el-form-item label="负责平台" prop="platforms">
          <el-select
            v-model="form.platforms"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择平台"
            style="width: 100%"
          >
            <el-option-group
              v-for="group in PLATFORM_OPTION_GROUPS"
              :key="group.label"
              :label="group.label"
            >
              <el-option
                v-for="item in group.options"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="负责店铺">
          <el-select
            v-model="form.assignedStoreIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :disabled="!form.platforms.length"
            :placeholder="form.platforms.length ? '选择店铺（选填）' : '请先选择负责平台'"
            style="width: 100%"
          >
            <el-option
              v-for="store in availableStores"
              :key="store.id"
              :label="store.storeName"
              :value="store.id"
            />
          </el-select>
        </el-form-item>

        <p class="form-section-title">仓库权限</p>
        <el-form-item label="仓库下单">
          <div class="warehouse-switch">
            <el-switch v-model="form.warehouseOrdering" />
            <span class="warehouse-switch__hint">
              {{ form.warehouseOrdering ? '已开通：员工可提交出库申请' : '未开通：员工端不显示仓库下单' }}
            </span>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ form.id ? '保存' : '确认添加' }}
        </el-button>
      </template>
    </el-dialog>
  </PageScroll>
</template>

<style scoped>
.employee-page {
  display: grid;
  gap: 16px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.toolbar-search {
  width: 240px;
}

.employee-table {
  border-radius: var(--ch-radius-lg);
}

.cell-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text);
  line-height: 1.4;
}

.cell-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--ch-text-muted);
}

.text-muted {
  font-size: 12px;
  color: var(--ch-text-muted);
}

.form-section-title {
  margin: 0 0 12px;
  padding-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ch-text);
  border-bottom: 1px solid var(--ch-border, #ebeef5);
}

.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ch-text-muted);
}

.form-section-title:not(:first-child) {
  margin-top: 8px;
}

.dialog-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.warehouse-switch {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.warehouse-switch__hint {
  font-size: 12px;
  color: var(--ch-text-muted);
  line-height: 1.45;
}
</style>
