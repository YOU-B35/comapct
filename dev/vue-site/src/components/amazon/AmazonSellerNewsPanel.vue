<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { useFuzzySearchPagination } from '@/composables/useFuzzySearchPagination'
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

const sorted = computed(() =>
  [...props.news].sort((a, b) => {
    if (a.importance === 'high' && b.importance !== 'high') return -1
    if (b.importance === 'high' && a.importance !== 'high') return 1
    return String(b.publishedAt).localeCompare(String(a.publishedAt))
  }),
)

const { page, pageSize, total, paged } = useFuzzySearchPagination(sorted, {
  pageSize: 15,
  fields: [],
})
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

    <div class="news-list">
      <article
        v-for="item in paged"
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

    <div class="pagination-row">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        small
        layout="total, prev, pager, next"
        :total="total"
      />
    </div>

    <el-empty v-if="!loading && !sorted.length" description="暂无卖家新闻" :image-size="72" />
  </div>
</template>

<style scoped>
.amz-panel { display: grid; gap: 16px; }
.news-list { display: grid; gap: 8px; }
.news-card {
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}
.news-card.is-high {
  border-left: 3px solid var(--el-color-danger);
  background: #fef2f2;
}
.news-head {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-bottom: 5px;
}
.news-store, .news-time {
  font-size: 12px; color: var(--el-text-color-secondary);
}
.news-time { margin-left: auto; }
.news-title { margin: 0 0 5px; font-size: 13px; }
.news-summary {
  margin: 0; font-size: 13px; line-height: 1.5;
  color: var(--el-text-color-regular);
}
.pagination-row { display: flex; justify-content: flex-end; margin-top: 10px; }
</style>
