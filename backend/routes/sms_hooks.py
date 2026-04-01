"""
SMS trigger hooks — called from invoice creation, payment receipt, etc.
Each function is fire-and-forget (errors logged, never blocks the caller).
Uses _raw_db (unscoped) for lookups to bypass tenant ContextVar mutations.
organization_id is resolved explicitly and passed to queue_sms for proper isolation.
"""
from config import _raw_db as raw_db, logger


async def _resolve_org_id(branch_id: str) -> str:
    """Resolve organization_id from a branch_id. Returns empty string if not found."""
    if not branch_id:
        return ""
    branch = await raw_db.branches.find_one({"id": branch_id}, {"_id": 0, "organization_id": 1})
    return (branch or {}).get("organization_id", "") if branch else ""


async def get_company_name(organization_id: str = "") -> str:
    """Get the business name for the given org (or fallback to AgriBooks)."""
    query = {"key": "business_info"}
    if organization_id:
        query["organization_id"] = organization_id
    biz = await raw_db.settings.find_one(query, {"_id": 0})
    return biz.get("value", {}).get("business_name", "AgriBooks") if biz else "AgriBooks"


async def get_branch_name(branch_id: str) -> str:
    if not branch_id:
        return ""
    branch = await raw_db.branches.find_one({"id": branch_id}, {"_id": 0, "name": 1})
    return branch.get("name", "") if branch else ""


async def on_credit_sale_created(invoice: dict):
    """Called after a credit sale invoice is created with balance > 0."""
    try:
        from routes.sms import queue_sms
        customer_id = invoice.get("customer_id", "")
        if not customer_id:
            return
        customer = await raw_db.customers.find_one({"id": customer_id}, {"_id": 0})
        if not customer:
            return
        phone = customer.get("phone") or invoice.get("customer_phone", "")
        if not phone:
            return

        branch_id = invoice.get("branch_id", "")
        org_id = await _resolve_org_id(branch_id)
        company_name = await get_company_name(org_id)
        branch_name = await get_branch_name(branch_id)

        await queue_sms(
            template_key="credit_new",
            customer_id=customer_id,
            customer_name=customer.get("name", invoice.get("customer_name", "")),
            phone=phone,
            variables={
                "customer_name": customer.get("name", invoice.get("customer_name", "")),
                "amount": f"{invoice.get('grand_total', 0):,.2f}",
                "company_name": company_name,
                "branch_name": branch_name,
                "date": invoice.get("order_date", ""),
                "due_date": invoice.get("due_date", ""),
                "total_balance": f"{customer.get('balance', 0):,.2f}",
            },
            organization_id=org_id,
            branch_id=branch_id,
            branch_name=branch_name,
            trigger="auto",
            trigger_ref=invoice.get("id", ""),
            dedup_key=f"credit_new:{invoice.get('id', '')}",
        )
    except Exception as e:
        logger.error(f"SMS hook on_credit_sale_created failed: {e}")


async def on_payment_received(customer_id: str, amount_paid: float, remaining_balance: float,
                               branch_id: str = "", next_due_info: str = ""):
    """Called after a customer payment is applied."""
    try:
        from routes.sms import queue_sms
        customer = await raw_db.customers.find_one({"id": customer_id}, {"_id": 0})
        if not customer:
            return
        phone = customer.get("phone", "")
        if not phone:
            return

        org_id = await _resolve_org_id(branch_id)
        company_name = await get_company_name(org_id)

        await queue_sms(
            template_key="payment_received",
            customer_id=customer_id,
            customer_name=customer.get("name", ""),
            phone=phone,
            variables={
                "customer_name": customer.get("name", ""),
                "amount_paid": f"{amount_paid:,.2f}",
                "remaining_balance": f"{remaining_balance:,.2f}",
                "next_due_info": next_due_info,
                "company_name": company_name,
            },
            organization_id=org_id,
            branch_id=branch_id,
            branch_name=await get_branch_name(branch_id),
            trigger="auto",
            trigger_ref=f"payment:{customer_id}:{amount_paid}",
        )
    except Exception as e:
        logger.error(f"SMS hook on_payment_received failed: {e}")


async def on_charge_applied(customer_id: str, charge_type: str, charge_amount: float,
                             total_balance: float, branch_id: str = ""):
    """Called after interest or penalty is generated."""
    try:
        from routes.sms import queue_sms
        customer = await raw_db.customers.find_one({"id": customer_id}, {"_id": 0})
        if not customer:
            return
        phone = customer.get("phone", "")
        if not phone:
            return

        org_id = await _resolve_org_id(branch_id)
        company_name = await get_company_name(org_id)

        await queue_sms(
            template_key="charge_applied",
            customer_id=customer_id,
            customer_name=customer.get("name", ""),
            phone=phone,
            variables={
                "charge_type": charge_type,
                "charge_amount": f"{charge_amount:,.2f}",
                "customer_name": customer.get("name", ""),
                "total_balance": f"{total_balance:,.2f}",
                "company_name": company_name,
            },
            organization_id=org_id,
            branch_id=branch_id,
            branch_name=await get_branch_name(branch_id),
            trigger="auto",
            trigger_ref=f"charge:{customer_id}:{charge_type}",
        )
    except Exception as e:
        logger.error(f"SMS hook on_charge_applied failed: {e}")
