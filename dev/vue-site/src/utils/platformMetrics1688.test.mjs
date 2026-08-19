import test from 'node:test'
import assert from 'node:assert/strict'
import { build1688SalesMetrics } from './alibaba1688.js'

test('1688 sales uses product gmv1d not purchase amount', () => {
  const metrics = build1688SalesMetrics({
    products: [{ gmv1d: '100' }, { gmv1d: '50' }],
    purchaseOrders: [{ amount: 9999, status: 'pending_payment', storeId: 's1' }],
    supplierAlerts: [{ resolved: false, storeId: 's1' }],
  })
  assert.equal(metrics.revenue, 150)
  assert.equal(metrics.orders, 2)
  assert.ok(metrics.alerts >= 1)
})

test('1688 sales prefers retail summary when provided', () => {
  const metrics = build1688SalesMetrics({
    products: [{ gmv1d: '99999' }],
    purchaseOrders: [],
    supplierAlerts: [],
    summary: {
      paid_sales: 5325,
      net_sales: 4800,
      paid_order_count: 3,
      refund_order_count: 1,
      sold_product_count: 2,
    },
  })
  assert.equal(metrics.revenue, 4800)
  assert.equal(metrics.orders, 3)
  assert.equal(metrics.alerts, 3)
  assert.match(metrics.revenueText, /4,800|4800/)
})

test('1688 retail summary falls back to paid sales when net is absent', () => {
  const metrics = build1688SalesMetrics({
    products: [],
    purchaseOrders: [],
    supplierAlerts: [],
    summary: { paid_sales: 100, paid_order_count: 1 },
  })
  assert.equal(metrics.revenue, 100)
  assert.equal(metrics.orders, 1)
})
