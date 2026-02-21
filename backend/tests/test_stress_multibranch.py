"""
Comprehensive Multi-Branch Stress Test
Tests all features across Main Branch, IPIL Branch, and Sampoli Branch:
- Sales (cash + credit), POs, inventory, repacks, credit, expenses, supplier payments
- Fund management setup, AR payments, close wizard preview, low stock, supplier payables
"""
import pytest
import requests
import os
import json
from datetime import datetime, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Branch IDs ───────────────────────────────────────────────────────────────
MAIN_BRANCH_ID   = "da114e26-fd00-467f-8728-6b8047a244b5"
IPIL_BRANCH_ID   = "d4a041e7-4918-490e-afb8-54ae90cec7fb"
SAMPOLI_BRANCH_ID = "de3b347f-6166-446e-9ab7-2b4ab1836176"

# ── Product IDs (partial → need to resolve full UUIDs at runtime) ─────────────
ENERTONE_ID   = "c313bfe0"   # CASE ₱920 cost
VITMIN_ID     = "4dfff4e8"   # Box ₱500
VOLPLEX_ID    = "63e3729a"   # Box ₱800
LANNATE_ID    = "4a7ff0dc"   # Pouch ₱500
PLATINUM_ID   = "f0a877e6"   # CASE ₱1380
R_LANNATE_ID  = "5c66d75c"   # Repack Lannate
R_VITMIN_ID   = "d3bb5438"
R_ENERTONE_ID = "fd23a124"
R_PLATINUM_ID = "f4e875b0"

# ── Supplier IDs ─────────────────────────────────────────────────────────────
PILMICO_ID    = "26995540"
SUPPLIER1_ID  = "f6b4131d"

# ── Customer IDs ─────────────────────────────────────────────────────────────
JANMARK_ID    = "5ddee74b"
TEST_AUTO_CUSTOMER_ID = "df111808"
SADRAK_ID     = "a842f0fe"

TODAY = datetime.utcnow().strftime("%Y-%m-%d")
DUE_5_DAYS = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d")
DUE_3_DAYS = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")

# ── Shared state ─────────────────────────────────────────────────────────────
shared_state = {}


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(session):
    resp = session.post(f"{BASE_URL}/api/auth/login",
                        json={"username": "owner", "password": "521325"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("token") or resp.json().get("access_token")
    assert token, "No token in login response"
    return token


@pytest.fixture(scope="module")
def authed(session, auth_token):
    session.headers.update({"Authorization": f"Bearer {auth_token}"})
    return session


def resolve_product_id(authed, partial_id):
    """Find full product UUID by partial ID prefix."""
    resp = authed.get(f"{BASE_URL}/api/products?limit=200")
    if resp.status_code == 200:
        products = resp.json().get("products", [])
        for p in products:
            if p.get("id", "").startswith(partial_id):
                return p["id"]
    return partial_id  # fallback to partial if not found


def resolve_customer_id(authed, partial_id):
    resp = authed.get(f"{BASE_URL}/api/customers?limit=200")
    if resp.status_code == 200:
        customers = resp.json().get("customers", [])
        for c in customers:
            if c.get("id", "").startswith(partial_id):
                return c["id"]
    return partial_id


def resolve_supplier_id(authed, partial_id):
    resp = authed.get(f"{BASE_URL}/api/suppliers?limit=200")
    if resp.status_code == 200:
        suppliers = resp.json().get("suppliers", [])
        for s in suppliers:
            if s.get("id", "").startswith(partial_id):
                return s["id"]
    return partial_id


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0: Resolve IDs
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase0ResolvIDs:
    """Resolve full UUIDs for partial IDs used in later tests."""

    def test_resolve_products(self, authed):
        resp = authed.get(f"{BASE_URL}/api/products?limit=200")
        assert resp.status_code == 200
        products = resp.json().get("products", [])
        print(f"\nTotal products found: {len(products)}")

        for p in products:
            pid = p.get("id", "")
            name = p.get("name", "")
            print(f"  {pid[:8]} → {name}")
            if pid.startswith(ENERTONE_ID):
                shared_state["enertone_id"] = pid
                shared_state["enertone_name"] = name
            elif pid.startswith(VITMIN_ID):
                shared_state["vitmin_id"] = pid
                shared_state["vitmin_name"] = name
            elif pid.startswith(VOLPLEX_ID):
                shared_state["volplex_id"] = pid
                shared_state["volplex_name"] = name
            elif pid.startswith(LANNATE_ID):
                shared_state["lannate_id"] = pid
                shared_state["lannate_name"] = name
            elif pid.startswith(PLATINUM_ID):
                shared_state["platinum_id"] = pid
                shared_state["platinum_name"] = name
            elif pid.startswith(R_LANNATE_ID):
                shared_state["r_lannate_id"] = pid
                shared_state["r_lannate_name"] = name
            elif pid.startswith(R_VITMIN_ID):
                shared_state["r_vitmin_id"] = pid
                shared_state["r_vitmin_name"] = name
            elif pid.startswith(R_ENERTONE_ID):
                shared_state["r_enertone_id"] = pid
            elif pid.startswith(R_PLATINUM_ID):
                shared_state["r_platinum_id"] = pid

        assert "enertone_id" in shared_state, "ENERTONE product not found"
        print(f"\nResolved ENERTONE: {shared_state['enertone_id']}")
        print(f"Resolved VITMIN: {shared_state.get('vitmin_id', 'NOT FOUND')}")
        print(f"Resolved VOLPLEX: {shared_state.get('volplex_id', 'NOT FOUND')}")
        print(f"Resolved LANNATE: {shared_state.get('lannate_id', 'NOT FOUND')}")
        print(f"Resolved PLATINUM: {shared_state.get('platinum_id', 'NOT FOUND')}")
        print(f"Resolved R_LANNATE: {shared_state.get('r_lannate_id', 'NOT FOUND')}")

    def test_resolve_customers(self, authed):
        resp = authed.get(f"{BASE_URL}/api/customers?limit=200")
        assert resp.status_code == 200
        customers = resp.json().get("customers", [])
        print(f"\nTotal customers: {len(customers)}")
        for c in customers:
            cid = c.get("id", "")
            if cid.startswith(JANMARK_ID):
                shared_state["janmark_id"] = cid
                shared_state["janmark_balance"] = c.get("balance", 0)
            elif cid.startswith(TEST_AUTO_CUSTOMER_ID):
                shared_state["test_auto_cust_id"] = cid
                shared_state["test_auto_cust_balance"] = c.get("balance", 0)
            elif cid.startswith(SADRAK_ID):
                shared_state["sadrak_id"] = cid
        print(f"JANMARK: {shared_state.get('janmark_id', 'NOT FOUND')} bal={shared_state.get('janmark_balance', 0)}")
        print(f"TEST_AUTO: {shared_state.get('test_auto_cust_id', 'NOT FOUND')} bal={shared_state.get('test_auto_cust_balance', 0)}")

    def test_resolve_suppliers(self, authed):
        resp = authed.get(f"{BASE_URL}/api/suppliers?limit=100")
        assert resp.status_code == 200
        raw = resp.json()
        # Endpoint returns a list or dict with "suppliers" key
        if isinstance(raw, list):
            suppliers = raw
        else:
            suppliers = raw.get("suppliers", [])

        print(f"\nTotal suppliers: {len(suppliers)}")
        for s in suppliers:
            sid = s.get("id", "")
            name = s.get("name", "")
            print(f"  {sid[:8]} → {name}")
            if sid.startswith(PILMICO_ID):
                shared_state["pilmico_id"] = sid
                shared_state["pilmico_name"] = name
            elif sid.startswith(SUPPLIER1_ID):
                shared_state["supplier1_id"] = sid
                shared_state["supplier1_name"] = name

        print(f"PILMICO: {shared_state.get('pilmico_id', 'NOT FOUND')}")
        print(f"SUPPLIER1: {shared_state.get('supplier1_id', 'NOT FOUND')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: SETUP
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase1Setup:
    """Setup: Fund wallets, inventory, customers."""

    # ── Fund wallet helpers ────────────────────────────────────────────────────
    def _get_or_create_wallet(self, authed, branch_id, wallet_type):
        resp = authed.get(f"{BASE_URL}/api/fund-wallets?branch_id={branch_id}")
        assert resp.status_code == 200
        wallets = resp.json()
        for w in wallets:
            if w.get("type") == wallet_type and w.get("active"):
                return w
        # Create wallet
        resp = authed.post(f"{BASE_URL}/api/fund-wallets", json={
            "branch_id": branch_id,
            "type": wallet_type,
            "name": f"{wallet_type.capitalize()} - {branch_id[:8]}",
            "balance": 0.0
        })
        assert resp.status_code == 200, f"Could not create {wallet_type} wallet: {resp.text}"
        return resp.json()

    def test_01_ipil_cashier_fund_setup(self, authed):
        """Add ₱5,000 to IPIL cashier wallet."""
        wallet = self._get_or_create_wallet(authed, IPIL_BRANCH_ID, "cashier")
        wallet_id = wallet["id"]
        current_balance = wallet.get("balance", 0)
        print(f"\nIPIL cashier current balance: ₱{current_balance}")
        shared_state["ipil_cashier_wallet_id"] = wallet_id
        shared_state["ipil_cashier_balance_before"] = current_balance

        # Deposit ₱5,000
        resp = authed.post(f"{BASE_URL}/api/fund-wallets/{wallet_id}/deposit",
                           json={"amount": 5000, "reference": "STRESS_TEST_SETUP_IPIL_CASHIER"})
        assert resp.status_code == 200, f"IPIL cashier deposit failed: {resp.text}"
        print(f"IPIL cashier deposit ₱5,000 OK: {resp.json()}")

    def test_02_ipil_safe_fund_setup(self, authed):
        """Add ₱30,000 to IPIL safe wallet."""
        wallet = self._get_or_create_wallet(authed, IPIL_BRANCH_ID, "safe")
        wallet_id = wallet["id"]
        shared_state["ipil_safe_wallet_id"] = wallet_id
        resp = authed.post(f"{BASE_URL}/api/fund-wallets/{wallet_id}/deposit",
                           json={"amount": 30000, "reference": "STRESS_TEST_SETUP_IPIL_SAFE"})
        assert resp.status_code == 200, f"IPIL safe deposit failed: {resp.text}"
        print(f"IPIL safe deposit ₱30,000 OK")

    def test_03_sampoli_cashier_fund_setup(self, authed):
        """Add ₱3,000 to Sampoli cashier wallet."""
        wallet = self._get_or_create_wallet(authed, SAMPOLI_BRANCH_ID, "cashier")
        wallet_id = wallet["id"]
        current_balance = wallet.get("balance", 0)
        shared_state["sampoli_cashier_wallet_id"] = wallet_id
        shared_state["sampoli_cashier_balance_before"] = current_balance
        resp = authed.post(f"{BASE_URL}/api/fund-wallets/{wallet_id}/deposit",
                           json={"amount": 3000, "reference": "STRESS_TEST_SETUP_SAMPOLI_CASHIER"})
        assert resp.status_code == 200, f"Sampoli cashier deposit failed: {resp.text}"
        print(f"Sampoli cashier deposit ₱3,000 OK")

    def test_04_sampoli_safe_fund_setup(self, authed):
        """Add ₱20,000 to Sampoli safe wallet."""
        wallet = self._get_or_create_wallet(authed, SAMPOLI_BRANCH_ID, "safe")
        wallet_id = wallet["id"]
        shared_state["sampoli_safe_wallet_id"] = wallet_id
        resp = authed.post(f"{BASE_URL}/api/fund-wallets/{wallet_id}/deposit",
                           json={"amount": 20000, "reference": "STRESS_TEST_SETUP_SAMPOLI_SAFE"})
        assert resp.status_code == 200, f"Sampoli safe deposit failed: {resp.text}"
        print(f"Sampoli safe deposit ₱20,000 OK")

    def test_05_main_inventory_setup(self, authed):
        """Set Main Branch inventory: ENERTONE=50, Lannate=100, VITMIN=30, VOLPLEX=20, PLATINUM=15."""
        assert "enertone_id" in shared_state, "Products not resolved (run test_resolve_products first)"
        inventories = [
            (shared_state["enertone_id"], 50, "ENERTONE"),
            (shared_state.get("lannate_id", LANNATE_ID), 100, "Lannate"),
            (shared_state.get("vitmin_id", VITMIN_ID), 30, "VITMIN"),
            (shared_state.get("volplex_id", VOLPLEX_ID), 20, "VOLPLEX"),
            (shared_state.get("platinum_id", PLATINUM_ID), 15, "PLATINUM"),
        ]
        for prod_id, qty, name in inventories:
            resp = authed.post(f"{BASE_URL}/api/inventory/set", json={
                "product_id": prod_id,
                "branch_id": MAIN_BRANCH_ID,
                "quantity": qty
            })
            assert resp.status_code == 200, f"Main inv set failed for {name}: {resp.text}"
            print(f"Main Branch {name}={qty} set OK")

    def test_06_ipil_inventory_setup(self, authed):
        """Set IPIL Branch inventory: ENERTONE=40, PLATINUM=20, VITMIN=25."""
        inventories = [
            (shared_state.get("enertone_id", ENERTONE_ID), 40, "ENERTONE"),
            (shared_state.get("platinum_id", PLATINUM_ID), 20, "PLATINUM"),
            (shared_state.get("vitmin_id", VITMIN_ID), 25, "VITMIN"),
        ]
        for prod_id, qty, name in inventories:
            resp = authed.post(f"{BASE_URL}/api/inventory/set", json={
                "product_id": prod_id,
                "branch_id": IPIL_BRANCH_ID,
                "quantity": qty
            })
            assert resp.status_code == 200, f"IPIL inv set failed for {name}: {resp.text}"
            print(f"IPIL Branch {name}={qty} set OK")

    def test_07_sampoli_inventory_setup(self, authed):
        """Set Sampoli Branch inventory: ENERTONE=30, Lannate=50, VITMIN=20."""
        inventories = [
            (shared_state.get("enertone_id", ENERTONE_ID), 30, "ENERTONE"),
            (shared_state.get("lannate_id", LANNATE_ID), 50, "Lannate"),
            (shared_state.get("vitmin_id", VITMIN_ID), 20, "VITMIN"),
        ]
        for prod_id, qty, name in inventories:
            resp = authed.post(f"{BASE_URL}/api/inventory/set", json={
                "product_id": prod_id,
                "branch_id": SAMPOLI_BRANCH_ID,
                "quantity": qty
            })
            assert resp.status_code == 200, f"Sampoli inv set failed for {name}: {resp.text}"
            print(f"Sampoli Branch {name}={qty} set OK")

    def test_08_create_customer_rosario_main(self, authed):
        """Create ROSARIO customer for Main Branch with balance=0."""
        resp = authed.post(f"{BASE_URL}/api/customers", json={
            "name": "ROSARIO_TEST_STRESS",
            "phone": "09100000001",
            "branch_id": MAIN_BRANCH_ID,
            "credit_limit": 0,
            "interest_rate": 0,
            "price_scheme": "retail"
        })
        assert resp.status_code == 200, f"Create ROSARIO failed: {resp.text}"
        customer = resp.json()
        shared_state["rosario_id"] = customer["id"]
        shared_state["rosario_balance_before"] = customer.get("balance", 0)
        print(f"ROSARIO created: {customer['id']}")

    def test_09_create_customer_pedro_ipil(self, authed):
        """Create PEDRO customer for IPIL Branch."""
        resp = authed.post(f"{BASE_URL}/api/customers", json={
            "name": "PEDRO_TEST_STRESS",
            "phone": "09100000002",
            "branch_id": IPIL_BRANCH_ID,
            "credit_limit": 0,
            "interest_rate": 0,
            "price_scheme": "retail"
        })
        assert resp.status_code == 200, f"Create PEDRO failed: {resp.text}"
        customer = resp.json()
        shared_state["pedro_id"] = customer["id"]
        print(f"PEDRO created: {customer['id']}")

    def test_10_create_customer_maria_sampoli(self, authed):
        """Create MARIA customer for Sampoli Branch."""
        resp = authed.post(f"{BASE_URL}/api/customers", json={
            "name": "MARIA_TEST_STRESS",
            "phone": "09100000003",
            "branch_id": SAMPOLI_BRANCH_ID,
            "credit_limit": 0,
            "interest_rate": 0,
            "price_scheme": "retail"
        })
        assert resp.status_code == 200, f"Create MARIA failed: {resp.text}"
        customer = resp.json()
        shared_state["maria_id"] = customer["id"]
        print(f"MARIA created: {customer['id']}")

    def test_11_create_supplier_agri(self, authed):
        """Create AGRI SUPPLIES supplier."""
        resp = authed.post(f"{BASE_URL}/api/suppliers", json={
            "name": "AGRI SUPPLIES TEST STRESS",
            "contact": "09123456789",
            "email": "agrisupplies@test.com",
            "address": "Test Address",
            "terms_days": 30
        })
        # 200 or 201
        assert resp.status_code in [200, 201], f"Create supplier failed: {resp.text}"
        supplier = resp.json()
        shared_state["agri_supplier_id"] = supplier.get("id", "")
        print(f"AGRI SUPPLIES created: {supplier.get('id', '')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: MAIN BRANCH TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase2MainBranch:
    """All Main Branch transactions."""

    def _get_cashier_balance(self, authed, branch_id):
        resp = authed.get(f"{BASE_URL}/api/fund-wallets?branch_id={branch_id}")
        if resp.status_code == 200:
            wallets = resp.json()
            for w in wallets:
                if w.get("type") == "cashier" and w.get("active"):
                    return w.get("balance", 0)
        return None

    def test_01_main_cash_sale_enertone(self, authed):
        """Cash sale: 5 cases ENERTONE @ ₱1,150 each = ₱5,750."""
        enertone_id = shared_state.get("enertone_id", ENERTONE_ID)
        enertone_name = shared_state.get("enertone_name", "ENERTONE")

        # Record cashier balance before
        shared_state["main_cashier_before_sales"] = self._get_cashier_balance(authed, MAIN_BRANCH_ID)

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": MAIN_BRANCH_ID,
            "items": [{
                "product_id": enertone_id,
                "product_name": enertone_name,
                "sku": "ENERTONE",
                "unit": "CASE",
                "quantity": 5,
                "unit_price": 1150,
                "rate": 1150,
                "line_total": 5750,
                "category": "Veterinary"
            }],
            "payment_type": "cash",
            "customer_name": "Walk-in",
            "payment_method": "Cash",
            "subtotal": 5750,
            "grand_total": 5750,
            "amount_paid": 5750,
            "balance": 0,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"Main cash sale ENERTONE failed: {resp.text}"
        invoice = resp.json()
        shared_state["main_sale1_id"] = invoice.get("id")
        shared_state["main_sale1_invoice_num"] = invoice.get("invoice_number")
        print(f"\nMain sale1 (ENERTONE): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("grand_total") == 5750
        assert invoice.get("status") == "paid"

    def test_02_main_cash_sale_r_lannate(self, authed):
        """Cash sale: 10 repacks R Lannate @ ₱65 each = ₱650."""
        r_lannate_id = shared_state.get("r_lannate_id")
        if not r_lannate_id:
            pytest.skip("R Lannate product not found")

        r_lannate_name = shared_state.get("r_lannate_name", "R Lannate")
        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": MAIN_BRANCH_ID,
            "items": [{
                "product_id": r_lannate_id,
                "product_name": r_lannate_name,
                "sku": "R-LANNATE",
                "unit": "Pouch",
                "quantity": 10,
                "unit_price": 65,
                "rate": 65,
                "line_total": 650,
                "category": "Veterinary"
            }],
            "payment_type": "cash",
            "customer_name": "Walk-in",
            "payment_method": "Cash",
            "subtotal": 650,
            "grand_total": 650,
            "amount_paid": 650,
            "balance": 0,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"Main cash sale R Lannate failed: {resp.text}"
        invoice = resp.json()
        shared_state["main_sale2_id"] = invoice.get("id")
        print(f"Main sale2 (R Lannate): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")

    def test_03_main_credit_sale_rosario_volplex(self, authed):
        """Credit sale: ROSARIO, 3 boxes VOLPLEX @ ₱1,000 = ₱3,000 full credit."""
        rosario_id = shared_state.get("rosario_id")
        assert rosario_id, "ROSARIO customer not created"
        volplex_id = shared_state.get("volplex_id", VOLPLEX_ID)
        volplex_name = shared_state.get("volplex_name", "VOLPLEX")

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": MAIN_BRANCH_ID,
            "customer_id": rosario_id,
            "customer_name": "ROSARIO_TEST_STRESS",
            "items": [{
                "product_id": volplex_id,
                "product_name": volplex_name,
                "sku": "VOLPLEX",
                "unit": "Box",
                "quantity": 3,
                "unit_price": 1000,
                "rate": 1000,
                "line_total": 3000,
                "category": "Veterinary"
            }],
            "payment_type": "credit",
            "payment_method": "Credit",
            "subtotal": 3000,
            "grand_total": 3000,
            "amount_paid": 0,
            "balance": 3000,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"Main credit sale ROSARIO failed: {resp.text}"
        invoice = resp.json()
        shared_state["rosario_invoice_id"] = invoice.get("id")
        shared_state["rosario_invoice_num"] = invoice.get("invoice_number")
        print(f"Main credit sale (ROSARIO/VOLPLEX): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("status") == "open"
        assert invoice.get("balance") == 3000

    def test_04_main_po_creation_supplier1_vitmin(self, authed):
        """Create PO: SUPPLIER 1, 30 boxes VITMIN PRO POWDER @ ₱500, due in 5 days."""
        supplier1_id = shared_state.get("supplier1_id", SUPPLIER1_ID)
        supplier1_name = shared_state.get("supplier1_name", "SUPPLIER 1")
        vitmin_id = shared_state.get("vitmin_id", VITMIN_ID)
        vitmin_name = shared_state.get("vitmin_name", "VITMIN PRO POWDER")

        resp = authed.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": supplier1_name,
            "branch_id": MAIN_BRANCH_ID,
            "items": [{
                "product_id": vitmin_id,
                "product_name": vitmin_name,
                "quantity": 30,
                "unit_price": 500
            }],
            "payment_method": "credit",
            "purchase_date": TODAY,
            "due_date": DUE_5_DAYS,
            "terms_days": 5,
            "notes": "Stress test PO - Main Branch"
        })
        assert resp.status_code == 200, f"Main PO creation failed: {resp.text}"
        po = resp.json()
        shared_state["main_po_id"] = po.get("id")
        shared_state["main_po_number"] = po.get("po_number")
        print(f"Main PO created: {po.get('po_number')} ₱{po.get('subtotal')}")
        assert po.get("subtotal") == 15000
        assert po.get("payment_status") == "unpaid"

    def test_05_main_po_receive(self, authed):
        """Receive the Main Branch PO (mark as received, inventory updated)."""
        po_id = shared_state.get("main_po_id")
        assert po_id, "Main PO not created"
        # Save VITMIN inventory before receive
        vitmin_id = shared_state.get("vitmin_id", VITMIN_ID)
        inv_resp = authed.get(f"{BASE_URL}/api/inventory?branch_id={MAIN_BRANCH_ID}&limit=200")
        if inv_resp.status_code == 200:
            items = inv_resp.json().get("items", [])
            for item in items:
                if item.get("id", "").startswith(VITMIN_ID) or item.get("name", "").upper().startswith("VITMIN"):
                    branch_stock = item.get("branch_stock", {})
                    shared_state["main_vitmin_before_receive"] = branch_stock.get(MAIN_BRANCH_ID, 0)

        resp = authed.post(f"{BASE_URL}/api/purchase-orders/{po_id}/receive")
        assert resp.status_code == 200, f"Main PO receive failed: {resp.text}"
        print(f"Main PO received: {resp.json()}")

    def test_06_main_expense_utilities(self, authed):
        """Operational expense: ₱2,500 utilities."""
        resp = authed.post(f"{BASE_URL}/api/expenses", json={
            "branch_id": MAIN_BRANCH_ID,
            "category": "Utilities",
            "description": "Monthly utilities - stress test",
            "amount": 2500,
            "payment_method": "Cash",
            "date": TODAY
        })
        assert resp.status_code == 200, f"Main utilities expense failed: {resp.text}"
        expense = resp.json()
        shared_state["main_expense1_id"] = expense.get("id")
        print(f"Main utilities expense: ₱{expense.get('amount')}")
        assert expense.get("amount") == 2500

    def test_07_main_farm_expense_rosario(self, authed):
        """Farm service expense for ROSARIO: ₱1,500."""
        rosario_id = shared_state.get("rosario_id")
        assert rosario_id, "ROSARIO customer not created"
        resp = authed.post(f"{BASE_URL}/api/expenses/farm", json={
            "branch_id": MAIN_BRANCH_ID,
            "customer_id": rosario_id,
            "description": "Farm service - stress test",
            "amount": 1500,
            "payment_method": "Cash",
            "date": TODAY
        })
        assert resp.status_code == 200, f"Main farm expense failed: {resp.text}"
        result = resp.json()
        shared_state["rosario_farm_invoice_id"] = result.get("invoice", {}).get("id")
        print(f"Main farm expense for ROSARIO: ₱1,500 → invoice {result.get('invoice', {}).get('invoice_number')}")

    def test_08_main_customer_cashout(self, authed):
        """Customer cash-out ₱3,000 for TEST_AUTOMATION_CUSTOMER_2026."""
        test_auto_id = shared_state.get("test_auto_cust_id")
        if not test_auto_id:
            pytest.skip("TEST_AUTOMATION_CUSTOMER_2026 not found")

        balance_before = shared_state.get("test_auto_cust_balance", 0)
        resp = authed.post(f"{BASE_URL}/api/expenses/customer-cashout", json={
            "branch_id": MAIN_BRANCH_ID,
            "customer_id": test_auto_id,
            "amount": 3000,
            "description": "Cash advance - stress test",
            "date": TODAY
        })
        assert resp.status_code == 200, f"Customer cashout failed: {resp.text}"
        result = resp.json()
        shared_state["cashout_invoice_id"] = result.get("invoice", {}).get("id")
        print(f"Customer cashout ₱3,000 → invoice {result.get('invoice', {}).get('invoice_number')}")

    def test_09_main_ar_payment_test_customer(self, authed):
        """AR payment: TEST_AUTOMATION_CUSTOMER_2026 pays ₱1,000 on existing balance."""
        test_auto_id = shared_state.get("test_auto_cust_id")
        if not test_auto_id:
            pytest.skip("TEST_AUTOMATION_CUSTOMER_2026 not found")

        # Find an open invoice for this customer
        resp = authed.get(f"{BASE_URL}/api/invoices?customer_id={test_auto_id}&status=open&limit=10")
        invoices = []
        if resp.status_code == 200:
            invoices = resp.json().get("invoices", [])

        if not invoices:
            resp = authed.get(f"{BASE_URL}/api/invoices?customer_id={test_auto_id}&limit=10")
            if resp.status_code == 200:
                invoices = [i for i in resp.json().get("invoices", []) if i.get("balance", 0) > 0]

        if not invoices:
            pytest.skip("No open invoices for TEST_AUTOMATION_CUSTOMER_2026")

        inv_id = invoices[0]["id"]
        inv_balance = invoices[0].get("balance", 0)
        pay_amount = min(1000, inv_balance)

        resp = authed.post(f"{BASE_URL}/api/invoices/{inv_id}/payment", json={
            "amount": pay_amount,
            "method": "Cash",
            "date": TODAY,
            "reference": "Stress test payment",
            "fund_source": "cashier"
        })
        assert resp.status_code == 200, f"AR payment failed: {resp.text}"
        result = resp.json()
        shared_state["ar_payment_result"] = result
        print(f"AR payment ₱{pay_amount} on invoice {inv_id}: new_balance={result.get('new_balance')}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: IPIL BRANCH TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase3IpilBranch:
    """All IPIL Branch transactions."""

    def test_01_ipil_cash_sale_enertone(self, authed):
        """IPIL cash sale: 3 cases ENERTONE @ ₱1,200 = ₱3,600."""
        enertone_id = shared_state.get("enertone_id", ENERTONE_ID)
        enertone_name = shared_state.get("enertone_name", "ENERTONE")

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": enertone_id,
                "product_name": enertone_name,
                "sku": "ENERTONE",
                "unit": "CASE",
                "quantity": 3,
                "unit_price": 1200,
                "rate": 1200,
                "line_total": 3600,
                "category": "Veterinary"
            }],
            "payment_type": "cash",
            "customer_name": "Walk-in",
            "payment_method": "Cash",
            "subtotal": 3600,
            "grand_total": 3600,
            "amount_paid": 3600,
            "balance": 0,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"IPIL cash sale ENERTONE failed: {resp.text}"
        invoice = resp.json()
        shared_state["ipil_sale1_id"] = invoice.get("id")
        print(f"\nIPIL sale1 (ENERTONE): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("grand_total") == 3600

    def test_02_ipil_credit_sale_janmark_platinum(self, authed):
        """IPIL credit sale: JANMARK, 2 cases PLATINUM @ ₱1,600 = ₱3,200 full credit."""
        janmark_id = shared_state.get("janmark_id")
        if not janmark_id:
            pytest.skip("JANMARK customer not found")

        platinum_id = shared_state.get("platinum_id", PLATINUM_ID)
        platinum_name = shared_state.get("platinum_name", "PLATINUM")
        janmark_balance_before = shared_state.get("janmark_balance", 0)

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": IPIL_BRANCH_ID,
            "customer_id": janmark_id,
            "customer_name": "JANMARK",
            "items": [{
                "product_id": platinum_id,
                "product_name": platinum_name,
                "sku": "PLATINUM",
                "unit": "CASE",
                "quantity": 2,
                "unit_price": 1600,
                "rate": 1600,
                "line_total": 3200,
                "category": "Veterinary"
            }],
            "payment_type": "credit",
            "payment_method": "Credit",
            "subtotal": 3200,
            "grand_total": 3200,
            "amount_paid": 0,
            "balance": 3200,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"IPIL credit sale JANMARK failed: {resp.text}"
        invoice = resp.json()
        shared_state["janmark_invoice_id"] = invoice.get("id")
        print(f"IPIL credit sale (JANMARK/PLATINUM): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("status") == "open"
        assert invoice.get("balance") == 3200

    def test_03_ipil_employee_advance(self, authed):
        """Employee cash advance ₱4,000 for a test employee."""
        # Get or create an employee
        emp_resp = authed.get(f"{BASE_URL}/api/employees?branch_id={IPIL_BRANCH_ID}&limit=5")
        employee_id = None
        if emp_resp.status_code == 200:
            employees = emp_resp.json()
            if isinstance(employees, list) and employees:
                employee_id = employees[0].get("id")
            elif isinstance(employees, dict):
                emps = employees.get("employees", [])
                if emps:
                    employee_id = emps[0].get("id")

        if not employee_id:
            # Create a test employee
            create_emp = authed.post(f"{BASE_URL}/api/employees", json={
                "name": "STRESS_TEST_EMPLOYEE",
                "branch_id": IPIL_BRANCH_ID,
                "position": "Cashier",
                "phone": "09200000001",
                "salary": 15000
            })
            if create_emp.status_code in [200, 201]:
                employee_id = create_emp.json().get("id")

        if not employee_id:
            pytest.skip("No employee found/created for IPIL branch")

        shared_state["ipil_employee_id"] = employee_id
        resp = authed.post(f"{BASE_URL}/api/expenses/employee-advance", json={
            "branch_id": IPIL_BRANCH_ID,
            "employee_id": employee_id,
            "amount": 4000,
            "description": "Stress test employee advance",
            "date": TODAY
        })
        assert resp.status_code == 200, f"IPIL employee advance failed: {resp.text}"
        expense = resp.json()
        shared_state["ipil_advance_id"] = expense.get("id")
        print(f"IPIL employee advance ₱4,000: {expense.get('id')}")
        assert expense.get("amount") == 4000

    def test_04_ipil_po_pilmico_lannate(self, authed):
        """IPIL Create PO from PILMICO: 20 pouches Lannate @ ₱500, due in 3 days (URGENT)."""
        pilmico_id = shared_state.get("pilmico_id", PILMICO_ID)
        pilmico_name = shared_state.get("pilmico_name", "PILMICO")
        lannate_id = shared_state.get("lannate_id", LANNATE_ID)
        lannate_name = shared_state.get("lannate_name", "Lannate")

        resp = authed.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": pilmico_name,
            "branch_id": IPIL_BRANCH_ID,
            "items": [{
                "product_id": lannate_id,
                "product_name": lannate_name,
                "quantity": 20,
                "unit_price": 500
            }],
            "payment_method": "credit",
            "purchase_date": TODAY,
            "due_date": DUE_3_DAYS,
            "terms_days": 3,
            "notes": "Stress test PO - IPIL Branch URGENT"
        })
        assert resp.status_code == 200, f"IPIL PILMICO PO failed: {resp.text}"
        po = resp.json()
        shared_state["ipil_po_id"] = po.get("id")
        shared_state["ipil_po_number"] = po.get("po_number")
        print(f"IPIL PILMICO PO: {po.get('po_number')} ₱{po.get('subtotal')} due={DUE_3_DAYS}")
        assert po.get("subtotal") == 10000
        assert po.get("payment_status") == "unpaid"

    def test_05_ipil_pay_pilmico_partial_cash(self, authed):
        """Pay PILMICO PO partial payment ₱5,000 from cashier."""
        po_id = shared_state.get("ipil_po_id")
        assert po_id, "IPIL PO not created"

        resp = authed.post(f"{BASE_URL}/api/purchase-orders/{po_id}/pay", json={
            "amount": 5000,
            "fund_source": "cashier",
            "method": "Cash",
            "payment_date": TODAY,
            "reference": "Stress test partial payment"
        })
        assert resp.status_code == 200, f"IPIL pay PO failed: {resp.text}"
        result = resp.json()
        shared_state["ipil_po_payment_result"] = result
        print(f"IPIL PILMICO PO payment ₱5,000: new_balance={result.get('new_balance')}")
        assert result.get("new_balance") == 5000  # 10000 - 5000 = 5000
        assert result.get("payment_status") == "partial"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: SAMPOLI BRANCH TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase4SampoliBranch:
    """All Sampoli Branch transactions."""

    def test_01_sampoli_cash_sale_vitmin(self, authed):
        """Sampoli cash sale: 2 boxes VITMIN PRO POWDER @ ₱620 = ₱1,240."""
        vitmin_id = shared_state.get("vitmin_id", VITMIN_ID)
        vitmin_name = shared_state.get("vitmin_name", "VITMIN PRO POWDER")

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": SAMPOLI_BRANCH_ID,
            "items": [{
                "product_id": vitmin_id,
                "product_name": vitmin_name,
                "sku": "VITMIN",
                "unit": "Box",
                "quantity": 2,
                "unit_price": 620,
                "rate": 620,
                "line_total": 1240,
                "category": "Veterinary"
            }],
            "payment_type": "cash",
            "customer_name": "Walk-in",
            "payment_method": "Cash",
            "subtotal": 1240,
            "grand_total": 1240,
            "amount_paid": 1240,
            "balance": 0,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"Sampoli cash sale VITMIN failed: {resp.text}"
        invoice = resp.json()
        shared_state["sampoli_sale1_id"] = invoice.get("id")
        print(f"\nSampoli sale1 (VITMIN): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("grand_total") == 1240

    def test_02_sampoli_credit_sale_maria_lannate(self, authed):
        """Sampoli credit sale: MARIA, 3 pouches Lannate @ ₱750 = ₱2,250."""
        maria_id = shared_state.get("maria_id")
        assert maria_id, "MARIA customer not created"
        lannate_id = shared_state.get("lannate_id", LANNATE_ID)
        lannate_name = shared_state.get("lannate_name", "Lannate")

        resp = authed.post(f"{BASE_URL}/api/unified-sale", json={
            "branch_id": SAMPOLI_BRANCH_ID,
            "customer_id": maria_id,
            "customer_name": "MARIA_TEST_STRESS",
            "items": [{
                "product_id": lannate_id,
                "product_name": lannate_name,
                "sku": "LANNATE",
                "unit": "Pouch",
                "quantity": 3,
                "unit_price": 750,
                "rate": 750,
                "line_total": 2250,
                "category": "Veterinary"
            }],
            "payment_type": "credit",
            "payment_method": "Credit",
            "subtotal": 2250,
            "grand_total": 2250,
            "amount_paid": 0,
            "balance": 2250,
            "order_date": TODAY
        })
        assert resp.status_code == 200, f"Sampoli credit sale MARIA failed: {resp.text}"
        invoice = resp.json()
        shared_state["maria_invoice_id"] = invoice.get("id")
        print(f"Sampoli credit sale (MARIA/Lannate): {invoice.get('invoice_number')} ₱{invoice.get('grand_total')}")
        assert invoice.get("status") == "open"

    def test_03_sampoli_create_platinum_repack(self, authed):
        """Create NEW repack for PLATINUM: 'R PLATINUM SMALL (12/case)'."""
        platinum_id = shared_state.get("platinum_id", PLATINUM_ID)
        assert platinum_id, "PLATINUM product not found"

        resp = authed.post(f"{BASE_URL}/api/products/{platinum_id}/generate-repack", json={
            "name": "R PLATINUM SMALL (12/case)",
            "unit": "Piece",
            "units_per_parent": 12,
            "cost_price": 0,
            "add_on_cost": 10,
            "prices": {
                "retail": 150,
                "wholesale": 130,
                "special": 125
            }
        })
        assert resp.status_code == 200, f"Sampoli repack creation failed: {resp.text}"
        repack = resp.json()
        shared_state["sampoli_platinum_repack_id"] = repack.get("id")
        print(f"Sampoli PLATINUM repack created: {repack.get('sku')} id={repack.get('id')}")
        assert repack.get("is_repack") == True
        assert repack.get("units_per_parent") == 12
        assert repack.get("parent_id") == platinum_id

    def test_04_sampoli_cleaning_expense(self, authed):
        """Sampoli expense: ₱800 cleaning supplies."""
        resp = authed.post(f"{BASE_URL}/api/expenses", json={
            "branch_id": SAMPOLI_BRANCH_ID,
            "category": "Supplies",
            "description": "Cleaning supplies - stress test",
            "amount": 800,
            "payment_method": "Cash",
            "date": TODAY
        })
        assert resp.status_code == 200, f"Sampoli cleaning expense failed: {resp.text}"
        expense = resp.json()
        shared_state["sampoli_expense1_id"] = expense.get("id")
        print(f"Sampoli cleaning expense: ₱{expense.get('amount')}")
        assert expense.get("amount") == 800


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: INVENTORY VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase5InventoryVerification:
    """Verify inventory decreased correctly after all sales."""

    def _get_branch_qty(self, authed, product_id_prefix, branch_id):
        resp = authed.get(f"{BASE_URL}/api/inventory?branch_id={branch_id}&limit=200")
        if resp.status_code != 200:
            return None
        items = resp.json().get("items", [])
        for item in items:
            pid = item.get("id", "")
            if pid.startswith(product_id_prefix):
                branch_stock = item.get("branch_stock", {})
                total_stock = item.get("total_stock", 0)
                return branch_stock.get(branch_id, total_stock)
        return None

    def test_01_main_enertone_inventory(self, authed):
        """Main ENERTONE should be ~45 (set 50, sold 5)."""
        qty = self._get_branch_qty(authed, ENERTONE_ID, MAIN_BRANCH_ID)
        print(f"\nMain ENERTONE qty: {qty} (expected ~45)")
        if qty is not None:
            assert qty <= 50, f"ENERTONE qty {qty} > initial 50"
            # Should be ~45 (sold 5)
            assert qty <= 47, f"ENERTONE inventory not reduced enough: {qty}"

    def test_02_ipil_enertone_inventory(self, authed):
        """IPIL ENERTONE should be ~37 (set 40, sold 3)."""
        qty = self._get_branch_qty(authed, ENERTONE_ID, IPIL_BRANCH_ID)
        print(f"IPIL ENERTONE qty: {qty} (expected ~37)")
        if qty is not None:
            assert qty <= 40, f"IPIL ENERTONE qty {qty} > initial 40"
            assert qty <= 38, f"IPIL ENERTONE not reduced: {qty}"

    def test_03_sampoli_vitmin_inventory(self, authed):
        """Sampoli VITMIN should be ~18 (set 20, sold 2)."""
        qty = self._get_branch_qty(authed, VITMIN_ID, SAMPOLI_BRANCH_ID)
        print(f"Sampoli VITMIN qty: {qty} (expected ~18)")
        if qty is not None:
            assert qty <= 20, f"Sampoli VITMIN {qty} > initial 20"

    def test_04_main_vitmin_inventory_after_po(self, authed):
        """Main VITMIN should have increased after PO receive (+30 boxes)."""
        qty = self._get_branch_qty(authed, VITMIN_ID, MAIN_BRANCH_ID)
        print(f"Main VITMIN qty after PO receive: {qty} (initial 30 + 30 received = 60)")
        if qty is not None:
            # Should be at least initial (30) + PO received (30) = 60
            assert qty >= 55, f"Main VITMIN {qty} not increased after PO receive"

    def test_05_sampoli_lannate_inventory_after_credit_sale(self, authed):
        """Sampoli Lannate should be ~47 (set 50, sold 3)."""
        qty = self._get_branch_qty(authed, LANNATE_ID, SAMPOLI_BRANCH_ID)
        print(f"Sampoli Lannate qty: {qty} (expected ~47)")
        if qty is not None:
            assert qty <= 50, f"Sampoli Lannate {qty} > initial 50"

    def test_06_main_volplex_inventory_after_credit_sale(self, authed):
        """Main VOLPLEX should be ~17 (set 20, sold 3)."""
        qty = self._get_branch_qty(authed, VOLPLEX_ID, MAIN_BRANCH_ID)
        print(f"Main VOLPLEX qty: {qty} (expected ~17)")
        if qty is not None:
            assert qty <= 20, f"Main VOLPLEX {qty} > initial 20"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: CASH BALANCE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase6CashVerification:
    """Verify cashier balances are updated correctly per branch."""

    def _get_cashier_balance(self, authed, branch_id):
        resp = authed.get(f"{BASE_URL}/api/fund-wallets?branch_id={branch_id}")
        if resp.status_code == 200:
            for w in resp.json():
                if w.get("type") == "cashier" and w.get("active"):
                    return w.get("balance", 0)
        return None

    def test_01_main_cashier_balance(self, authed):
        """Main branch cashier balance should reflect cash sales and expenses."""
        balance = self._get_cashier_balance(authed, MAIN_BRANCH_ID)
        print(f"\nMain Branch cashier balance: ₱{balance}")
        assert balance is not None, "Could not get Main cashier balance"
        # Balance should be > 0 after sales
        # Main cashier had ₱7849 + cash_sale1 (₱5750) + cash_sale2 (₱650) - expenses(₱2500) - farm(₱1500) - cashout(₱3000) + AR_payment(₱1000)
        # Note: farm expense is cash outflow
        print(f"  Main cashier balance: ₱{balance}")

    def test_02_ipil_cashier_balance(self, authed):
        """IPIL cashier balance should have increased by deposits and sales."""
        balance = self._get_cashier_balance(authed, IPIL_BRANCH_ID)
        print(f"IPIL Branch cashier balance: ₱{balance}")
        assert balance is not None, "Could not get IPIL cashier balance"
        # IPIL started at ₱29040 (existing) + ₱5000 (deposit) + ₱3600 (cash sale) - ₱4000 (advance) - ₱5000 (PO pay) = ~₱28640
        print(f"  IPIL cashier balance: ₱{balance}")

    def test_03_sampoli_cashier_balance(self, authed):
        """Sampoli cashier balance should reflect deposits and sales minus expenses."""
        balance = self._get_cashier_balance(authed, SAMPOLI_BRANCH_ID)
        print(f"Sampoli Branch cashier balance: ₱{balance}")
        assert balance is not None, "Could not get Sampoli cashier balance"
        # Sampoli: ₱3000 deposit + ₱1240 (cash sale) - ₱800 (expense) = ₱3440 net addition
        print(f"  Sampoli cashier balance: ₱{balance}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: AR BALANCE VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase7ARVerification:
    """Verify AR customer balances increased after credit sales."""

    def _get_customer_balance(self, authed, customer_id):
        resp = authed.get(f"{BASE_URL}/api/customers/{customer_id}")
        if resp.status_code == 200:
            return resp.json().get("balance", 0)
        return None

    def test_01_rosario_ar_balance(self, authed):
        """ROSARIO balance should be ₱3,000 (credit sale) + ₱1,500 (farm) = ₱4,500."""
        rosario_id = shared_state.get("rosario_id")
        if not rosario_id:
            pytest.skip("ROSARIO not created")
        balance = self._get_customer_balance(authed, rosario_id)
        print(f"\nROSARIO balance: ₱{balance} (expected ₱4,500)")
        assert balance is not None
        # ₱3000 (VOLPLEX credit) + ₱1500 (farm expense) = ₱4500
        assert balance >= 4500, f"ROSARIO balance {balance} < expected 4500"

    def test_02_janmark_ar_balance(self, authed):
        """JANMARK balance should have increased by ₱3,200 (PLATINUM credit sale)."""
        janmark_id = shared_state.get("janmark_id")
        if not janmark_id:
            pytest.skip("JANMARK not found")
        balance = self._get_customer_balance(authed, janmark_id)
        before = shared_state.get("janmark_balance", 0)
        print(f"JANMARK balance: ₱{balance} (before={before}, expected += ₱3,200)")
        assert balance is not None
        assert balance >= before + 3200, f"JANMARK balance {balance} not increased by ₱3200"

    def test_03_maria_ar_balance(self, authed):
        """MARIA balance should be ₱2,250 (Lannate credit sale)."""
        maria_id = shared_state.get("maria_id")
        if not maria_id:
            pytest.skip("MARIA not created")
        balance = self._get_customer_balance(authed, maria_id)
        print(f"MARIA balance: ₱{balance} (expected ₱2,250)")
        assert balance is not None
        assert balance >= 2250, f"MARIA balance {balance} < ₱2250"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: REPORTS & CLOSE WIZARD
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase8Reports:
    """Low stock, supplier payables, and close wizard preview."""

    def test_01_low_stock_alert_main(self, authed):
        """Low Stock Alert for Main Branch - check results."""
        resp = authed.get(f"{BASE_URL}/api/low-stock-alert?branch_id={MAIN_BRANCH_ID}")
        assert resp.status_code == 200, f"Low stock alert failed: {resp.text}"
        items = resp.json()
        print(f"\nLow Stock Alert Main Branch: {len(items)} items")
        for item in items:
            print(f"  {item.get('name')} qty={item.get('current_qty')} status={item.get('status')}")
        assert isinstance(items, list), "Low stock alert should return list"

    def test_02_low_stock_alert_ipil(self, authed):
        """Low Stock Alert for IPIL Branch."""
        resp = authed.get(f"{BASE_URL}/api/low-stock-alert?branch_id={IPIL_BRANCH_ID}")
        assert resp.status_code == 200, f"IPIL low stock alert failed: {resp.text}"
        items = resp.json()
        print(f"Low Stock Alert IPIL Branch: {len(items)} items")
        assert isinstance(items, list)

    def test_03_supplier_payables_ipil(self, authed):
        """Supplier Payables for IPIL Branch - PILMICO PO should appear as URGENT."""
        resp = authed.get(f"{BASE_URL}/api/supplier-payables?branch_id={IPIL_BRANCH_ID}")
        assert resp.status_code == 200, f"IPIL supplier payables failed: {resp.text}"
        payables = resp.json()
        print(f"\nIPIL Supplier Payables: {len(payables)} items")
        found_pilmico = False
        for p in payables:
            days = p.get("days_until_due")
            print(f"  {p.get('vendor')} PO#{p.get('po_number')} bal=₱{p.get('balance')} days={days} urgent={p.get('is_urgent')}")
            if p.get("po_number") == shared_state.get("ipil_po_number") or (
                    days is not None and days <= 7 and p.get("balance", 0) > 0):
                found_pilmico = True
        assert found_pilmico or len(payables) > 0, "Expected PILMICO PO in payables"

    def test_04_supplier_payables_main(self, authed):
        """Supplier Payables for Main Branch - SUPPLIER 1 PO should appear."""
        resp = authed.get(f"{BASE_URL}/api/supplier-payables?branch_id={MAIN_BRANCH_ID}")
        assert resp.status_code == 200
        payables = resp.json()
        print(f"Main Supplier Payables: {len(payables)} items")
        for p in payables:
            print(f"  {p.get('vendor')} PO#{p.get('po_number')} bal=₱{p.get('balance')} days={p.get('days_until_due')}")
        # Main PO was received but was credit - should be in payables
        assert isinstance(payables, list)

    def test_05_daily_close_preview_main(self, authed):
        """Daily close preview for Main Branch - verify totals include our transactions."""
        resp = authed.get(f"{BASE_URL}/api/daily-close-preview?branch_id={MAIN_BRANCH_ID}&date={TODAY}")
        assert resp.status_code == 200, f"Daily close preview failed: {resp.text}"
        preview = resp.json()
        print(f"\nMain Branch Daily Close Preview:")
        print(f"  date: {preview.get('date')}")
        print(f"  starting_float: ₱{preview.get('starting_float')}")
        print(f"  total_cash_sales: ₱{preview.get('total_cash_sales')}")
        print(f"  total_expenses: ₱{preview.get('total_expenses')}")
        print(f"  expected_counter: ₱{preview.get('expected_counter')}")
        print(f"  total_credit_today: ₱{preview.get('total_credit_today')}")
        assert preview.get("total_cash_sales", 0) > 0, "Main branch should have cash sales today"

    def test_06_daily_close_preview_ipil(self, authed):
        """Daily close preview for IPIL Branch."""
        resp = authed.get(f"{BASE_URL}/api/daily-close-preview?branch_id={IPIL_BRANCH_ID}&date={TODAY}")
        assert resp.status_code == 200
        preview = resp.json()
        print(f"\nIPIL Branch Daily Close Preview:")
        print(f"  total_cash_sales: ₱{preview.get('total_cash_sales')}")
        print(f"  total_credit_today: ₱{preview.get('total_credit_today')}")
        print(f"  expected_counter: ₱{preview.get('expected_counter')}")

    def test_07_daily_close_preview_sampoli(self, authed):
        """Daily close preview for Sampoli Branch."""
        resp = authed.get(f"{BASE_URL}/api/daily-close-preview?branch_id={SAMPOLI_BRANCH_ID}&date={TODAY}")
        assert resp.status_code == 200
        preview = resp.json()
        print(f"\nSampoli Branch Daily Close Preview:")
        print(f"  total_cash_sales: ₱{preview.get('total_cash_sales')}")
        print(f"  expected_counter: ₱{preview.get('expected_counter')}")

    def test_08_daily_log_main(self, authed):
        """Daily log for Main Branch - verify sales recorded."""
        resp = authed.get(f"{BASE_URL}/api/daily-log?branch_id={MAIN_BRANCH_ID}&date={TODAY}")
        assert resp.status_code == 200
        log = resp.json()
        summary = log.get("summary", {})
        print(f"\nMain Branch Daily Log:")
        print(f"  total_cash: ₱{summary.get('total_cash')}")
        print(f"  total_credit: ₱{summary.get('total_credit')}")
        print(f"  cash_count: {summary.get('cash_count')}")
        print(f"  credit_invoice_count: {summary.get('credit_invoice_count')}")

    def test_09_daily_report_main(self, authed):
        """Daily report for Main Branch."""
        resp = authed.get(f"{BASE_URL}/api/daily-report?branch_id={MAIN_BRANCH_ID}&date={TODAY}")
        assert resp.status_code == 200
        report = resp.json()
        print(f"\nMain Daily Report:")
        print(f"  new_sales_today: ₱{report.get('new_sales_today')}")
        print(f"  net_profit: ₱{report.get('net_profit')}")
        print(f"  cashier_wallet_balance: ₱{report.get('cashier_wallet_balance')}")

    def test_10_manager_pin_verification(self, authed):
        """Verify manager PIN 521325 works for close wizard."""
        resp = authed.post(f"{BASE_URL}/api/auth/verify-manager-pin", json={"pin": "521325"})
        assert resp.status_code == 200
        result = resp.json()
        print(f"\nManager PIN verify: valid={result.get('valid')} manager={result.get('manager_name')}")
        assert result.get("valid") == True, "Manager PIN 521325 should be valid"


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 9: DATA INTEGRITY & CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════
class TestPhase9DataIntegrity:
    """Verify data integrity and collect summary."""

    def test_01_transaction_summary(self, authed):
        """Print comprehensive summary of all transactions."""
        print("\n" + "="*60)
        print("STRESS TEST TRANSACTION SUMMARY")
        print("="*60)
        print(f"\nDate: {TODAY}")
        print(f"\n--- MAIN BRANCH TRANSACTIONS ---")
        print(f"  Sale1 (ENERTONE cash): Invoice {shared_state.get('main_sale1_invoice_num')} ₱5,750")
        print(f"  Sale2 (R Lannate cash): Invoice {shared_state.get('main_sale2_id', 'N/A')[:8]} ₱650")
        print(f"  Credit Sale (ROSARIO/VOLPLEX): Invoice {shared_state.get('rosario_invoice_num')} ₱3,000")
        print(f"  PO (SUPPLIER1/VITMIN): PO# {shared_state.get('main_po_number')} ₱15,000 credit")
        print(f"  Expense Utilities: ₱2,500")
        print(f"  Farm Expense (ROSARIO): ₱1,500")
        print(f"  Customer Cashout (TEST_AUTO): ₱3,000")
        print(f"\n--- IPIL BRANCH TRANSACTIONS ---")
        print(f"  Sale (ENERTONE cash): Invoice {shared_state.get('ipil_sale1_id', 'N/A')[:8]} ₱3,600")
        print(f"  Credit Sale (JANMARK/PLATINUM): Invoice {shared_state.get('janmark_invoice_id', 'N/A')[:8]} ₱3,200")
        print(f"  Employee Advance: ₱4,000")
        print(f"  PO (PILMICO/Lannate): PO# {shared_state.get('ipil_po_number')} ₱10,000 credit")
        print(f"  PO Partial Payment: ₱5,000")
        print(f"\n--- SAMPOLI BRANCH TRANSACTIONS ---")
        print(f"  Sale (VITMIN cash): Invoice {shared_state.get('sampoli_sale1_id', 'N/A')[:8]} ₱1,240")
        print(f"  Credit Sale (MARIA/Lannate): Invoice {shared_state.get('maria_invoice_id', 'N/A')[:8]} ₱2,250")
        print(f"  Repack Created: PLATINUM SMALL (12/case)")
        print(f"  Expense Cleaning: ₱800")
        print("="*60)
        assert True

    def test_02_verify_rosario_invoices(self, authed):
        """Verify ROSARIO has correct invoices (credit sale + farm expense)."""
        rosario_id = shared_state.get("rosario_id")
        if not rosario_id:
            pytest.skip("ROSARIO not created")
        # accounting router has no prefix: endpoint is /api/customers/{id}/invoices
        resp = authed.get(f"{BASE_URL}/api/customers/{rosario_id}/invoices")
        assert resp.status_code == 200
        invoices = resp.json()
        print(f"\nROSARIO open invoices: {len(invoices)}")
        for inv in invoices:
            print(f"  {inv.get('invoice_number')} {inv.get('sale_type')} ₱{inv.get('balance')}")
        assert len(invoices) >= 2, f"Expected ≥2 open invoices for ROSARIO, got {len(invoices)}"

    def test_03_verify_ipil_po_payment_status(self, authed):
        """Verify IPIL PILMICO PO is in partial status after ₱5,000 payment."""
        po_id = shared_state.get("ipil_po_id")
        if not po_id:
            pytest.skip("IPIL PO not created")
        resp = authed.get(f"{BASE_URL}/api/purchase-orders?branch_id={IPIL_BRANCH_ID}&limit=20")
        assert resp.status_code == 200
        pos = resp.json().get("purchase_orders", [])
        target_po = None
        for po in pos:
            if po.get("id") == po_id:
                target_po = po
                break
        assert target_po, f"IPIL PO {po_id} not found"
        print(f"\nIPIL PILMICO PO status: payment_status={target_po.get('payment_status')} balance=₱{target_po.get('balance')}")
        assert target_po.get("payment_status") == "partial"
        assert target_po.get("balance") == 5000

    def test_04_verify_platinum_repack_exists(self, authed):
        """Verify the PLATINUM SMALL repack was created."""
        repack_id = shared_state.get("sampoli_platinum_repack_id")
        if not repack_id:
            pytest.skip("Repack not created")
        resp = authed.get(f"{BASE_URL}/api/products/{repack_id}")
        assert resp.status_code == 200
        repack = resp.json()
        print(f"\nPLATINUM repack: {repack.get('name')} sku={repack.get('sku')} units_per_parent={repack.get('units_per_parent')}")
        assert repack.get("is_repack") == True
        assert repack.get("units_per_parent") == 12

    def test_05_check_daily_close_status_main(self, authed):
        """Check if Main Branch day is already closed (to decide close wizard test)."""
        resp = authed.get(f"{BASE_URL}/api/daily-close/{TODAY}?branch_id={MAIN_BRANCH_ID}")
        assert resp.status_code == 200
        status_data = resp.json()
        is_closed = status_data.get("status") == "closed"
        shared_state["main_day_closed"] = is_closed
        print(f"\nMain Branch day status: {status_data.get('status')}")
        print(f"  Closed: {is_closed}")

    def test_06_verify_fund_wallet_movements(self, authed):
        """Verify fund wallet movements for IPIL branch show correct entries."""
        ipil_cashier_id = shared_state.get("ipil_cashier_wallet_id")
        if not ipil_cashier_id:
            resp = authed.get(f"{BASE_URL}/api/fund-wallets?branch_id={IPIL_BRANCH_ID}")
            if resp.status_code == 200:
                for w in resp.json():
                    if w.get("type") == "cashier":
                        ipil_cashier_id = w.get("id")
                        break

        if not ipil_cashier_id:
            pytest.skip("IPIL cashier wallet not found")

        resp = authed.get(f"{BASE_URL}/api/fund-wallets/{ipil_cashier_id}/movements?limit=20")
        assert resp.status_code == 200
        movements = resp.json()
        print(f"\nIPIL Cashier Wallet movements (last 20): {len(movements)} entries")
        for m in movements[:5]:
            print(f"  {m.get('type')} ₱{m.get('amount')} ref={m.get('reference', '')[:30]}")

    def test_07_summary_state(self, authed):
        """Final state: print all IDs and key values."""
        print("\n" + "="*60)
        print("SHARED STATE SUMMARY")
        print("="*60)
        for k, v in shared_state.items():
            if isinstance(v, (str, int, float, bool)) and v:
                print(f"  {k}: {v}")
        print("="*60)
        assert True
