from typing import Dict, Any, Optional
from pydantic import BaseModel
from src.tools.procurement_tools import get_supplier_info

class AuthorizationDecision(BaseModel):
    authorized: bool
    requires_human_escalation: bool
    reason: str

class DeterministicAuthorizer:
    """Evaluates financial and policy compliance rules in deterministic Python code."""

    def __init__(self, po_threshold_usd: float = 5000.0):
        self.po_threshold_usd = po_threshold_usd

    def authorize_purchase_order(
        self,
        sku: str,
        qty: int,
        unit_price: float,
        supplier_id: str,
        user_role: str = "procurement_agent"
    ) -> AuthorizationDecision:
        total_cost = round(qty * unit_price, 2)
        
        # 1. Vendor Status Check
        supplier_res = get_supplier_info(supplier_id)
        if supplier_res.success:
            status = supplier_res.data.get("preferred_status", "APPROVED")
            if status == "RESTRICTED":
                return AuthorizationDecision(
                    authorized=False,
                    requires_human_escalation=True,
                    reason=f"Policy Block: Supplier '{supplier_id}' is RESTRICTED and requires IT Security / Compliance approval."
                )

        # 2. Financial Delegation Limit Check
        if total_cost > self.po_threshold_usd and user_role not in ["manager", "admin"]:
            return AuthorizationDecision(
                authorized=False,
                requires_human_escalation=True,
                reason=(
                    f"Financial Spend Threshold Exceeded: PO total ${total_cost:.2f} USD exceeds the authorized threshold "
                    f"of ${self.po_threshold_usd:.2f} USD for user role '{user_role}'. Human escalation required."
                )
            )

        return AuthorizationDecision(
            authorized=True,
            requires_human_escalation=False,
            reason="Within authorized policy threshold and vendor guidelines."
        )
