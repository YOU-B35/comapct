import { nowUtc8DateString, nowUtc8String } from '@/utils/time'
import { ORDER_STATUS_MAP } from '@/constants/warehouseOrders'

export function formatFileSize(bytes = 0) {
  const size = Number(bytes) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function fileIconType(name = '') {
  const lower = name.toLowerCase()
  if (lower.endsWith('.pdf')) return 'pdf'
  if (lower.endsWith('.doc') || lower.endsWith('.docx')) return 'word'
  if (lower.endsWith('.xls') || lower.endsWith('.xlsx')) return 'excel'
  if (/\.(png|jpe?g|gif|webp)$/.test(lower)) return 'image'
  return 'file'
}

export function statusLabel(status) {
  return ORDER_STATUS_MAP[status]?.label || status
}

export function statusTagType(status) {
  return ORDER_STATUS_MAP[status]?.tag || 'info'
}

export function summarizeItems(items = []) {
  const totalQty = items.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0)
  const skuCount = items.length
  return { totalQty, skuCount }
}

export function attachmentFromUpload(file) {
  return {
    id: `att_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    name: file.name,
    size: file.size || 0,
    mime: file.type || '',
    uploadedAt: nowUtc8String(),
  }
}

export function normalizeUploadedFiles(files = [], prefix = 'att') {
  return (files || []).map((file, index) => ({
    id: file.id || `${prefix}_${Date.now()}_${index}`,
    name: file.name,
    size: file.size || 0,
    mime: file.mime || '',
    uploadedAt: file.uploadedAt || nowUtc8String(),
  }))
}

export function emptyOrderForm() {
  return {
    warehouseId: '',
    sourceType: 'marketplace',
    sourcePlatform: 'temu',
    sourceStoreName: '',
    b2bCustomerName: '',
    remark: '',
    items: [{ id: `li_${Date.now()}`, productName: '', sku: '', quantity: 1, unit: '件' }],
    attachments: [],
    cartonMarks: [],
    labels: [],
  }
}

export function emptyReviewForm() {
  return {
    canShip: true,
    estimatedShipAt: '',
    missingMaterials: '',
    packagingNotes: '',
    extraOrderNotes: '',
    reviewRemark: '',
  }
}

export function emptyReleaseForm() {
  return {
    estimatedShipAt: '',
    releaseRemark: '',
  }
}
