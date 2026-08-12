<script setup>
import { computed, ref } from 'vue'
import { ChatDotRound, Lightning } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { AI_CONTEXT_HINTS, AI_SKILL_GROUPS } from '@/constants/aiOffice'
import { PLATFORM_OPTIONS } from '@/constants/employees'
import { platformDisplayLabels } from '@/constants/platforms'
import AiChatPanel from '@/components/ai/AiChatPanel.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import PageSection from '@/components/common/PageSection.vue'

const auth = useAuthStore()
const chatRef = ref(null)
const activeGroup = ref(AI_SKILL_GROUPS[0].id)

const platformLabels = computed(() => {
  const map = Object.fromEntries(PLATFORM_OPTIONS.map((p) => [p.value, p.label]))
  const list = auth.backendLinked ? (auth.platforms || []) : (auth.employee.platforms || [])
  return platformDisplayLabels(list, map).join(' · ') || '运营'
})

const activeSkills = computed(
  () => AI_SKILL_GROUPS.find((g) => g.id === activeGroup.value)?.skills || [],
)

function runSkill(prompt) {
  chatRef.value?.sendMessage?.(prompt)
}
</script>

<template>
  <div class="ai-office">
    <PageHeader
      title="CrossHub AI"
      eyebrow="智能助手"
      :description="`${auth.employee.name} · ${auth.employee.role}${platformLabels ? ` · ${platformLabels}` : ''}`"
    >
      <template #actions>
        <el-tag type="primary" effect="plain" class="ai-office__badge">
          <el-icon><Lightning /></el-icon>
          Copilot
        </el-tag>
      </template>
    </PageHeader>

    <div class="ai-body">
      <PageSection title="AI 技能" description="点选后直接发到对话" class="ai-skills-section">
        <div class="ai-skills__tabs">
          <button
            v-for="group in AI_SKILL_GROUPS"
            :key="group.id"
            type="button"
            class="skill-tab"
            :class="{ 'is-active': activeGroup === group.id }"
            :style="activeGroup === group.id ? { '--tab-color': group.color } : {}"
            @click="activeGroup = group.id"
          >
            {{ group.label }}
          </button>
        </div>
        <div class="skill-list">
          <button
            v-for="skill in activeSkills"
            :key="skill.id"
            type="button"
            class="skill-item"
            @click="runSkill(skill.prompt)"
          >
            <span class="skill-item__label">{{ skill.label }}</span>
            <span class="skill-item__desc">{{ skill.desc }}</span>
          </button>
        </div>
      </PageSection>

      <PageSection flush class="ai-chat-section">
        <AiChatPanel
          ref="chatRef"
          scope="employee"
          :user-name="auth.employee.name"
          :platforms="platformLabels"
        />
      </PageSection>

      <PageSection title="工作上下文" class="ai-context-section">
        <div class="context-stats">
          <article
            v-for="item in AI_CONTEXT_HINTS"
            :key="item.label"
            class="context-stat"
            :class="`is-${item.type}`"
          >
            <span class="context-stat__value">{{ item.value }}</span>
            <span class="context-stat__label">{{ item.label }}</span>
          </article>
        </div>

        <h4 class="context-subtitle">
          <el-icon><ChatDotRound /></el-icon>
          能力说明
        </h4>
        <ul class="context-list">
          <li>Listing 标题、卖点与多语言润色</li>
          <li>差评 / 买家消息 / Case 回复草稿</li>
          <li>补货、滞销、亏损 SKU 决策建议</li>
          <li>今日待办与预警优先级排序</li>
        </ul>
        <p class="context-note">
          正式版将接入你负责店铺的真实订单、库存与任务数据，生成可执行的运营建议。
        </p>
      </PageSection>
    </div>
  </div>
</template>

<style scoped>
.ai-office {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  gap: 14px;
}

.ai-office__badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 6px;
}

.ai-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 240px 1fr 248px;
  gap: 14px;
}

.ai-skills-section,
.ai-chat-section,
.ai-context-section {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ai-skills-section :deep(.page-section__body),
.ai-chat-section :deep(.page-section__body),
.ai-context-section :deep(.page-section__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ai-skills__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.skill-tab {
  padding: 7px 12px;
  border: 1px solid var(--ch-border);
  border-radius: 8px;
  background: var(--ch-surface);
  color: var(--ch-text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: var(--ch-shadow-xs);
  transition:
    background 0.15s,
    color 0.15s,
    border-color 0.15s,
    box-shadow 0.15s;
}

.skill-tab:hover {
  background: var(--ch-primary-soft);
  border-color: var(--ch-primary-muted);
  color: var(--ch-primary);
}

.skill-tab.is-active {
  border-color: color-mix(in srgb, var(--tab-color, var(--ch-primary)) 40%, var(--ch-border));
  background: color-mix(in srgb, var(--tab-color, var(--ch-primary)) 12%, #fff);
  color: var(--tab-color, var(--ch-primary));
  font-weight: 650;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--tab-color, var(--ch-primary)) 18%, transparent);
}

.skill-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 12px 11px;
  border: 1px solid var(--ch-border);
  border-radius: 8px;
  background: var(--ch-surface);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--ch-shadow-xs);
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s, transform 0.15s;
}

.skill-item:hover {
  border-color: var(--ch-primary-muted);
  background: linear-gradient(180deg, #f8faff 0%, #fff 70%);
  box-shadow: var(--ch-shadow-sm);
  transform: translateY(-1px);
}

.skill-item__label {
  font-size: 13px;
  font-weight: 650;
  color: var(--ch-text);
}

.skill-item__desc {
  font-size: 12px;
  line-height: 1.4;
  color: var(--ch-text-muted);
}

.ai-chat-section :deep(.chat-shell) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.context-stats {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-bottom: 14px;
}

.context-stat {
  position: relative;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--ch-border);
  border-radius: 8px;
  background: var(--ch-surface);
  overflow: hidden;
}

.context-stat::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: var(--ch-primary);
}

.context-stat.is-warning::before { background: var(--ch-warning); }
.context-stat.is-danger::before { background: var(--ch-error); }
.context-stat.is-success::before { background: var(--ch-success); }

.context-stat__value {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  color: var(--ch-text);
}

.context-stat.is-primary .context-stat__value { color: var(--ch-primary); }
.context-stat.is-warning .context-stat__value { color: var(--ch-warning); }
.context-stat.is-danger .context-stat__value { color: var(--ch-error); }
.context-stat.is-success .context-stat__value { color: var(--ch-success); }

.context-stat__label {
  font-size: 12px;
  font-weight: 550;
  color: var(--ch-text-muted);
}

.context-subtitle {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 650;
  color: var(--ch-text);
}

.context-list {
  margin: 0 0 12px;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.75;
  color: var(--ch-text-secondary);
}

.context-note {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px dashed var(--ch-border);
  background: var(--ch-surface-muted);
  font-size: 12px;
  line-height: 1.55;
  color: var(--ch-text-muted);
}

@media (max-width: 1100px) {
  .ai-body {
    grid-template-columns: 220px 1fr;
  }

  .ai-context-section {
    display: none;
  }
}

@media (max-width: 768px) {
  .ai-body {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
  }

  .ai-skills-section {
    max-height: 240px;
  }
}
</style>
