import test from 'node:test'
import assert from 'node:assert/strict'
import { buildTodayHotProducts, isExcludedOrderStatus } from './douyinTodayHotProducts.js'

const NOW = new Date('2026-08-17T12:00:00+08:00')

test('excludes closed/cancelled statuses', () => {
  assert.equal(isExcludedOrderStatus('已关闭'), true)
  assert.equal(isExcludedOrderStatus('已取消'), true)
  assert.equal(isExcludedOrderStatus('关闭'), true)
  assert.equal(isExcludedOrderStatus('待发货'), false)
  assert.equal(isExcludedOrderStatus('已发货'), false)
})

test('aggregates last 24h effective qty by store+name; threshold 10', () => {
  const orders = [
    { storeId: 's1', productName: '饵料A', quantity: 6, status: '待发货', orderedAt: '2026-08-17 10:00:00' },
    { storeId: 's1', productName: '饵料A', quantity: 5, status: '已发货', orderedAt: '2026-08-17 11:00:00' },
    { storeId: 's1', productName: '饵料B', quantity: 9, status: '待发货', orderedAt: '2026-08-17 11:00:00' },
    { storeId: 's1', productName: '饵料A', quantity: 20, status: '已关闭', orderedAt: '2026-08-17 11:30:00' },
    { storeId: 's1', productName: '旧品', quantity: 50, status: '已发货', orderedAt: '2026-08-15 10:00:00' },
  ]
  const products = [
    { storeId: 's1', productName: '饵料A', productId: 'p1', mainImage: 'img', price: 10, stock: 3, sales: 100 },
  ]
  const list = buildTodayHotProducts(orders, products, { now: NOW, minQty: 10 })
  assert.equal(list.length, 1)
  assert.equal(list[0].productName, '饵料A')
  assert.equal(list[0].todaySales, 11)
  assert.equal(list[0].productId, 'p1')
  assert.equal(list[0].mainImage, 'img')
  assert.equal(list[0].sales, 100)
})

test('matches catalog by productId when titles differ', () => {
  const orders = [
    {
      storeId: 's1',
      productId: '3836',
      productName: '订单标题短版',
      quantity: 12,
      status: '已发货',
      orderedAt: '2026-08-17 09:00:00',
    },
  ]
  const products = [
    {
      storeId: 's1',
      productId: '3836',
      productName: '商品库标题完整版含鱼钩',
      price: 6.9,
      stock: 100,
      statusLabel: '售卖中',
    },
  ]
  const list = buildTodayHotProducts(orders, products, { now: NOW, minQty: 10 })
  assert.equal(list.length, 1)
  assert.equal(list[0].todaySales, 12)
  assert.equal(list[0].price, 6.9)
  assert.equal(list[0].stock, 100)
  assert.equal(list[0].statusLabel, '售卖中')
  assert.equal(list[0].productName, '商品库标题完整版含鱼钩')
})

test('aggregates same productId even if order titles differ', () => {
  const orders = [
    { storeId: 's1', productId: 'pid1', productName: '标题A', quantity: 6, status: '待发货', orderedAt: '2026-08-17 10:00:00' },
    { storeId: 's1', productId: 'pid1', productName: '标题B', quantity: 5, status: '已发货', orderedAt: '2026-08-17 11:00:00' },
  ]
  const products = [
    { storeId: 's1', productId: 'pid1', productName: '库标题', price: 1 },
  ]
  const list = buildTodayHotProducts(orders, products, { now: NOW, minQty: 10 })
  assert.equal(list.length, 1)
  assert.equal(list[0].todaySales, 11)
  assert.equal(list[0].productId, 'pid1')
})

test('sorts by todaySales desc', () => {
  const orders = [
    { storeId: 's1', productName: '低', quantity: 10, status: '待发货', orderedAt: '2026-08-17 10:00:00' },
    { storeId: 's1', productName: '高', quantity: 15, status: '待发货', orderedAt: '2026-08-17 10:00:00' },
  ]
  const list = buildTodayHotProducts(orders, [], { now: NOW, minQty: 10 })
  assert.deepEqual(list.map((r) => r.productName), ['高', '低'])
  assert.equal(list[0].todaySales, 15)
})

test('keeps row without catalog match', () => {
  const orders = [
    { storeId: 's1', productName: '仅订单有', quantity: 12, status: '已发货', orderedAt: '2026-08-17 09:00:00' },
  ]
  const list = buildTodayHotProducts(orders, [], { now: NOW, minQty: 10 })
  assert.equal(list.length, 1)
  assert.equal(list[0].todaySales, 12)
  assert.equal(list[0].productId, undefined)
})

test('falls back to createdAt when orderedAt missing', () => {
  const orders = [
    { storeId: 's1', productName: '回退', quantity: 10, status: '待发货', createdAt: '2026-08-17 08:00:00' },
  ]
  const list = buildTodayHotProducts(orders, [], { now: NOW, minQty: 10 })
  assert.equal(list.length, 1)
  assert.equal(list[0].todaySales, 10)
})
