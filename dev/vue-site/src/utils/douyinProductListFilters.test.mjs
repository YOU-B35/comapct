import test from 'node:test'
import assert from 'node:assert/strict'
import { filterTodaySalesOrders, filterNewListedProducts } from './douyinProductListFilters.js'

const NOW = new Date('2026-08-17T15:00:00+08:00')

test('filterTodaySalesOrders keeps only today effective orders', () => {
  const orders = [
    { orderNo: '1', status: '待发货', orderedAt: '2026-08-17 10:00:00' },
    { orderNo: '2', status: '已关闭', orderedAt: '2026-08-17 11:00:00' },
    { orderNo: '3', status: '待发货', orderedAt: '2026-08-16 23:00:00' },
    { orderNo: '4', status: '已发货', orderedAt: '2026-08-17 20:00:00' },
  ]
  const list = filterTodaySalesOrders(orders, { now: NOW })
  assert.deepEqual(
    list.map((o) => o.orderNo),
    ['1', '4'],
  )
})

test('filterNewListedProducts keeps published within last 3 calendar days', () => {
  const products = [
    { productId: 'a', productName: '新1', publishedAt: '2026-08-17 09:00:00', sales: 1 },
    { productId: 'b', productName: '新2', publishedAt: '2026-08-15 01:00:00', sales: 2 },
    { productId: 'c', productName: '旧', publishedAt: '2026-08-14 23:00:00', sales: 9 },
    { productId: 'd', productName: '无时间', sales: 3 },
  ]
  const list = filterNewListedProducts(products, { now: NOW, days: 3 })
  assert.deepEqual(
    list.map((p) => p.productId),
    ['a', 'b'],
  )
})
