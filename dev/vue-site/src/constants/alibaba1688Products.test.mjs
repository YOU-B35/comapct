import test from 'node:test'
import assert from 'node:assert/strict'
import { PRODUCT_TABS } from './alibaba1688Products.js'

test('1688 product tabs match backend categories', () => {
  assert.deepEqual(
    PRODUCT_TABS.map(({ tab, categoryCode }) => [tab, categoryCode]),
    [
      ['all', null],
      ['potential', 'growth_potential'],
      ['yanxuan', 'growth_yanxuan'],
      ['index', 'growth_index'],
      ['on_sale', 'status_on_sale'],
      ['pending_list', 'status_pending_list'],
      ['sold_out', 'status_sold_out'],
      ['reviewing', 'status_reviewing'],
      ['violation_off', 'status_violation_off'],
    ],
  )
})
