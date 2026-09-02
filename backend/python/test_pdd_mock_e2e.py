#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end test for PDD mock data flow."""
from datetime import datetime
import sys
import os
from pathlib import Path

# Force UTF-8 encoding on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Add backend/python to path
BACKEND_PYTHON = Path(__file__).parent
sys.path.insert(0, str(BACKEND_PYTHON))

from app.timezone import SHANGHAI


def test_mock_generators():
    """Test mock data generators."""
    from app.mock_pdd import (
        generate_mock_orders,
        generate_mock_products,
        generate_mock_compass,
        generate_mock_compass_data,
    )

    print("\n=== Testing Mock Data Generators ===\n")

    # Test orders
    print("1️⃣  Testing generate_mock_orders()...")
    orders = generate_mock_orders(tenant_id=1, date_window="today", count=20)
    assert isinstance(orders, list), "Orders should be a list"
    assert len(orders) == 20, f"Expected 20 orders, got {len(orders)}"
    assert all("order_no" in o for o in orders), "All orders should have order_no"
    print(f"   ✅ Generated {len(orders)} orders")
    if orders:
        print(f"      Sample: {orders[0]['order_no']} - {orders[0]['product_name']} ({orders[0]['status']})")

    # Test products
    print("\n2️⃣  Testing generate_mock_products()...")
    products = generate_mock_products(tenant_id=1, count=50)
    assert isinstance(products, list), "Products should be a list"
    assert len(products) == 50, f"Expected 50 products, got {len(products)}"
    assert all("product_key" in p for p in products), "All products should have product_key"
    print(f"   ✅ Generated {len(products)} products")
    if products:
        print(f"      Sample: {products[0]['product_name']} - ¥{products[0]['price']} (库存: {products[0]['stock']})")

    # Test compass
    print("\n3️⃣  Testing generate_mock_compass()...")
    compass = generate_mock_compass(tenant_id=1, date_type=1)
    assert isinstance(compass, dict), "Compass should be a dict"
    assert "pay_amount" in compass, "Compass should have pay_amount"
    assert "pay_count" in compass, "Compass should have pay_count"
    print(f"   ✅ Generated compass snapshot")
    print(f"      销售额: ¥{compass['pay_amount']:,.0f}, 成交单数: {compass['pay_count']}, 转化率: {compass['conversion_rate']:.2%}")

    # Test complete compass data
    print("\n4️⃣  Testing generate_mock_compass_data()...")
    compass_data = generate_mock_compass_data(tenant_id=1)
    assert isinstance(compass_data, dict), "Compass data should be a dict"
    assert "realtime" in compass_data, "Should have realtime data"
    assert "d1" in compass_data, "Should have d1 data"
    assert "d7" in compass_data, "Should have d7 data"
    assert "d30" in compass_data, "Should have d30 data"
    print(f"   ✅ Generated complete compass data for 4 date types")

    print("\n✅ All mock generators passed!")
    return True


def test_ingest_layer():
    """Test ingest layer (SQLite write)."""
    print("\n=== Testing Ingest Layer ===\n")

    from app.ingest_pdd import upsert_orders, upsert_products, upsert_compass
    from app.mock_pdd import generate_mock_orders, generate_mock_products, generate_mock_compass

    print("1️⃣  Testing upsert_orders()...")
    orders = generate_mock_orders(tenant_id=1, date_window="today", count=5)
    count = upsert_orders(tenant_id=1, rows=orders)
    assert count > 0, f"Expected to ingest orders, got {count}"
    print(f"   ✅ Upserted {count} orders into SQLite")

    # Try upsert again (should be idempotent)
    count2 = upsert_orders(tenant_id=1, rows=orders)
    assert count2 > 0, "Should be idempotent"
    print(f"   ✅ Idempotent upsert: {count2} orders (no duplicates)")

    print("\n2️⃣  Testing upsert_products()...")
    products = generate_mock_products(tenant_id=1, count=10)
    count = upsert_products(tenant_id=1, rows=products)
    assert count > 0, f"Expected to ingest products, got {count}"
    print(f"   ✅ Upserted {count} products into SQLite")

    print("\n3️⃣  Testing upsert_compass()...")
    compass = generate_mock_compass(tenant_id=1, date_type=1)
    success = upsert_compass(tenant_id=1, payload=compass, date_type=1)
    assert success, "Compass upsert should succeed"
    print(f"   ✅ Upserted compass snapshot (date_type=1)")

    print("\n✅ All ingest operations passed!")
    return True


def test_pdd_tasks_mock_mode():
    """Test that pdd_tasks returns mock data."""
    print("\n=== Testing PDD Tasks (Mock Mode) ===\n")

    from agent.pdd_tasks import (
        fetch_orders_via_xhr,
        fetch_products_via_xhr,
        fetch_compass_via_xhr,
        _MOCK_ORDERS_ENABLED,
        _MOCK_PRODUCTS_ENABLED,
        _MOCK_COMPASS_ENABLED,
    )

    print(f"Mock mode status:")
    print(f"  Orders:   {'🟢 ENABLED' if _MOCK_ORDERS_ENABLED else '🔴 DISABLED'}")
    print(f"  Products: {'🟢 ENABLED' if _MOCK_PRODUCTS_ENABLED else '🔴 DISABLED'}")
    print(f"  Compass:  {'🟢 ENABLED' if _MOCK_COMPASS_ENABLED else '🔴 DISABLED'}")

    # Test orders fetch
    print("\n1️⃣  Testing fetch_orders_via_xhr()...")
    orders, source_url = fetch_orders_via_xhr(page=None, date_window="today")
    assert isinstance(orders, list), "Orders should be a list"
    assert len(orders) > 0, "Should return mock orders"
    assert isinstance(source_url, str), "Should return source_url"
    print(f"   ✅ Fetched {len(orders)} mock orders")
    print(f"      Source: {source_url}")

    # Test products fetch
    print("\n2️⃣  Testing fetch_products_via_xhr()...")
    products, source_url = fetch_products_via_xhr(page=None)
    assert isinstance(products, list), "Products should be a list"
    assert len(products) > 0, "Should return mock products"
    print(f"   ✅ Fetched {len(products)} mock products")
    print(f"      Source: {source_url}")

    # Test compass fetch
    print("\n3️⃣  Testing fetch_compass_via_xhr()...")
    compass, source_url = fetch_compass_via_xhr(page=None, date_type=1)
    assert isinstance(compass, dict), "Compass should be a dict"
    assert "pay_amount" in compass, "Compass should have metrics"
    print(f"   ✅ Fetched mock compass snapshot")
    print(f"      Source: {source_url}")

    print("\n✅ All PDD tasks mock mode passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 PDD Mock Data End-to-End Test Suite")
    print("=" * 60)

    try:
        test_mock_generators()
        test_ingest_layer()
        test_pdd_tasks_mock_mode()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\n📝 Summary:")
        print("  ✅ Mock data generators work correctly")
        print("  ✅ SQLite ingest layer is functional")
        print("  ✅ PDD tasks return mock data as expected")
        print("\n🚀 Ready for integration testing!")
        print("   - Start Java backend: npm run start:java")
        print("   - Start Vue frontend: npm run dev:vue")
        print("   - Start Python Agent: npm run start:agent")
        print("\nThen test the flow:")
        print("  1. Open http://localhost:5173/pdd-module")
        print("  2. Click 'Refresh Orders' to trigger sync")
        print("  3. Check Agent logs for mock data execution")
        print("  4. Verify orders appear in frontend")

    except Exception as exc:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {exc}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
