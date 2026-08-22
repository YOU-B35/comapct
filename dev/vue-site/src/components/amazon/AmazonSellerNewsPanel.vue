<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { summarizeSellerNews } from '@/utils/amazon'
import AmazonPanelHeader from '@/components/amazon/AmazonPanelHeader.vue'

const props = defineProps({
  news: { type: Array, default: () => [] },
  syncedAt: { type: String, default: '' },
  summaryText: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showStoreColumn: { type: Boolean, default: false },
  storeNameMap: { type: Object, default: () => ({}) },
})

defineEmits(['open-history'])

const summary = computed(() => summarizeSellerNews(props.news))

const sorted = computed(() =>
  [...props.news].sort((a, b) => {
    if (a.importance === 'high' && b.importance !== 'high') return -1
    if (b.importance === 'high' && a.importance !== 'high') return 1
    return String(b.publishedAt).localeCompare(String(a.publishedAt))
  }),
)
</script>

<template>
  <div class="amz-panel">
    <AmazonPanelHeader
      title="卖家新闻"
      description="平台通知已自动归纳，用最直白的话告诉你今天该注意什么"
      :synced-at="syncedAt"
      :summary-text="summaryText"
      @open-history="$emit('open-history')"
    />

    <div class="mini-stats">
      <div class="mini-stat is-danger">
        <span class="mini-stat__value">{{ summary.highPriority }}</span>
        <span class="mini-stat__label">重要通知</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.today }}</span>
        <span class="mini-stat__label">今日新增</span>
      </div>
      <div class="mini-stat">
        <span class="mini-stat__value">{{ summary.total }}</span>
        <span class="mini-stat__label">近期待阅</span>
      </div>
    </div>

    <div class="news-list">
      <article
        v-for="item in sorted"
        :key="item.id"
        class="news-card"
        :class="{ 'is-high': item.importance === 'high' }"
      >
        <div class="news-head">
          <el-tag v-if="item.importance === 'high'" type="danger" size="small" effect="plain">重要</el-tag>
          <el-tag size="small" effect="plain">{{ item.category }}</el-tag>
          <span v-if="showStoreColumn" class="news-store">{{ storeNameMap[item.storeId] }}</span>
          <span class="news-time">{{ formatUtc8(item.publishedAt) }}</span>
        </div>
        <h4 class="news-title">{{ item.title }}</h4>
        <p class="news-summary">{{ item.summaryPlain }}</p>
      </article>
    </div>

    <el-empty v-if="!loading && !sorted.length" description="暂无卖家新闻" :image-size="72" />
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.mini-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.mini-stat {
  display: grid; gap: 4px; padding: 12px 14px;
  border-radius: 8px; background: var(--el-fill-color-lighter);
}
.mini-stat.is-danger .mini-stat__value { color: var(--el-color-danger); }
.mini-stat__value { font-size: 18px; font-weight: 700; }
.mini-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }
.news-list { display: grid; gap: 12px; }
.news-card {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}
.news-card.is-high {
  border-left: 3px solid var(--el-color-danger);
  background: #fef2f2;
}
.news-head {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 8px;
}
.news-store, .news-time {
  font-size: 12px; color: var(--el-text-color-secondary);
}
.news-time { margin-left: auto; }
.news-title { margin: 0 0 8px; font-size: 15px; }
.news-summary {
  margin: 0; font-size: 14px; line-height: 1.65;
  color: var(--el-text-color-regular);
}
</style>
