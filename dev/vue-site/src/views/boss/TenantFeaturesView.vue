<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import { fetchTenantFeatures, updateTenantFeatures } from '@/api/tenantFeatures'

const auth = useAuthStore()

const loading = ref(false)
const saving = ref(false)
const features = ref([])

const portalLabels = {
  boss: '企业管理员',
  employee: '员工端口',
  warehouse: '仓库端口',
}

const groupedFeatures = computed(() => {
  const groups = new Map()
  for (const item of features.value) {
    const portal = item.portal || 'other'
    if (!groups.has(portal)) {
      groups.set(portal, [])
    }
    groups.get(portal).push(item)
  }
  return [...groups.entries()].map(([portal, items]) => ({
    portal,
    label: portalLabels[portal] || portal,
    items,
  }))
})

async function loadFeatures() {
  loading.value = true
  try {
    const res = await fetchTenantFeatures(auth)
    features.value = (res.data || []).map((item) => ({
      ...item,
      enabled: item.enabled !== false,
    }))
  } catch {
    features.value = []
    ElMessage.error('加载功能开关失败')
  } finally {
    loading.value = false
  }
}

async function saveFeatures() {
  saving.value = true
  try {
    const payload = features.value.map((item) => ({
      feature_code: item.feature_code,
      enabled: item.enabled !== false,
    }))
    await updateTenantFeatures(auth, payload)
    await auth.refreshSession()
    ElMessage.success('功能开关已保存，侧栏菜单已刷新')
  } catch (err) {
    ElMessage.error(err?.response?.data?.message || err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadFeatures)
</script>

<template>
  <PageScroll>
    <PageHeader
      title="功能开关"
      eyebrow="租户"
      description="按租户启用或关闭菜单模块。关闭后 Boss 与员工侧栏将不再显示对应入口，直接访问 URL 也会被拦截。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadFeatures">
          刷新
        </el-button>
        <el-button type="primary" :loading="saving" @click="saveFeatures">
          保存
        </el-button>
      </template>
    </PageHeader>

    <el-alert
      class="feature-hint"
      type="info"
      :closable="false"
      show-icon
      title="核心设置项（运营绑定、账户绑定、工作台等）不可关闭。关闭平台模块时会同步关闭对应员工端入口。"
    />

    <PageSection title="模块权限">
    <div v-loading="loading" class="feature-groups">
      <el-card
        v-for="group in groupedFeatures"
        :key="group.portal"
        shadow="never"
        class="feature-group-card"
      >
        <template #header>
          <span class="group-title">{{ group.label }}</span>
        </template>

        <div class="feature-list">
          <div
            v-for="item in group.items"
            :key="item.feature_code"
            class="feature-row"
          >
            <div class="feature-meta">
              <div class="feature-label">{{ item.label }}</div>
              <div class="feature-code">{{ item.feature_code }}</div>
            </div>
            <el-switch
              v-model="item.enabled"
              :disabled="item.protected"
              inline-prompt
              active-text="开"
              inactive-text="关"
            />
          </div>
        </div>
      </el-card>
    </div>
    </PageSection>
  </PageScroll>
</template>

<style scoped>
.feature-hint {
  margin-bottom: 16px;
}

.feature-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.group-title {
  font-weight: 600;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.feature-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.feature-row:last-child {
  border-bottom: none;
}

.feature-meta {
  min-width: 0;
}

.feature-label {
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.feature-code {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}
</style>
