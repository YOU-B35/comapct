/** TM-P5 smoke: simulate Temu four-tab counts from live API */
import http from 'node:http'
import { applyServerAlgorithms } from '../dev/vue-site/src/utils/temuServerAlgo.js'
import { mapReptileSaleToTemuProduct } from '../dev/vue-site/src/utils/mapReptileSaleToTemuProduct.js'
import { enrichAllProducts } from '../dev/vue-site/src/utils/temu.js'

function request(method, path, body, token) {
  return new Promise((resolve, reject) => {
    const headers = { 'Content-Type': 'application/json' }
    if (token) headers.Authorization = `Bearer ${token}`
    const opts = { hostname: '127.0.0.1', port: 18080, path, method, headers }
    const req = http.request(opts, (res) => {
      let data = ''
      res.on('data', (c) => { data += c })
      res.on('end', () => {
        try { resolve(JSON.parse(data)) } catch (e) { reject(e) }
      })
    })
    req.on('error', reject)
    if (body) req.write(JSON.stringify(body))
    req.end()
  })
}

async function main() {
  const login = await request('POST', '/api/auth/login', {
    account: 'HangZhouYiTuo',
    password: 'HangZhouYiTuo',
  })
  const token = login.data.token
  const shopId = '634418211126671'
  const op = await request('GET', `/api/temu/operational?shop_id=${shopId}&report_time=2026-07-22`, null, token)

  const {
    products = [],
    lose_products = [],
    low_warnings = [],
    inventory_warnings = [],
    overload_products = [],
    report_time,
  } = op

  const enriched = enrichAllProducts(products.map((row) => mapReptileSaleToTemuProduct(row)))
  const merged = applyServerAlgorithms(enriched, {
    loseProducts: lose_products,
    lowWarnings: low_warnings,
    inventoryWarnings: inventory_warnings,
    overloadProducts: overload_products,
  })

  console.log('report_time', report_time)
  console.log('arrays', { products: products.length, lose: lose_products.length, low: low_warnings.length, inv: inventory_warnings.length, overload: overload_products.length })

  const tabCounts = {
    profit: merged.length,
    loss: merged.filter((p) => p.isLoss).length,
    slow: merged.filter((p) => p.slowMoving).length,
    hot: merged.filter((p) => p.isHot).length,
    restock: merged.filter((p) => p.restock?.urgency && p.restock.urgency !== 'normal').length,
  }
  console.log('tab counts after frontend pipeline:', tabCounts)

  try {
    const comp = await request('POST', '/api/temu/competitors/discover', { market: 'ZA', keyword: 'fishing' }, token)
    console.log('competitor discover keys:', Object.keys(comp))
    console.log('competitor data sample:', JSON.stringify(comp.data || comp).slice(0, 300))
  } catch (e) {
    console.log('competitor discover error:', e.message)
  }

  try {
    const crawl = await request('POST', '/api/temu/crawl', { force: true }, token)
    console.log('crawl trigger status:', crawl.code, crawl.data?.status || crawl.status, crawl.data?.error_code)
  } catch (e) {
    console.log('crawl error', e)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
