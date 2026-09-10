import json
from typing import List, Dict, Any
from src.tools.procurement_tools import (
    check_inventory,
    list_low_stock_items,
    get_supplier_info,
    create_purchase_order,
    ToolResult
)

PROCUREMENT_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "Check current stock level, category, and unit cost for an inventory item by SKU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU code of the item, e.g. SKU-1001"}
                },
                "required": ["sku"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_low_stock_items",
            "description": "List inventory items that have stock levels at or below their reorder threshold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Optional category filter (e.g. IT Hardware, Office Supplies)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_info",
            "description": "Get supplier details, rating, contact info, and preferred status by supplier ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "supplier_id": {"type": "string", "description": "The supplier ID, e.g. SUP-101"}
                },
                "required": ["supplier_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_order",
            "description": "Create a purchase order for a specified SKU, quantity, supplier, and unit price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "The SKU code of the item"},
                    "qty": {"type": "integer", "description": "Quantity to order"},
                    "supplier_id": {"type": "string", "description": "The supplier ID, e.g. SUP-101"},
                    "unit_price": {"type": "number", "description": "Unit price in USD"}
                },
                "required": ["sku", "qty", "supplier_id", "unit_price"]
            }
        }
    }
]

def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any], user_role: str = "procurement_agent") -> ToolResult:
    """Dispatches tool execution to deterministic Python functions."""
    if tool_name == "check_inventory":
        return check_inventory(sku=arguments.get("sku", ""))
    elif tool_name == "list_low_stock_items":
        return list_low_stock_items(category=arguments.get("category"))
    elif tool_name == "get_supplier_info":
        return get_supplier_info(supplier_id=arguments.get("supplier_id", ""))
    elif tool_name == "create_purchase_order":
        return create_purchase_order(
            sku=arguments.get("sku", ""),
            qty=int(arguments.get("qty", 1)),
            supplier_id=arguments.get("supplier_id", ""),
            unit_price=float(arguments.get("unit_price", 0.0)),
            user_role=user_role
        )
    else:
        return ToolResult(
            tool_name=tool_name,
            success=False,
            error=f"Unknown tool name: '{tool_name}'"
        )
