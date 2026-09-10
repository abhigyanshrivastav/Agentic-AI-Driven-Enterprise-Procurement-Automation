# Enterprise Procurement & Expenditure Policy 2026

## 1. Delegated Financial Authority Thresholds
- **Procurement Agent (Level 1)**: Authorized for individual purchase orders up to **$5,000.00 USD**.
- **Procurement Manager (Level 2)**: Authorized for purchase orders up to **$50,000.00 USD**.
- **Executive / Admin (Level 3)**: Authorized for unlimited expenditure subject to board oversight.

## 2. Spend Restriction & Human Escalation Rules
- Any purchase request exceeding **$5,000.00 USD** submitted by a Level 1 Procurement Agent MUST be flagged and escalated to a Procurement Manager for manual sign-off.
- Orders attempting to bypass authorization will be blocked by system guardrails.
- Purchases of restricted categories (e.g., Hazardous Materials, Unapproved Software Licenses) require mandatory compliance audit prior to PO creation.

## 3. Supplier Selection & Preferred Vendors
- All purchase orders must prioritize Preferred Vendors (Status = 'PREFERRED').
- Purchases from non-preferred vendors exceeding $1,000.00 USD require justification in the order notes.
- Orders placed with Restricted or Suspended vendors will be automatically rejected.

## 4. Reorder & Inventory Management Guidelines
- Stock items falling below their specified `reorder_threshold` should trigger an automated reorder recommendation.
- Standard reorder quantity must not exceed 2x the current shortage amount unless authorized by a Manager.
