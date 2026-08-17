import { loadAlibaba1688DemoData } from './alibaba1688DemoLocal'
import { enrichPurchaseOrder, enrichSupplierAlert } from '@/utils/alibaba1688'
import {
  canUseAlibaba1688Backend,
  fetchAlibaba1688Operational,
} from './alibaba1688Api'

export { canUseAlibaba1688Backend } from './alibaba1688Api'
export {
  triggerAlibaba1688Crawl,
  refreshAlibaba1688DataWithCrawl,
  fetchAlibaba1688Operational,
} from './alibaba1688Api'

function demoPayload(stores = []) {
  const data = loadAlibaba1688DemoData(stores)
  return {
    success: true,
    data: {
      purchaseOrders: data.purchaseOrders.map(enrichPurchaseOrder),
      supplierAlerts: data.supplierAlerts.map(enrichSupplierAlert),
      supplierRanking: [],
      overview: null,
      syncedAt: new Date().toISOString().replace('T', ' ').slice(0, 19),
    },
  }
}

export async function loadAlibaba1688OperationalData(stores = [], auth) {
  if (canUseAlibaba1688Backend(auth)) {
    try {
      const data = await fetchAlibaba1688Operational()
      return {
        success: true,
        data: {
          purchaseOrders: (data.purchaseOrders || []).map(enrichPurchaseOrder),
          supplierAlerts: (data.supplierAlerts || []).map(enrichSupplierAlert),
          supplierRanking: data.supplierRanking || [],
          overview: data.overview || null,
          syncedAt: data.syncedAt || '',
        },
      }
    } catch {
      // fall through to demo
    }
  }
  return demoPayload(stores)
}

export function loadAlibaba1688PurchaseOrders(stores = []) {
  const data = loadAlibaba1688DemoData(stores)
  return {
    success: true,
    data: {
      orders: data.purchaseOrders.map(enrichPurchaseOrder),
      syncedAt: new Date().toISOString().replace('T', ' ').slice(0, 19),
    },
  }
}

export function loadAlibaba1688SupplierAlerts(stores = []) {
  const data = loadAlibaba1688DemoData(stores)
  return {
    success: true,
    data: {
      alerts: data.supplierAlerts.map(enrichSupplierAlert),
      syncedAt: new Date().toISOString().replace('T', ' ').slice(0, 19),
    },
  }
}
