<script setup>
import { computed } from 'vue'
import { AGENT_PROMPT_TEMPLATES } from '../settings'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'apply'])

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function applyTemplate(item) {
  emit('apply', item)
  open.value = false
}
</script>

<template>
  <el-drawer
    v-model="open"
    title="Agent 提示词模板"
    size="360px"
    append-to-body
    destroy-on-close
  >
    <p class="ai-agent__hint">选择模板后仅复制到剪贴板，不会自动填入输入框；请自行粘贴并改写后再生成。</p>
    <div class="ai-agent__list">
      <button
        v-for="item in AGENT_PROMPT_TEMPLATES"
        :key="item.id"
        type="button"
        class="ai-agent__card"
        @click="applyTemplate(item)"
      >
        <strong>{{ item.label }}</strong>
        <span>{{ item.prompt }}</span>
      </button>
    </div>
  </el-drawer>
</template>

<style scoped>
.ai-agent__hint {
  margin: 0 0 14px;
  font-size: 13px;
  color: #64748b;
}

.ai-agent__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-agent__card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.ai-agent__card:hover {
  border-color: #93c5fd;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.12);
}

.ai-agent__card strong {
  font-size: 14px;
  color: #0f172a;
}

.ai-agent__card span {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
</style>
