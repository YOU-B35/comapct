<script setup>
import { computed, ref } from 'vue'
import { Paperclip, Promotion, Close } from '@element-plus/icons-vue'
import {
  AI_IMAGE_MODELS,
  AI_IMAGE_QUALITIES,
  AI_IMAGE_RATIOS,
  MAX_REFERENCE_IMAGES,
} from '../constants'
import { collectImageFilesFromClipboard } from '../pasteImages'

const props = defineProps({
  prompt: { type: String, required: true },
  quality: { type: String, required: true },
  ratio: { type: String, required: true },
  steps: { type: [Number, String], required: true },
  count: { type: Number, required: true },
  model: { type: String, required: true },
  submitting: { type: Boolean, default: false },
  /** @type {{ name: string, url: string }[]} */
  referencePreviews: { type: Array, default: () => [] },
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
  'remove-file',
  'clear-files',
])

const fileInput = ref(null)
const rootRef = ref(null)
const advancedOpen = ref(true)
const emptySlots = computed(() =>
  Math.max(0, Math.min(3, MAX_REFERENCE_IMAGES - (props.referencePreviews?.length || 0))),
)

const advancedSummary = computed(() => {
  const modelLabel = AI_IMAGE_MODELS.find((m) => m.value === props.model)?.label || props.model
  return `${props.quality || '-'} · ${props.ratio || '-'} · ${modelLabel} · ×${props.count || 1}`
})

function toggleAdvanced() {
  advancedOpen.value = !advancedOpen.value
}

function openPicker() {
  fileInput.value?.click()
}

function onFileChange(e) {
  const files = Array.from(e.target.files || []).slice(0, MAX_REFERENCE_IMAGES)
  emit('pick-files', files)
  e.target.value = ''
}

function onPaste(e) {
  const files = collectImageFilesFromClipboard(e.clipboardData, MAX_REFERENCE_IMAGES)
  if (!files.length) return
  e.preventDefault()
  emit('pick-files', files)
}

function focusRoot() {
  rootRef.value?.focus?.()
}
</script>

<template>
  <div
    ref="rootRef"
    class="ai-composer"
    tabindex="0"
    @paste="onPaste"
    @click="focusRoot"
  >
    <div class="ai-composer__refs" aria-label="参考图（可粘贴）">
      <div
        v-for="(item, index) in referencePreviews"
        :key="`${item.name}-${index}`"
        class="ai-composer__thumb"
      >
        <img :src="item.url" :alt="item.name || `参考图 ${index + 1}`" />
        <button
          type="button"
          class="ai-composer__thumb-remove"
          title="移除参考图"
          @click.stop="emit('remove-file', index)"
        >
          <el-icon><Close /></el-icon>
        </button>
      </div>
      <button
        v-for="n in emptySlots"
        :key="`slot-${n}`"
        type="button"
        class="ai-composer__slot"
        title="点击上传或粘贴图片"
        @click.stop="openPicker"
      />
    </div>

    <el-input
      type="textarea"
      :rows="3"
      resize="none"
      :model-value="prompt"
      placeholder="请输入提示词；也可直接粘贴图片做图生图"
      class="ai-composer__prompt"
      @update:model-value="emit('update:prompt', $event)"
      @keydown.ctrl.enter.prevent="emit('submit')"
      @paste="onPaste"
    />

    <div class="ai-composer__bar">
      <button
        type="button"
        class="ai-composer__advanced"
        :aria-expanded="advancedOpen"
        @click.stop="toggleAdvanced"
      >
        进阶参数
        <span class="ai-composer__advanced-caret">{{ advancedOpen ? '▾' : '▸' }}</span>
      </button>
      <span
        v-if="!advancedOpen"
        class="ai-composer__advanced-summary"
        :title="advancedSummary"
        @click.stop="toggleAdvanced"
      >
        {{ advancedSummary }}
      </span>

      <div v-show="advancedOpen" class="ai-composer__controls" @click.stop>
        <div class="ctrl">
          <span class="ctrl__label">质量</span>
          <el-select
            :model-value="quality"
            size="small"
            style="width: 88px"
            teleported
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
            teleported
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
            teleported
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

      <div class="ai-composer__actions" @click.stop>
        <el-badge :value="referencePreviews.length || ''" :hidden="!referencePreviews.length">
          <el-button :icon="Paperclip" circle title="上传参考图" @click="openPicker" />
        </el-badge>
        <el-button
          v-if="referencePreviews.length"
          link
          type="info"
          size="small"
          @click="emit('clear-files')"
        >
          清空参考图
        </el-button>
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
  background: #fff;
  box-shadow: var(--ch-shadow-md);
  outline: none;
}

.ai-composer:focus-within {
  border-color: #93c5fd;
}

.ai-composer__refs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.ai-composer__slot {
  width: 56px;
  height: 56px;
  border: 1px dashed #dbe3ef;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  padding: 0;
}

.ai-composer__slot:hover {
  border-color: #93c5fd;
  background: #f8fbff;
}

.ai-composer__thumb {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.ai-composer__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.ai-composer__thumb-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.65);
  color: #fff;
  display: grid;
  place-items: center;
  cursor: pointer;
  padding: 0;
  font-size: 10px;
}

.ai-composer__prompt :deep(.el-textarea__inner) {
  border: 0;
  box-shadow: none !important;
  padding: 4px 2px 8px;
  font-size: 15px;
  line-height: 1.5;
  color: var(--ch-text);
  background: #fff;
}

.ai-composer__prompt :deep(.el-textarea__inner::placeholder) {
  color: #cbd5e1;
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

.ai-composer__advanced:hover {
  color: var(--ch-primary, #2563eb);
}

.ai-composer__advanced-caret {
  margin-left: 2px;
}

.ai-composer__advanced-summary {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #94a3b8;
  cursor: pointer;
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
