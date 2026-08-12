<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { deletePlatformStore, fetchAllPlatformStores } from '@/api/platformAccounts'
import { formatCaughtError } from '@/utils/appErrorCode'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import BindStoreDialog from '@/components/accounts/BindStoreDialog.vue'
import ZiniaoImportDialog from '@/components/accounts/ZiniaoImportDialog.vue'

const PLATFORM_META = {
  temu: { label: 'Temu', type: 'warning' },
  aliexpress: { label: 'AliExpress', type: 'danger' },
  amazon: { label: 'Amazon', type: '' },
  walmart: { label: 'Walmart', type: 'primary' },
  pdd: { label: '拼多多', type: 'danger' },
  douyin: { label: '抖音', type: '' },
  channels: { label: '视频号', type: 'success' },
  '1688': { label: '1688', type: 'warning' },
  shopify: { label: 'Shopify', type: 'success' },
  wordpress: { label: 'WordPress', type: 'info' },
}

const FILTER_PLATFORMS = [
  { value: 'temu', label: 'Temu' },
  { value: 'aliexpress', label: 'AliExpress' },
  { value: 'amazon', label: 'Amazon' },
  { value: 'walmart', label: 'Walmart' },
  { value: 'pdd', label: '拼多多' },
  { value: 'douyin', label: '抖音' },
  { value: 'channels', label: '视频号' },
  { value: '1688', label: '1688' },
  { value: 'shopify', label: 'Shopify' },
  { value: 'wordpress', label: 'WordPress' },
]

const loading = ref(false)
const allStores = ref([])
const activePlatform = ref('all')
const bindDialogVisible = ref(false)
const bindDefaultPlatform = ref('temu')
const editingStore = ref(null)
const ziniaoDialogVisible = ref(false)

const showZiniaoImport = computed(
  () => activePlatform.value === 'amazon' || activePlatform.value === 'all',
)

const platformCounts = computed(() => {
  const counts = {}
  for (const store of allStores.value) {
    counts[store.platform] = (counts[store.platform] || 0) + 1
  }
  return counts
})

const filteredStores = computed(() => {
  if (activePlatform.value === 'all') return allStores.value
  return allStores.value.filter((store) => store.platform === activePlatform.value)
})

function platformLabel(platform) {
  return PLATFORM_META[platform]?.label || platform
}

function platformTagType(platform) {
  return PLATFORM_META[platform]?.type || 'info'
}

function openBindDialog(platform = 'temu') {
  editingStore.value = null
  bindDefaultPlatform.value = platform === 'all' ? 'temu' : platform
  bindDialogVisible.value = true
}

function openEditDialog(row) {
  editingStore.value = { ...row }
  bindDialogVisible.value = true
}

function onBindDialogClosed() {
  editingStore.value = null
}

async function loadStores() {
  loading.value = true
  try {
    const res = await fetchAllPlatformStores()
    allStores.value = res.data || []
  } catch {
    allStores.value = []
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function removeStore(row) {
  try {
    await ElMessageBox.confirm(`确定解除「${row.storeName}」的绑定？`, '解除绑定', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  loading.value = true
  try {
    await deletePlatformStore(row.id)
    await loadStores()
    ElMessage.success('已解除绑定')
  } catch (err) {
    ElMessage.error(formatCaughtError(err, '操作失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadStores)
</script>

<template>
  <PageScroll>
    <template #header>
      <PageHeader
        title="账户绑定"
        eyebrow="配置"
        description="绑定各平台店铺后，对应运营模块将自动读取"
      >
        <template #actions>
          <el-button :icon="Refresh" :loading="loading" @click="loadStores">刷新</el-button>
          <el-button
            v-if="showZiniaoImport"
            @click="ziniaoDialogVisible = true"
          >
            从紫鸟导入
          </el-button>
          <el-button type="primary" :icon="Plus" @click="openBindDialog(activePlatform)">
            绑定店铺
          </el-button>
        </template>
      </PageHeader>
    </template>

    <PageSection title="平台筛选">
      <div class="filter-bar">
      <button
        type="button"
        class="filter-chip"
        :class="{ 'is-active': activePlatform === 'all' }"
        @click="activePlatform = 'all'"
      >
        全部
        <span v-if="allStores.length" class="filter-chip__count">{{ allStores.length }}</span>
      </button>
      <button
        v-for="item in FILTER_PLATFORMS"
        :key="item.value"
        type="button"
        class="filter-chip"
        :class="{ 'is-active': activePlatform === item.value }"
        @click="activePlatform = item.value"
      >
        {{ item.label }}
        <span v-if="platformCounts[item.value]" class="filter-chip__count">
          {{ platformCounts[item.value] }}
        </span>
      </button>
      </div>
    </PageSection>

    <PageSection title="已绑定店铺">
    <div v-loading="loading" class="store-card">
      <el-table
        v-if="filteredStores.length"
        :data="filteredStores"
        size="small"
        stripe
        class="store-table"
      >
        <el-table-column label="平台" width="110">
          <template #default="{ row }">
            <el-tag :type="platformTagType(row.platform)" size="small" effect="plain">
              {{ platformLabel(row.platform) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="storeName" label="店铺名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="account" label="登录账号" min-width="180" show-overflow-tooltip />
        <el-table-column label="接入方式" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.integrationMode === 'ziniao'" size="small" type="success" effect="plain">
              紫鸟
            </el-tag>
            <span v-else class="cell-muted">手动</span>
          </template>
        </el-table-column>
        <el-table-column prop="boundAt" label="绑定时间" width="170" />
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Edit" @click="openEditDialog(row)">
              编辑
            </el-button>
            <el-button link type="danger" :icon="Delete" @click="removeStore(row)">
              解除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else description="暂无绑定店铺" :image-size="80">
        <el-button type="primary" :icon="Plus" @click="openBindDialog(activePlatform)">
          绑定第一个店铺
        </el-button>
      </el-empty>
    </div>
    </PageSection>

    <BindStoreDialog
      v-model:visible="bindDialogVisible"
      :default-platform="bindDefaultPlatform"
      :edit-store="editingStore"
      @success="loadStores"
      @update:visible="(open) => { if (!open) onBindDialogClosed() }"
    />

    <ZiniaoImportDialog v-model="ziniaoDialogVisible" @bound="loadStores" />
  </PageScroll>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-bg-color);
  color: var(--el-text-color-regular);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.filter-chip:hover {
  border-color: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
}

.filter-chip.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}

.filter-chip__count {
  min-width: 18px;
  padding: 0 5px;
  border-radius: 10px;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  text-align: center;
}

.filter-chip.is-active .filter-chip__count {
  background: var(--el-color-primary-light-7);
  color: var(--el-color-primary);
}

.store-card {
  padding: 4px 0;
  border-radius: 8px;
  background: var(--el-bg-color);
}

.store-table {
  border-radius: 8px;
}

.cell-muted {
  color: var(--el-text-color-placeholder);
}
</style>
