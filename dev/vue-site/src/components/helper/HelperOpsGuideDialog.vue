<script setup>
import { computed } from 'vue'
import { HELPER_OPS_GUIDE_SECTIONS, HELPER_OPS_GUIDE_TITLE } from './helperOpsGuide'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const sections = HELPER_OPS_GUIDE_SECTIONS
const title = HELPER_OPS_GUIDE_TITLE
</script>

<template>
  <el-dialog
    v-model="open"
    :title="title"
    width="min(560px, 92vw)"
    append-to-body
    destroy-on-close
    class="helper-ops-guide-dialog"
  >
    <div class="helper-ops-guide">
      <section v-for="section in sections" :id="`guide-${section.id}`" :key="section.id" class="helper-ops-guide__section">
        <h3 class="helper-ops-guide__section-title">{{ section.title }}</h3>
        <ol class="helper-ops-guide__list">
          <li v-for="(item, index) in section.items" :key="item.title">
            <div class="helper-ops-guide__index">{{ index + 1 }}</div>
            <div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.body }}</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
    <template #footer>
      <el-button type="primary" @click="open = false">知道了</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.helper-ops-guide {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: min(70vh, 640px);
  overflow: auto;
  padding-right: 4px;
}

.helper-ops-guide__section-title {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 650;
  color: var(--el-text-color-primary);
}

.helper-ops-guide__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.helper-ops-guide__list li {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.helper-ops-guide__index {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.helper-ops-guide h4 {
  margin: 2px 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.helper-ops-guide p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-regular);
}
</style>
