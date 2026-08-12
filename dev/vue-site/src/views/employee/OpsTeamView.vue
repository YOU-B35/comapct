<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import PageScroll from '@/components/common/PageScroll.vue'
import PageSection from '@/components/common/PageSection.vue'
import {
  addOpsTeamMember,
  fetchMyOpsTeam,
  fetchUnassignedEmployees,
  removeOpsTeamMember,
} from '@/api/opsTeams'

const loading = ref(false)
const team = ref(null)
const unassigned = ref([])
const addUserId = ref(null)

async function load() {
  loading.value = true
  try {
    team.value = await fetchMyOpsTeam()
    unassigned.value = await fetchUnassignedEmployees()
  } catch (e) {
    ElMessage.error(e?.message || '加载小组失败')
  } finally {
    loading.value = false
  }
}

async function onAdd() {
  if (!team.value?.id || !addUserId.value) return
  try {
    await addOpsTeamMember(team.value.id, addUserId.value)
    ElMessage.success('已加入本组')
    addUserId.value = null
    await load()
  } catch (e) {
    ElMessage.error(e?.message || '加人失败')
  }
}

async function onRemove(userId, name) {
  try {
    await ElMessageBox.confirm(`确认将「${name}」移出本组？`, '移出组员', { type: 'warning' })
    await removeOpsTeamMember(team.value.id, userId)
    ElMessage.success('已移出')
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e?.message || '移出失败')
  }
}

onMounted(load)
</script>

<template>
  <PageScroll>
    <PageHeader
      title="我的小组"
      eyebrow="团队"
      :description="team ? `${team.name} · 主管` : '您当前不是活跃小组主管'"
    >
      <template v-if="team" #actions>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </template>
    </PageHeader>
    <div v-loading="loading">
      <template v-if="team">
        <PageSection title="添加组员">
          <div class="add-row">
            <el-select v-model="addUserId" filterable clearable placeholder="从未入组员工中选择" style="flex: 1">
              <el-option
                v-for="emp in unassigned"
                :key="emp.userId || emp.id"
                :label="`${emp.name}（${emp.account}）`"
                :value="emp.userId || emp.id"
              />
            </el-select>
            <el-button type="primary" :disabled="!addUserId" @click="onAdd">加入本组</el-button>
          </div>
        </PageSection>
        <PageSection title="组成员">
          <el-table :data="team.members || []" stripe>
            <el-table-column prop="name" label="姓名" />
            <el-table-column prop="account" label="账号" />
            <el-table-column prop="role" label="岗位" />
            <el-table-column prop="otherRole" label="其他角色" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button link type="danger" @click="onRemove(row.userId, row.name)">移出</el-button>
              </template>
            </el-table-column>
          </el-table>
        </PageSection>
      </template>
      <el-empty v-else description="请联系企业管理员将您设为运营小组主管" />
    </div>
  </PageScroll>
</template>

<style scoped>
.add-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
