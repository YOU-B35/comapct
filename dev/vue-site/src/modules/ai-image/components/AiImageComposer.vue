<script setup>
import { computed, ref } from 'vue'
import { Paperclip, Promotion } from '@element-plus/icons-vue'
import {
  AI_IMAGE_MODELS,
  AI_IMAGE_QUALITIES,
  AI_IMAGE_RATIOS,
  MAX_REFERENCE_IMAGES,
} from '../constants'

const props = defineProps({
  prompt: { type: String, required: true },
  quality: { type: String, required: true },
  ratio: { type: String, required: true },
  steps: { type: [Number, String], required: true },
  count: { type: Number, required: true },
  model: { type: String, required: true },
  submitting: { type: Boolean, default: false },
  fileCount: { type: Number, default: 0 },
})

const emit = defineEmits([
  'update:prompt',
  'update:quality',
  'update:ratio',
  'update:steps',
  'update:count',
  'update:model',
  'submit',
  'pick-files',
])

const fileInput = ref(null)
const advancedOpen = computed(() => true)

function openPicker() {
  fileInput.value?.click()
}

function onFileChange(e) {
  const files = Array.from(e.target.files || []).slice(0, MAX_REFERENCE_IMAGES)
  emit('pick-files', files)
  e.target.value = ''
}
</script>

<template>
  <div class="ai-composer">
    <el-input
      type="textarea"
      :rows="3"
      resize="none"
      :model-value="prompt"
      placeholder="请输入提示词，例如：生成一个可爱小猫"
      class="ai-composer__prompt"
      @update:model-value="emit('update:prompt', $event)"
      @keydown.ctrl.enter.prevent="emit('submit')"
    />

    <div class="ai-composer__bar">
      <button type="button" class="ai-composer__advanced">
        进阶参数
        <span v-if="advancedOpen">▾</span>
      </button>

      <div class="ai-composer__controls">
        <div class="ctrl">
          <span class="ctrl__label">质量</span>
          <el-select
            :model-value="quality"
            size="small"
            style="width: 88px"
            @update:model-value="emit('update:quality', $event)"
          >
            <el-option
              v-for="item in AI_IMAGE_QUALITIES"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <div class="ctrl">
          <span class="ctrl__label">比例</span>
          <el-select
            :model-value="ratio"
            size="small"
            style="width: 88px"
            @update:model-value="emit('update:ratio', $event)"
          >
            <el-option
              v-for="item in AI_IMAGE_RATIOS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <div class="ctrl">
          <span class="ctrl__label">模型</span>
          <el-select
            :model-value="model"
            size="small"
            style="width: 120px"
            @update:model-value="emit('update:model', $event)"
          >
            <el-option
              v-for="item in AI_IMAGE_MODELS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>

        <div class="ctrl">
          <span class="ctrl__label">步数</span>
          <el-input
            :model-value="String(steps)"
            size="small"
            style="width: 72px"
            @update:model-value="emit('update:steps', $event)"
          />
        </div>

        <div class="ctrl">
          <span class="ctrl__label">数量</span>
          <el-input-number
            :model-value="count"
            :min="1"
            :max="4"
            size="small"
            controls-position="right"
            @update:model-value="emit('update:count', $event || 1)"
          />
        </div>
      </div>

      <div class="ai-composer__actions">
        <el-badge :value="fileCount || ''" :hidden="!fileCount">
          <el-button :icon="Paperclip" circle @click="openPicker" />
        </el-badge>
        <el-button
          type="primary"
          class="ai-composer__send"
          :icon="Promotion"
          :loading="submitting"
          circle
          @click="emit('submit')"
        />
        <input
          ref="fileInput"
          type="file"
          class="ai-composer__file"
          accept="image/*"
          multiple
          @change="onFileChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-composer {
  width: min(920px, calc(100% - 32px));
  margin: 0 auto;
  padding: 14px 16px 12px;
  border: 1px solid var(--ch-border);
  border-radius: 14px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-md);
}

.ai-composer__prompt :deep(.el-textarea__inner) {
  border: 0;
  box-shadow: none !important;
  padding: 4px 2px 8px;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ch-text);
  background: transparent;
}

.ai-composer__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px solid var(--ch-border);
}

.ai-composer__advanced {
  border: 0;
  background: transparent;
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  padding: 0 4px;
  white-space: nowrap;
}

.ai-composer__controls {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  flex-wrap: wrap;
  min-width: 0;
}

.ctrl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ctrl__label {
  font-size: 12px;
  color: #94a3b8;
  white-space: nowrap;
}

.ai-composer__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.ai-composer__send {
  width: 40px;
  height: 40px;
  background: #2563eb !important;
  border-color: #2563eb !important;
}

.ai-composer__file {
  display: none;
}
</style>
