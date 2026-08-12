<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Promotion, UserFilled } from '@element-plus/icons-vue'
import {
  AI_EMPLOYEE_MOCK_REPLIES,
  AI_EMPLOYEE_WELCOME,
  AI_SUGGESTED_PROMPTS,
} from '@/constants/aiOffice'

const props = defineProps({
  scope: { type: String, default: 'employee' },
  userName: { type: String, default: '运营专员' },
  platforms: { type: String, default: '' },
})

const input = ref('')
const loading = ref(false)
const scrollRef = ref(null)

const platformLabel = computed(() => props.platforms || '运营')

const messages = ref([
  {
    role: 'assistant',
    content: AI_EMPLOYEE_WELCOME(props.userName, platformLabel.value),
    time: formatTime(new Date()),
  },
])

const suggestedPrompts = computed(() => AI_SUGGESTED_PROMPTS)

const showWelcomeCards = computed(
  () => messages.value.length === 1 && messages.value[0].role === 'assistant',
)

function formatTime(date) {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function pickReply(text) {
  const t = text.toLowerCase()
  if (t.includes('摘要') || t.includes('汇总')) return AI_EMPLOYEE_MOCK_REPLIES.summary
  if (t.includes('优先级') || t.includes('待办')) return AI_EMPLOYEE_MOCK_REPLIES.priority
  if (t.includes('标题') || t.includes('listing') || t.includes('卖点') || t.includes('bullet'))
    return AI_EMPLOYEE_MOCK_REPLIES.listing
  if (t.includes('差评') || t.includes('回复') || t.includes('买家'))
    return AI_EMPLOYEE_MOCK_REPLIES.review
  if (t.includes('补货') || t.includes('库存')) return AI_EMPLOYEE_MOCK_REPLIES.restock
  if (t.includes('滞销')) return AI_EMPLOYEE_MOCK_REPLIES.slow
  if (t.includes('竞店') || t.includes('竞品')) return AI_EMPLOYEE_MOCK_REPLIES.competitor
  if (t.includes('亏损')) return AI_EMPLOYEE_MOCK_REPLIES.loss
  return AI_EMPLOYEE_MOCK_REPLIES.default
}

function renderContent(text) {
  return (text || '').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
}

async function scrollToBottom() {
  await nextTick()
  const wrap = scrollRef.value?.wrapRef
  if (wrap) wrap.scrollTop = wrap.scrollHeight
}

async function sendMessage(text) {
  const content = (text || input.value).trim()
  if (!content || loading.value) return

  messages.value.push({ role: 'user', content, time: formatTime(new Date()) })
  input.value = ''
  loading.value = true
  await scrollToBottom()

  await new Promise((r) => setTimeout(r, 900))

  messages.value.push({
    role: 'assistant',
    content: pickReply(content),
    time: formatTime(new Date()),
  })
  loading.value = false
  await scrollToBottom()
}

watch(
  () => [props.userName, props.platforms],
  () => {
    messages.value = [
      {
        role: 'assistant',
        content: AI_EMPLOYEE_WELCOME(props.userName, platformLabel.value),
        time: formatTime(new Date()),
      },
    ]
  },
)

defineExpose({ sendMessage })
</script>

<template>
  <div class="chat-shell">
    <el-scrollbar ref="scrollRef" class="chat-scroll">
      <div class="chat-thread">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="chat-row"
          :class="msg.role"
        >
          <div v-if="msg.role === 'assistant'" class="chat-avatar chat-avatar--ai">
            <span>AI</span>
          </div>

          <div class="chat-bubble-wrap">
            <div class="chat-bubble" :class="`chat-bubble--${msg.role}`">
              <div class="chat-content" v-html="renderContent(msg.content)" />
            </div>
            <span class="chat-time">{{ msg.time }}</span>
          </div>

          <div v-if="msg.role === 'user'" class="chat-avatar chat-avatar--user">
            <el-icon><UserFilled /></el-icon>
          </div>
        </div>

        <div v-if="loading" class="chat-row assistant">
          <div class="chat-avatar chat-avatar--ai"><span>AI</span></div>
          <div class="chat-bubble-wrap">
            <div class="chat-bubble chat-bubble--assistant chat-bubble--typing">
              <span class="typing-dot" />
              <span class="typing-dot" />
              <span class="typing-dot" />
            </div>
          </div>
        </div>

        <div v-if="showWelcomeCards" class="welcome-cards">
          <button
            v-for="item in suggestedPrompts"
            :key="item.title"
            type="button"
            class="welcome-card"
            @click="sendMessage(item.prompt)"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.desc }}</span>
          </button>
        </div>
      </div>
    </el-scrollbar>

    <div class="chat-composer">
      <div class="composer-box">
        <el-input
          v-model="input"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="描述你的问题，或从左侧选择 AI 技能…"
          resize="none"
          @keydown.enter.exact.prevent="sendMessage()"
        />
        <el-button
          type="primary"
          class="composer-send"
          :icon="Promotion"
          :loading="loading"
          :disabled="!input.trim()"
          @click="sendMessage()"
        >
          发送
        </el-button>
      </div>
      <p class="composer-hint">Demo 模式 · 基于样本数据模拟回复，Enter 发送</p>
    </div>
  </div>
</template>

<style scoped>
.chat-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-radius: 10px;
  border: 1px solid var(--ch-border);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  overflow: hidden;
}

.chat-scroll {
  flex: 1;
  min-height: 0;
  background:
    radial-gradient(800px 280px at 10% -20%, rgba(31, 79, 214, 0.05), transparent 55%),
    var(--ch-surface);
}

.chat-scroll :deep(.el-scrollbar__view) {
  min-height: 100%;
}

.chat-thread {
  padding: 20px 20px 8px;
  min-height: 100%;
}

.chat-row {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
  align-items: flex-start;
}

.chat-row.user {
  flex-direction: row-reverse;
}

.chat-avatar {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
}

.chat-avatar--ai {
  background: var(--ch-primary);
  color: #fff;
}

.chat-avatar--user {
  background: var(--ch-surface-muted);
  color: var(--ch-text-secondary);
  font-size: 14px;
  border: 1px solid var(--ch-border);
}

.chat-bubble-wrap {
  max-width: min(72%, 560px);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-row.user .chat-bubble-wrap {
  align-items: flex-end;
}

.chat-bubble {
  padding: 12px 14px;
  border-radius: 10px;
  line-height: 1.65;
  font-size: 14px;
}

.chat-bubble--assistant {
  background: #f7f9fc;
  color: var(--ch-text);
  border: 1px solid var(--ch-border);
  border-top-left-radius: 4px;
}

.chat-bubble--user {
  background: var(--ch-primary);
  color: #fff;
  border-top-right-radius: 4px;
}

.chat-bubble--typing {
  display: flex;
  gap: 5px;
  padding: 14px 16px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ch-text-muted);
  animation: typing 1.2s ease-in-out infinite;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing {
  0%,
  80%,
  100% {
    opacity: 0.35;
    transform: scale(0.85);
  }
  40% {
    opacity: 1;
    transform: scale(1);
  }
}

.chat-content :deep(strong) {
  font-weight: 650;
  color: inherit;
}

.chat-time {
  font-size: 11px;
  color: var(--ch-text-muted);
  padding: 0 4px;
}

.welcome-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 8px;
  padding-left: 44px;
}

.welcome-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  text-align: left;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s, transform 0.15s;
}

.welcome-card:hover {
  border-color: var(--ch-primary-muted);
  background: linear-gradient(180deg, #f8faff 0%, #fff 70%);
  box-shadow: var(--ch-shadow-sm);
  transform: translateY(-1px);
}

.welcome-card strong {
  font-size: 13px;
  font-weight: 650;
  color: var(--ch-text);
}

.welcome-card span {
  font-size: 12px;
  color: var(--ch-text-muted);
  line-height: 1.4;
}

.chat-composer {
  flex-shrink: 0;
  padding: 12px 16px 14px;
  border-top: 1px solid var(--ch-border);
  background: #fbfcfe;
}

.composer-box {
  display: flex;
  gap: 10px;
  align-items: flex-end;
  padding: 8px 8px 8px 14px;
  border: 1px solid var(--ch-border);
  border-radius: 10px;
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-xs);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.composer-box:focus-within {
  border-color: var(--ch-primary-muted);
  box-shadow: var(--ch-shadow-focus);
}

.composer-box :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none !important;
  padding: 4px 0;
  background: transparent;
  resize: none;
}

.composer-send {
  flex-shrink: 0;
  border-radius: 8px;
}

.composer-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--ch-text-muted);
  text-align: center;
}

@media (max-width: 900px) {
  .welcome-cards {
    grid-template-columns: 1fr;
    padding-left: 0;
  }

  .chat-bubble-wrap {
    max-width: 85%;
  }
}
</style>
