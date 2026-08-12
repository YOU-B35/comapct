<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import { fetchWarehouseSites } from '@/api/warehouseSites'
import {
  deleteWarehouseStaff,
  fetchWarehouseStaff,
  saveWarehouseStaff,
  toggleWarehouseStaffStatus,
} from '@/api/warehouseStaff'
import { WAREHOUSE_DEFAULT_ROLE } from '@/constants/warehouseStaff'

const auth = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const staffList = ref([])
const warehouseSites = ref([])
const dialogVisible = ref(false)

const emptyForm = () => ({
  id: '',
  name: '',
  account: '',
  password: '',
  phone: '',
  role: WAREHOUSE_DEFAULT_ROLE,
  warehouseIds: [],
  status: true,
})

const form = reactive(emptyForm())
const formRef = ref(null)
const dialogTitle = computed(() => (form.id ? '编辑仓库人员' : '添加仓库人员'))

const warehouseNameMap = computed(() =>
  Object.fromEntries(warehouseSites.value.map((site) => [site.id, site.name])),
)

const formRules = computed(() => ({
  name: [{ required: true, message: '请填写员工姓名', trigger: 'blur' }],
  account: [{ required: true, message: '请填写登录账号', trigger: 'blur' }],
  warehouseIds: [{
    type: 'array',
    required: true,
    min: 1,
    message: '请至少分配一个管理仓库',
    trigger: 'change',
  }],
  password: form.id
    ? []
    : [{ required: true, message: '请设置初始登录密码', trigger: 'blur' }],
}))

function warehouseSummary(row) {
  const names = row.warehouseNames?.length
    ? row.warehouseNames
    : (row.warehouseIds || []).map((id) => warehouseNameMap.value[id] || id)
  if (!names.length) return '未分配'
  if (names.length <= 2) return names.join('、')
  return `${names.slice(0, 2).join('、')} 等 ${names.length} 仓`
}

async function loadData() {
  loading.value = true
  try {
    const [staffRes, sitesRes] = await Promise.all([
      fetchWarehouseStaff(auth),
      fetchWarehouseSites(auth, { activeOnly: false }),
    ])
    staffList.value = staffRes.data || []
    warehouseSites.value = sitesRes.data || []
  } catch {
    staffList.value = []
    warehouseSites.value = []
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
    role: WAREHOUSE_DEFAULT_ROLE,
    warehouseIds: [...(row.warehouseIds || [])],
    status: row.status !== false,
  })
  dialogVisible.value = true
}

async function submitForm() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    await saveWarehouseStaff(auth, {
      id: form.id || undefined,
      name: form.name.trim(),
      account: form.account.trim(),
      password: form.password,
      phone: form.phone.trim(),
      role: WAREHOUSE_DEFAULT_ROLE,
      warehouseIds: form.warehouseIds,
      status: form.status,
    })
    ElMessage.success(form.id ? '员工信息已更新' : '员工绑定成功')
    dialogVisible.value = false
    await loadData()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function removeStaff(row) {
  try {
    await ElMessageBox.confirm(`确定解除「${row.name}」的仓库人员绑定？`, '确认', {
      type: 'warning',
      confirmButtonText: '解除',
      cancelButtonText: '取消',
    })
    await deleteWarehouseStaff(auth, row.id)
    ElMessage.success('已解除绑定')
    await loadData()
  } catch {
    // cancelled
  }
}

async function handleStatusChange(row, status) {
  try {
    await toggleWarehouseStaffStatus(auth, row.id, status)
    row.status = status
    ElMessage.success(status ? '已启用' : '已停用')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
    await loadData()
  }
}

onMounted(loadData)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="仓库人员管理"
        eyebrow="仓储"
        description="由企业管理员维护仓库端口账号与分仓权限（岗位统一为仓库管理员）；仓管人员无权在此新增或绑定账号"
      >
        <template #actions>
          <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">添加员工</el-button>
        </template>
      </PageHeader>
    </template>

    <PageSection flush>
    <el-table v-loading="loading" :data="staffList" stripe size="small" class="staff-table">
      <el-table-column label="员工" min-width="120">
        <template #default="{ row }">
          <div class="cell-name">{{ row.name }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="account" label="登录账号" min-width="180" show-overflow-tooltip />
      <el-table-column label="管理仓库" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ 'text-muted': !row.warehouseIds?.length }">
            {{ warehouseSummary(row) }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="phone" label="联系电话" width="130">
        <template #default="{ row }">{{ row.phone || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="72" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.status !== false"
            size="small"
            @change="(val) => handleStatusChange(row, val)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="boundAt" label="绑定时间" width="160" />
      <el-table-column label="操作" width="120" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" :icon="Delete" @click="removeStaff(row)" />
        </template>
      </el-table-column>
    </el-table>
    </PageSection>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="88px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="登录账号" prop="account">
          <el-input v-model="form.account" placeholder="邮箱或手机号" />
        </el-form-item>
        <el-form-item :label="form.id ? '重置密码' : '登录密码'" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="form.id ? '留空则不修改' : '仓库端口登录密码'"
          />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="选填" />
        </el-form-item>
        <el-form-item label="管理仓库" prop="warehouseIds">
          <el-select
            v-model="form.warehouseIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择可管理的分仓"
            style="width: 100%"
          >
            <el-option
              v-for="site in warehouseSites.filter((s) => s.status !== false)"
              :key="site.id"
              :label="site.name"
              :value="site.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="form.status" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </PageScroll>
</template>

<style scoped>
.staff-table {
  border-radius: var(--ch-radius-lg);
}

.cell-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--ch-text);
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
</style>
