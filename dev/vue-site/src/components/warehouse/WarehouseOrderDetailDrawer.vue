<script setup>
import { formatUtc8 } from '@/utils/time'
import { computed } from 'vue'
import { Document, Files } from '@element-plus/icons-vue'
import { SOURCE_TYPE_OPTIONS } from '@/constants/warehouseOrders'
import {
  formatFileSize,
  fileIconType,
  statusLabel,
  statusTagType,
  summarizeItems,
} from '@/utils/warehouseOrders'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  order: { type: Object, default: null },
  showActions: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'review', 'ship', 'cancel'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const sourceTypeLabel = computed(() => {
  const found = SOURCE_TYPE_OPTIONS.find((item) => item.value === props.order?.sourceType)
  return found?.label || '—'
})

const itemSummary = computed(() => summarizeItems(props.order?.items || []))
</script>

<template>
  <el-drawer v-model="visible" :title="order ? `出库单 ${order.orderNo}` : '订单详情'" size="520px">
    <template v-if="order">
      <div class="detail-head">
        <el-tag :type="statusTagType(order.status)" effect="light">
          {{ statusLabel(order.status) }}
        </el-tag>
        <span class="detail-time">提交于 {{ formatUtc8(order.submittedAt) }}</span>
      </div>

      <el-descriptions :column="1" border class="detail-block">
        <el-descriptions-item label="出库仓库">{{ order.warehouseName || '—' }}</el-descriptions-item>
        <el-descriptions-item label="下单人">{{ order.submittedByName }}</el-descriptions-item>
        <el-descriptions-item label="货源类型">{{ sourceTypeLabel }}</el-descriptions-item>
        <el-descriptions-item label="来源">{{ order.sourceLabel }}</el-descriptions-item>
        <el-descriptions-item v-if="order.platformOrderNo" label="平台订单">
          {{ order.platformOrderNo }}
          <el-tag v-if="order.shipRequestType === 'urge'" type="warning" size="small" effect="plain">
            含催促
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="货品汇总">
          {{ itemSummary.skuCount }} 种 / 共 {{ itemSummary.totalQty }} 件
        </el-descriptions-item>
        <el-descriptions-item label="备注">{{ order.remark || '—' }}</el-descriptions-item>
      </el-descriptions>

      <h4 class="section-title">货品明细</h4>
      <el-table :data="order.items" size="small" border>
        <el-table-column prop="productName" label="货品" min-width="140" />
        <el-table-column prop="sku" label="SKU" width="110" />
        <el-table-column label="数量" width="90">
          <template #default="{ row }">{{ row.quantity }} {{ row.unit }}</template>
        </el-table-column>
      </el-table>

      <h4 v-if="order.attachments?.length" class="section-title">附件</h4>
      <ul v-if="order.attachments?.length" class="attachment-list">
        <li v-for="file in order.attachments" :key="file.id">
          <el-icon><Document v-if="fileIconType(file.name) === 'pdf'" /><Files v-else /></el-icon>
          <span>{{ file.name }}</span>
          <em>{{ formatFileSize(file.size) }}</em>
        </li>
      </ul>

      <h4 v-if="order.cartonMarks?.length" class="section-title">箱唛</h4>
      <ul v-if="order.cartonMarks?.length" class="attachment-list">
        <li v-for="file in order.cartonMarks" :key="file.id">
          <el-icon><Document v-if="fileIconType(file.name) === 'pdf'" /><Files v-else /></el-icon>
          <span>{{ file.name }}</span>
          <em>{{ formatFileSize(file.size) }}</em>
        </li>
      </ul>

      <h4 v-if="order.labels?.length" class="section-title">标签</h4>
      <ul v-if="order.labels?.length" class="attachment-list">
        <li v-for="file in order.labels" :key="file.id">
          <el-icon><Document v-if="fileIconType(file.name) === 'pdf'" /><Files v-else /></el-icon>
          <span>{{ file.name }}</span>
          <em>{{ formatFileSize(file.size) }}</em>
        </li>
      </ul>

      <template v-if="order.shipUrges?.length">
        <h4 class="section-title">发货催促</h4>
        <el-timeline class="urge-timeline">
          <el-timeline-item
            v-for="item in order.shipUrges"
            :key="item.id"
            :timestamp="item.at"
            type="warning"
            placement="top"
          >
            <strong>{{ item.byName || '运营' }}</strong>
            <p>{{ item.remark || '催促发货' }}</p>
          </el-timeline-item>
        </el-timeline>
      </template>

      <template v-if="order.warehouseReview">
        <h4 class="section-title">仓库反馈</h4>
        <el-alert
          :type="order.status === 'blocked' ? 'warning' : 'success'"
          :closable="false"
          show-icon
          :title="order.status === 'blocked'
            ? '仓库反馈：暂不可发'
            : (order.warehouseReview.releasedAt ? '已补货，确认可发货' : '仓库确认可发货')"
          style="margin-bottom: 12px"
        />
        <el-descriptions :column="1" border class="detail-block">
          <el-descriptions-item v-if="order.warehouseReview.estimatedShipAt" label="预计出库">
            {{ formatUtc8(order.warehouseReview.estimatedShipAt) }}
          </el-descriptions-item>
          <el-descriptions-item v-if="order.warehouseReview.missingMaterials" label="缺少材料">
            {{ order.warehouseReview.missingMaterials }}
          </el-descriptions-item>
          <el-descriptions-item v-if="order.warehouseReview.packagingNotes" label="包装说明">
            {{ order.warehouseReview.packagingNotes }}
          </el-descriptions-item>
          <el-descriptions-item v-if="order.warehouseReview.extraOrderNotes" label="追加订货">
            {{ order.warehouseReview.extraOrderNotes }}
          </el-descriptions-item>
          <el-descriptions-item label="综合反馈">
            {{ order.warehouseReview.reviewRemark }}
          </el-descriptions-item>
          <el-descriptions-item label="审批人">
            {{ order.warehouseReview.reviewedByName }} · {{ formatUtc8(order.warehouseReview.reviewedAt) }}
          </el-descriptions-item>
        </el-descriptions>

        <template v-if="order.warehouseReview.releasedAt">
          <h4 class="section-title">补货确认</h4>
          <el-descriptions :column="1" border class="detail-block">
            <el-descriptions-item label="可发说明">
              {{ order.warehouseReview.releaseRemark }}
            </el-descriptions-item>
            <el-descriptions-item label="确认人">
              {{ order.warehouseReview.releasedByName }} · {{ formatUtc8(order.warehouseReview.releasedAt) }}
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </template>

      <div v-if="showActions" class="detail-actions">
        <slot name="actions" />
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.detail-time {
  font-size: 12px;
  color: var(--ch-text-muted);
}

.detail-block {
  margin-bottom: 16px;
}

.section-title {
  margin: 16px 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.attachment-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.attachment-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--ch-border);
  font-size: 13px;
}

.attachment-list em {
  margin-left: auto;
  font-style: normal;
  color: var(--ch-text-muted);
  font-size: 12px;
}

.detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--ch-border);
}
</style>
