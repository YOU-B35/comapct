<script setup>
import { computed } from 'vue'
import { GUIDE_STEPS, markAiImageGuideSeen } from '../settings'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function close() {
  markAiImageGuideSeen()
  open.value = false
}
</script>

<template>
  <el-dialog
    v-model="open"
    title="操作指南"
    width="min(560px, 92vw)"
    append-to-body
    destroy-on-close
    @closed="markAiImageGuideSeen"
  >
    <ol class="ai-guide">
      <li v-for="(step, index) in GUIDE_STEPS" :key="step.title">
        <div class="ai-guide__index">{{ index + 1 }}</div>
        <div>
          <h4>{{ step.title }}</h4>
          <p>{{ step.body }}</p>
        </div>
      </li>
    </ol>
    <p class="ai-guide__footer">提示词请保持合规，避免违规内容导致生成失败。@CrossHub</p>
    <template #footer>
      <el-button type="primary" @click="close">我知道了</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.ai-guide {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ai-guide li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.ai-guide__index {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.ai-guide h4 {
  margin: 2px 0 4px;
  font-size: 14px;
  color: #0f172a;
}

.ai-guide p {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.55;
}

.ai-guide__footer {
  margin: 16px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
</style>
