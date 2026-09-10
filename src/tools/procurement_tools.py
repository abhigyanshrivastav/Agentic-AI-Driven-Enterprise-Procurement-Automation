import uuid
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from src.tools.db import execute_query, execute_statement
from src.observability import logger

class ToolResult(BaseModel):
    tool_name: str
    success: bool
    data: Dict[str, Any] = {}
    message: str = ""
    error: Optional[str] = None

def check_inventory(sku: str) -> ToolResult:
    """Checks stock quantity, category, and unit cost for a given SKU."""
    rows = execute_query("SELECT * FROM inventory WHERE sku = ?", (sku.upper(),))
    if not rows:
        return ToolResult(
            tool_name="check_inventory",
            success=False,
            error=f"SKU '{sku}' not found in inventory database."
        )
    item = rows[0]
    return ToolResult(
        tool_name="check_inventory",
        success=True,
        data=item,
        message=f"Stock for {sku} ({item['item_name']}): {item['stock_qty']} units at ${item['unit_cost_usd']}/unit."
    )

def list_low_stock_items(category: Optional[str] = None) -> ToolResult:
    """Finds inventory items where stock_qty is below the reorder_threshold."""
    if category:
        sql = "SELECT * FROM inventory WHERE stock_qty <= reorder_threshold AND category = ?"
        rows = execute_query(sql, (category,))
    else:
        sql = "SELECT * FROM inventory WHERE stock_qty <= reorder_threshold"
        rows = execute_query(sql)
        
    return ToolResult(
        tool_name="list_low_stock_items",
        success=True,
        data={"count": len(rows), "items": rows},
        message=f"Found {len(rows)} low stock items below threshold."
    )

def get_supplier_info(supplier_id: str) -> ToolResult:
    """Fetches details, rating, and preferred status for a supplier."""
    rows = execute_query("SELECT * FROM suppliers WHERE supplier_id = ?", (supplier_id.upper(),))
    if not rows:
        return ToolResult(
            tool_name="get_supplier_info",
            success=False,
            error=f"Supplier '{supplier_id}' not found."
        )
    supplier = rows[0]
    return ToolResult(
        tool_name="get_supplier_info",
        success=True,
        data=supplier,
        message=f"Supplier {supplier['name']} ({supplier_id}): Status {supplier['preferred_status']}, Rating {supplier['rating']}."
    )

def create_purchase_order(
    sku: str,
    qty: int,
    supplier_id: str,
    unit_price: float,
    created_by: str = "agent",
    user_role: str = "procurement_agent"
) -> ToolResult:
    """Creates a simulated purchase order record in SQLite."""
    sku_upper = sku.upper()
    supplier_upper = supplier_id.upper()
    
    # Validate supplier preferred status
    supplier_res = get_supplier_info(supplier_upper)
    if not supplier_res.success:
        return ToolResult(tool_name="create_purchase_order", success=False, error=supplier_res.error)
    
    supplier = supplier_res.data
    if supplier.get("preferred_status") == "RESTRICTED":
        return ToolResult(
            tool_name="create_purchase_order",
            success=False,
            error=f"PO Creation Blocked: Supplier '{supplier_upper}' status is RESTRICTED."
        )

    po_id = f"PO-{uuid.uuid4().hex[:6].upper()}"
    total_cost = round(qty * unit_price, 2)
    requires_approval = 1 if total_cost > 5000.0 else 0
    status = "PENDING_APPROVAL" if requires_approval else "APPROVED"

    sql = """
    INSERT INTO purchase_orders (po_id, sku, qty, unit_price_usd, total_amount_usd, supplier_id, status, created_by, requires_approval)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    affected = execute_statement(sql, (po_id, sku_upper, qty, unit_price, total_cost, supplier_upper, status, created_by, requires_approval))
    
    if affected > 0:
        return ToolResult(
            tool_name="create_purchase_order",
            success=True,
            data={
                "po_id": po_id,
                "sku": sku_upper,
                "qty": qty,
                "total_amount_usd": total_cost,
                "supplier_id": supplier_upper,
                "status": status,
                "requires_approval": bool(requires_approval)
            },
            message=f"Purchase Order {po_id} created successfully for ${total_cost} USD (Status: {status})."
        )
    return ToolResult(tool_name="create_purchase_order", success=False, error="Failed to insert PO record.")
