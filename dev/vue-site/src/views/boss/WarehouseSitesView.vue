<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import {
  deleteWarehouseSite,
  fetchWarehouseSites,
  saveWarehouseSite,
  toggleWarehouseSiteStatus,
} from '@/api/warehouseSites'

const auth = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const sites = ref([])
const dialogVisible = ref(false)

const emptyForm = () => ({
  id: '',
  name: '',
  code: '',
  address: '',
  status: true,
  sortOrder: 0,
})

const form = reactive(emptyForm())
const formRef = ref(null)

const dialogTitle = computed(() => (form.id ? '编辑仓库' : '添加仓库'))

const formRules = {
  name: [{ required: true, message: '请填写仓库名称', trigger: 'blur' }],
  code: [{ required: true, message: '请填写仓库编码', trigger: 'blur' }],
}

async function loadSites() {
  loading.value = true
  try {
    const res = await fetchWarehouseSites(auth)
    sites.value = res.data || []
  } catch {
    sites.value = []
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
  form.sortOrder = (sites.value.length + 1) * 10
  dialogVisible.value = true
}

function openEdit(row) {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name,
    code: row.code,
    address: row.address || '',
    status: row.status !== false,
    sortOrder: row.sortOrder || 0,
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
    await saveWarehouseSite(auth, {
      id: form.id || undefined,
      name: form.name.trim(),
      code: form.code.trim(),
      address: form.address.trim(),
      status: form.status,
      sortOrder: Number(form.sortOrder) || 0,
    })
    ElMessage.success(form.id ? '仓库已更新' : '仓库已添加')
    dialogVisible.value = false
    await loadSites()
  } catch (err) {
    ElMessage.error(err.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function removeSite(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」？`, '删除仓库', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteWarehouseSite(auth, row.id)
    ElMessage.success('已删除')
    await loadSites()
  } catch {
    // cancelled
  }
}

async function handleStatusChange(row, status) {
  try {
    await toggleWarehouseSiteStatus(auth, row.id, status)
    row.status = status
    ElMessage.success(status ? '已启用' : '已停用')
  } catch (err) {
    ElMessage.error(err.message || '操作失败')
    await loadSites()
  }
}

onMounted(loadSites)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="仓库设置"
        eyebrow="仓储"
        description="维护分仓信息；运营下单时需选择目标仓库，仓管仅处理已分配仓库的订单"
      >
        <template #actions>
          <el-button :icon="Refresh" :loading="loading" @click="loadSites">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">添加仓库</el-button>
        </template>
      </PageHeader>
    </template>

    <PageSection flush>
      <el-table v-loading="loading" :data="sites" stripe size="small" class="sites-table">
        <el-table-column prop="name" label="仓库名称" min-width="140" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="address" label="地址" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.address || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="sortOrder" label="排序" width="72" align="center" />
        <el-table-column label="状态" width="72" align="center">
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
            <el-button link type="danger" :icon="Delete" @click="removeSite(row)" />
          </template>
        </el-table-column>
      </el-table>
    </PageSection>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="480px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="88px">
        <el-form-item label="仓库名称" prop="name">
          <el-input v-model="form.name" placeholder="如：泰州1号仓" maxlength="32" />
        </el-form-item>
        <el-form-item label="仓库编码" prop="code">
          <el-input v-model="form.code" placeholder="如：tz1（英文/数字）" :disabled="Boolean(form.id)" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="选填" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sortOrder" :min="0" :max="999" controls-position="right" />
        </el-form-item>
        <el-form-item label="状态">
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
.sites-table {
  border-radius: var(--ch-radius-lg);
}
</style>
