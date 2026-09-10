import pytest
from src.tools.procurement_tools import (
    check_inventory,
    list_low_stock_items,
    get_supplier_info,
    create_purchase_order
)

def test_check_inventory():
    res = check_inventory("SKU-1001")
    assert res.success is True
    assert res.data["sku"] == "SKU-1001"
    assert "stock_qty" in res.data

def test_get_supplier_info():
    res = get_supplier_info("SUP-101")
    assert res.success is True
    assert res.data["name"] == "Zenith Electronics"
    assert res.data["preferred_status"] == "PREFERRED"

def test_create_purchase_order_restricted_supplier():
    res = create_purchase_order(
        sku="SKU-1005",
        qty=5,
        supplier_id="SUP-105",  # RESTRICTED status vendor
        unit_price=100.0,
        user_role="procurement_agent"
    )
    assert res.success is False
    assert "RESTRICTED" in res.error
