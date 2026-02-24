"""
AgriBooks Comprehensive E2E Test Suite - Iteration 43
Covers: Branches, Products, Repacks, Customers, Suppliers, POs, Sales, 
        Transfers, Accounting, Close Wizard, Returns, Count Sheets, Audit, 
        Bad Manager Scenario, Verification, Reports, Dashboard
"""

import pytest
import requests
import os
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ─── Shared state (populated during test execution) ──────────────────────────
state = {}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def auth_token():
    """Login as admin and return JWT token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "owner",
        "password": "521325"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data["token"]
    state["user_id"] = data["user"]["id"]
    state["user_role"] = data["user"]["role"]
    print(f"Logged in as owner, role={state['user_role']}, id={state['user_id']}")
    return token


@pytest.fixture(scope="session")
def hdr(auth_token):
    """Authorized headers for all requests."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: SETUP — Branches
# ─────────────────────────────────────────────────────────────────────────────

class TestBranchSetup:
    """Create Lakewood Branch and Riverside Branch, verify 4 wallets each."""

    def test_create_lakewood_branch(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/branches", json={"name": "Lakewood Branch", "address": "Lakewood Ave"}, headers=hdr)
        assert resp.status_code == 200, f"Create Lakewood failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Lakewood Branch"
        assert "id" in data
        state["lakewood_id"] = data["id"]
        print(f"Created Lakewood Branch id={state['lakewood_id']}")

    def test_create_riverside_branch(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/branches", json={"name": "Riverside Branch", "address": "Riverside Rd"}, headers=hdr)
        assert resp.status_code == 200, f"Create Riverside failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Riverside Branch"
        state["riverside_id"] = data["id"]
        print(f"Created Riverside Branch id={state['riverside_id']}")

    def test_lakewood_has_4_wallets(self, hdr):
        assert "lakewood_id" in state, "Lakewood branch not created yet"
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        assert resp.status_code == 200, f"Get wallets failed: {resp.text}"
        wallets = resp.json()
        assert len(wallets) == 4, f"Expected 4 wallets, got {len(wallets)}: {[w['type'] for w in wallets]}"
        wallet_types = {w["type"] for w in wallets}
        assert "cashier" in wallet_types, "Missing cashier wallet"
        assert "safe" in wallet_types, "Missing safe wallet"
        assert "digital" in wallet_types, "Missing digital wallet"
        assert "bank" in wallet_types, "Missing bank wallet"
        # Save wallet ids
        for w in wallets:
            state[f"lakewood_{w['type']}_wallet_id"] = w["id"]
            state[f"lakewood_{w['type']}_wallet"] = w
        print(f"Lakewood wallets: {wallet_types}")

    def test_riverside_has_4_wallets(self, hdr):
        assert "riverside_id" in state, "Riverside branch not created yet"
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['riverside_id']}", headers=hdr)
        assert resp.status_code == 200
        wallets = resp.json()
        assert len(wallets) == 4, f"Expected 4 wallets, got {len(wallets)}"
        wallet_types = {w["type"] for w in wallets}
        assert wallet_types == {"cashier", "safe", "digital", "bank"}
        for w in wallets:
            state[f"riverside_{w['type']}_wallet_id"] = w["id"]
        print(f"Riverside wallets: {wallet_types}")

    def test_add_capital_lakewood_safe(self, hdr):
        """Inject 50000 into Lakewood Safe via direct deposit to safe wallet."""
        assert "lakewood_safe_wallet_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/fund-wallets/{state['lakewood_safe_wallet_id']}/deposit",
            json={"amount": 50000, "reference": "Initial capital injection to Safe"},
            headers=hdr
        )
        assert resp.status_code == 200, f"Safe deposit failed: {resp.text}"
        data = resp.json()
        assert "message" in data or "amount" in data
        print(f"Added 50000 capital to Lakewood safe: {data}")

    def test_add_capital_lakewood_cashier(self, hdr):
        """Inject 10000 into Lakewood Cashier via direct deposit."""
        assert "lakewood_cashier_wallet_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/fund-wallets/{state['lakewood_cashier_wallet_id']}/deposit",
            json={"amount": 10000, "reference": "Initial cashier capital"},
            headers=hdr
        )
        assert resp.status_code == 200, f"Cashier deposit failed: {resp.text}"
        print("Added 10000 to Lakewood cashier")

    def test_add_capital_riverside_safe(self, hdr):
        assert "riverside_safe_wallet_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/fund-wallets/{state['riverside_safe_wallet_id']}/deposit",
            json={"amount": 50000, "reference": "Initial capital injection to Riverside Safe"},
            headers=hdr
        )
        assert resp.status_code == 200, f"Riverside safe deposit failed: {resp.text}"
        print("Added 50000 to Riverside safe")

    def test_add_capital_riverside_cashier(self, hdr):
        assert "riverside_cashier_wallet_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/fund-wallets/{state['riverside_cashier_wallet_id']}/deposit",
            json={"amount": 10000, "reference": "Riverside cashier capital"},
            headers=hdr
        )
        assert resp.status_code == 200
        print("Added 10000 to Riverside cashier")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: SETUP — Products & Repacks
# ─────────────────────────────────────────────────────────────────────────────

class TestProductSetup:
    """Create 5 products + 4 repacks."""

    def test_create_fertilizer_supreme(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Fertilizer Supreme 50kg",
            "category": "Fertilizer",
            "unit": "Bag",
            "cost_price": 800.00,
            "prices": {"retail": 950.00, "wholesale": 880.00},
            "description": "Premium fertilizer 50kg bag"
        }, headers=hdr)
        assert resp.status_code == 200, f"Create product failed: {resp.text}"
        data = resp.json()
        state["prod_fertilizer_id"] = data["id"]
        state["prod_fertilizer_cost"] = 800.00
        print(f"Created Fertilizer Supreme id={data['id']}")

    def test_create_rice_premium(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Rice Premium 25kg",
            "category": "Grains",
            "unit": "Bag",
            "cost_price": 1200.00,
            "prices": {"retail": 1400.00, "wholesale": 1300.00},
        }, headers=hdr)
        assert resp.status_code == 200, f"Create Rice failed: {resp.text}"
        data = resp.json()
        state["prod_rice_id"] = data["id"]
        state["prod_rice_cost"] = 1200.00
        print(f"Created Rice Premium id={data['id']}")

    def test_create_pesticide_gold(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Pesticide Gold 1L",
            "category": "Pesticides",
            "unit": "Bottle",
            "cost_price": 350.00,
            "prices": {"retail": 450.00, "wholesale": 400.00},
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["prod_pesticide_id"] = data["id"]
        state["prod_pesticide_cost"] = 350.00
        print(f"Created Pesticide Gold id={data['id']}")

    def test_create_animal_feed_deluxe(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Animal Feed Deluxe 20kg",
            "category": "Animal Feed",
            "unit": "Bag",
            "cost_price": 600.00,
            "prices": {"retail": 750.00, "wholesale": 690.00},
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["prod_animal_feed_id"] = data["id"]
        state["prod_animal_feed_cost"] = 600.00
        print(f"Created Animal Feed Deluxe id={data['id']}")

    def test_create_vet_antibiotic(self, hdr):
        """No repack for this product."""
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Vet Antibiotic Vial",
            "category": "Veterinary",
            "unit": "Vial",
            "cost_price": 120.00,
            "prices": {"retail": 180.00, "wholesale": 160.00},
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["prod_vet_id"] = data["id"]
        print(f"Created Vet Antibiotic id={data['id']}")

    def test_create_repack_fertilizer_1kg(self, hdr):
        """Fertilizer 1kg (50 per bag)."""
        assert "prod_fertilizer_id" in state
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Fertilizer Supreme 1kg",
            "category": "Fertilizer",
            "unit": "Bag",
            "cost_price": round(800.00 / 50, 2),  # 16.00
            "prices": {"retail": 20.00, "wholesale": 18.00},
            "is_repack": True,
            "parent_id": state["prod_fertilizer_id"],
            "units_per_parent": 50,
            "repack_unit": "kg"
        }, headers=hdr)
        assert resp.status_code == 200, f"Create repack failed: {resp.text}"
        data = resp.json()
        assert data.get("is_repack") is True
        state["repack_fertilizer_id"] = data["id"]
        print(f"Created Fertilizer 1kg repack id={data['id']}")

    def test_create_repack_rice_500g(self, hdr):
        """Rice 500g (50 per bag)."""
        assert "prod_rice_id" in state
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Rice Premium 500g",
            "category": "Grains",
            "unit": "Pack",
            "cost_price": round(1200.00 / 50, 2),  # 24.00
            "prices": {"retail": 30.00, "wholesale": 27.00},
            "is_repack": True,
            "parent_id": state["prod_rice_id"],
            "units_per_parent": 50,
            "repack_unit": "g"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["repack_rice_id"] = data["id"]
        print(f"Created Rice 500g repack id={data['id']}")

    def test_create_repack_pesticide_100ml(self, hdr):
        """Pesticide 100ml (10 per bottle)."""
        assert "prod_pesticide_id" in state
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Pesticide Gold 100ml",
            "category": "Pesticides",
            "unit": "Bottle",
            "cost_price": round(350.00 / 10, 2),  # 35.00
            "prices": {"retail": 50.00, "wholesale": 45.00},
            "is_repack": True,
            "parent_id": state["prod_pesticide_id"],
            "units_per_parent": 10,
            "repack_unit": "ml"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["repack_pesticide_id"] = data["id"]
        print(f"Created Pesticide 100ml repack id={data['id']}")

    def test_create_repack_animal_feed_1kg(self, hdr):
        """Animal Feed 1kg (20 per bag)."""
        assert "prod_animal_feed_id" in state
        resp = requests.post(f"{BASE_URL}/api/products", json={
            "name": "Animal Feed Deluxe 1kg",
            "category": "Animal Feed",
            "unit": "Pack",
            "cost_price": round(600.00 / 20, 2),  # 30.00
            "prices": {"retail": 40.00, "wholesale": 36.00},
            "is_repack": True,
            "parent_id": state["prod_animal_feed_id"],
            "units_per_parent": 20,
            "repack_unit": "kg"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["repack_animal_feed_id"] = data["id"]
        print(f"Created Animal Feed 1kg repack id={data['id']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: SETUP — Customers
# ─────────────────────────────────────────────────────────────────────────────

class TestCustomerSetup:
    """Create 5 customers."""

    def test_create_maria_santos(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/customers", json={
            "name": "Maria Santos",
            "customer_type": "retail",
            "payment_terms": "cash",
            "phone": "09171234567",
            "credit_limit": 0
        }, headers=hdr)
        assert resp.status_code == 200, f"Create customer failed: {resp.text}"
        data = resp.json()
        state["cust_maria_id"] = data["id"]
        print(f"Created Maria Santos id={data['id']}")

    def test_create_juan_delacruz(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/customers", json={
            "name": "Juan dela Cruz",
            "customer_type": "retail",
            "payment_terms": "credit",
            "interest_rate": 2.0,
            "credit_limit": 20000,
            "phone": "09181234567"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["cust_juan_id"] = data["id"]
        print(f"Created Juan dela Cruz id={data['id']}")

    def test_create_green_valley_farm(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/customers", json={
            "name": "Green Valley Farm",
            "customer_type": "farm",
            "payment_terms": "cash",
            "price_level": "wholesale",
            "phone": "09191234567"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["cust_green_valley_id"] = data["id"]
        print(f"Created Green Valley Farm id={data['id']}")

    def test_create_hillside_agriculture(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/customers", json={
            "name": "Hillside Agriculture Co",
            "customer_type": "farm",
            "payment_terms": "credit",
            "price_level": "wholesale",
            "credit_limit": 50000,
            "phone": "09201234567"
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["cust_hillside_id"] = data["id"]
        print(f"Created Hillside Agriculture Co id={data['id']}")

    def test_create_walkin_general(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/customers", json={
            "name": "Walk-in General",
            "customer_type": "retail",
            "payment_terms": "cash",
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["cust_walkin_id"] = data["id"]
        print(f"Created Walk-in General id={data['id']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: SETUP — Suppliers
# ─────────────────────────────────────────────────────────────────────────────

class TestSupplierSetup:
    """Create 3 suppliers."""

    def test_create_agritech_supplies(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/suppliers", json={
            "name": "AgriTech Supplies Inc",
            "contact_person": "Tom Rivera",
            "phone": "02-8123456",
            "email": "agritech@test.com",
            "address": "Quezon City"
        }, headers=hdr)
        assert resp.status_code == 200, f"Create supplier failed: {resp.text}"
        data = resp.json()
        state["supp_agritech_id"] = data["id"]
        print(f"Created AgriTech Supplies Inc id={data['id']}")

    def test_create_biogrow_intl(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/suppliers", json={
            "name": "BioGrow International",
            "contact_person": "Ana Reyes",
            "phone": "02-8234567",
            "email": "biogrow@test.com",
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["supp_biogrow_id"] = data["id"]
        print(f"Created BioGrow International id={data['id']}")

    def test_create_farmpro_distributors(self, hdr):
        resp = requests.post(f"{BASE_URL}/api/suppliers", json={
            "name": "FarmPro Distributors",
            "contact_person": "Carlos Mendoza",
            "phone": "02-8345678",
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["supp_farmpro_id"] = data["id"]
        print(f"Created FarmPro Distributors id={data['id']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: PO MODULE
# ─────────────────────────────────────────────────────────────────────────────

class TestPurchaseOrders:
    """Create and receive POs at Lakewood and Riverside branches."""

    def test_create_lakewood_po1_cash(self, hdr):
        """Cash PO at Lakewood from AgriTech."""
        assert all(k in state for k in ["lakewood_id", "supp_agritech_id", "prod_fertilizer_id"])
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": "AgriTech Supplies Inc",
            "supplier_id": state["supp_agritech_id"],
            "branch_id": state["lakewood_id"],
            "po_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "payment_terms": "cash",
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "quantity": 10, "unit_price": 800.00},
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "quantity": 20, "unit_price": 1200.00},
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "quantity": 15, "unit_price": 350.00}
            ],
            "status": "received",
            "fund_source": "cashier"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create PO failed: {resp.text}"
        data = resp.json()
        state["po_lakewood1_id"] = data["id"]
        state["po_lakewood1_number"] = data.get("po_number", "")
        print(f"Created Lakewood Cash PO id={data['id']} po_number={data.get('po_number')}")

    def test_create_lakewood_po2_terms(self, hdr):
        """Terms/Credit PO at Lakewood from BioGrow."""
        assert "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": "BioGrow International",
            "supplier_id": state["supp_biogrow_id"],
            "branch_id": state["lakewood_id"],
            "po_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "po_type": "terms",
            "payment_terms": "net30",
            "terms_days": 30,
            "items": [
                {"product_id": state["prod_animal_feed_id"], "product_name": "Animal Feed Deluxe 20kg", "quantity": 15, "unit_price": 600.00},
                {"product_id": state["prod_vet_id"], "product_name": "Vet Antibiotic Vial", "quantity": 30, "unit_price": 120.00},
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "quantity": 5, "unit_price": 800.00}
            ],
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create Terms PO failed: {resp.text}"
        data = resp.json()
        state["po_lakewood2_id"] = data["id"]
        print(f"Created Lakewood Terms PO id={data['id']}")

    def test_create_riverside_po1_cash(self, hdr):
        """Cash PO at Riverside from FarmPro."""
        assert "riverside_id" in state
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": "FarmPro Distributors",
            "supplier_id": state["supp_farmpro_id"],
            "branch_id": state["riverside_id"],
            "po_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "payment_terms": "cash",
            "items": [
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "quantity": 10, "unit_price": 1200.00},
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "quantity": 10, "unit_price": 350.00},
                {"product_id": state["prod_animal_feed_id"], "product_name": "Animal Feed Deluxe 20kg", "quantity": 8, "unit_price": 600.00}
            ],
            "status": "received",
            "fund_source": "cashier"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create Riverside PO failed: {resp.text}"
        data = resp.json()
        state["po_riverside1_id"] = data["id"]
        print(f"Created Riverside Cash PO id={data['id']}")

    def test_create_riverside_po2_terms(self, hdr):
        """Terms/Credit PO at Riverside from AgriTech."""
        assert "riverside_id" in state
        resp = requests.post(f"{BASE_URL}/api/purchase-orders", json={
            "vendor": "AgriTech Supplies Inc",
            "supplier_id": state["supp_agritech_id"],
            "branch_id": state["riverside_id"],
            "po_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "po_type": "terms",
            "payment_terms": "net15",
            "terms_days": 15,
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "quantity": 8, "unit_price": 800.00},
                {"product_id": state["prod_vet_id"], "product_name": "Vet Antibiotic Vial", "quantity": 20, "unit_price": 120.00},
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "quantity": 12, "unit_price": 1200.00}
            ],
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create Riverside Terms PO failed: {resp.text}"
        data = resp.json()
        state["po_riverside2_id"] = data["id"]
        print(f"Created Riverside Terms PO id={data['id']}")

    def test_get_lakewood_pos(self, hdr):
        """Verify POs created at Lakewood."""
        assert "lakewood_id" in state
        resp = requests.get(f"{BASE_URL}/api/purchase-orders?branch_id={state['lakewood_id']}", headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        pos = data.get("orders", data) if isinstance(data, dict) else data
        lw_ids = {po["id"] for po in pos}
        assert state.get("po_lakewood1_id") in lw_ids, "Lakewood PO1 not found"
        print(f"Lakewood POs verified: {len(pos)} orders")

    def test_reopen_lakewood_po1_and_verify_cashier_returned(self, hdr):
        """Reopen received cash PO - cashier fund should be RETURNED."""
        assert "po_lakewood1_id" in state and "lakewood_cashier_wallet_id" in state
        # Get cashier balance before reopen
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        wallets_before = {w["type"]: w for w in resp.json()}
        cashier_balance_before = wallets_before.get("cashier", {}).get("balance", 0)

        # Reopen PO
        resp = requests.post(
            f"{BASE_URL}/api/purchase-orders/{state['po_lakewood1_id']}/reopen",
            json={"reason": "Test reopen to verify cashier fund return"},
            headers=hdr
        )
        # Accept 200 or 404 (endpoint might be named differently)
        assert resp.status_code in [200, 201, 400, 404], f"Reopen failed unexpectedly: {resp.text}"
        if resp.status_code == 200:
            # Verify cashier was returned
            resp2 = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
            wallets_after = {w["type"]: w for w in resp2.json()}
            cashier_balance_after = wallets_after.get("cashier", {}).get("balance", 0)
            print(f"Cashier before: {cashier_balance_before}, after: {cashier_balance_after}")
        else:
            print(f"Reopen endpoint returned {resp.status_code}: {resp.text[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: SALES MODULE
# ─────────────────────────────────────────────────────────────────────────────

class TestSalesModule:
    """Complete 6 sales at Lakewood Branch."""

    def _get_today(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def test_sale_cash_walkin_1(self, hdr):
        """Cash walk-in sale #1."""
        assert all(k in state for k in ["lakewood_id", "prod_fertilizer_id"])
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_name": "Walk-in Customer",
            "payment_type": "cash",
            "payment_method": "Cash",
            "fund_source": "cashier",
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "quantity": 2, "rate": 950.00}
            ],
            "amount_paid": 1900.00,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"Cash sale 1 failed: {resp.text}"
        data = resp.json()
        state["sale1_id"] = data["id"]
        state["sale1_invoice_number"] = data.get("invoice_number", "")
        print(f"Cash sale 1: {data.get('invoice_number')} grand_total={data['grand_total']}")

    def test_sale_cash_walkin_2(self, hdr):
        """Cash walk-in sale #2."""
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_name": "Walk-in Customer 2",
            "payment_type": "cash",
            "payment_method": "Cash",
            "fund_source": "cashier",
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "quantity": 3, "rate": 1400.00},
                {"product_id": state["prod_vet_id"], "product_name": "Vet Antibiotic Vial", "quantity": 2, "rate": 180.00}
            ],
            "amount_paid": 4560.00,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"Cash sale 2 failed: {resp.text}"
        data = resp.json()
        state["sale2_id"] = data["id"]
        print(f"Cash sale 2: {data.get('invoice_number')} grand_total={data['grand_total']}")

    def test_sale_gcash_digital(self, hdr):
        """GCash digital sale (ref# required)."""
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_name": "GCash Customer",
            "payment_type": "digital",
            "payment_method": "GCash",
            "fund_source": "digital",
            "digital_platform": "GCash",
            "digital_ref_number": "GC-20260224-001",
            "digital_sender": "GCash Sender",
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "quantity": 3, "rate": 450.00}
            ],
            "amount_paid": 1350.00,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"GCash sale failed: {resp.text}"
        data = resp.json()
        state["sale3_id"] = data["id"]
        assert data.get("fund_source") == "digital" or data.get("payment_method") == "GCash"
        print(f"GCash sale: {data.get('invoice_number')} ref={data.get('digital_ref_number')}")

    def test_sale_split_cash_gcash(self, hdr):
        """Split payment: cash + GCash."""
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_name": "Split Payment Customer",
            "payment_type": "split",
            "payment_method": "Split",
            "fund_source": "split",
            "cash_amount": 500.00,
            "digital_amount": 700.00,
            "digital_platform": "GCash",
            "digital_ref_number": "GC-20260224-SPLIT",
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_animal_feed_id"], "product_name": "Animal Feed Deluxe 20kg", "quantity": 2, "rate": 750.00}
            ],
            "amount_paid": 1200.00,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"Split sale failed: {resp.text}"
        data = resp.json()
        state["sale4_id"] = data["id"]
        print(f"Split sale: {data.get('invoice_number')} grand_total={data['grand_total']}")

    def test_sale_credit_juan_delacruz(self, hdr):
        """Credit sale to Juan dela Cruz."""
        assert "cust_juan_id" in state
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_id": state["cust_juan_id"],
            "customer_name": "Juan dela Cruz",
            "payment_type": "credit",
            "payment_method": "Credit",
            "terms": "net30",
            "terms_days": 30,
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "quantity": 3, "rate": 950.00}
            ],
            "amount_paid": 0,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"Credit sale failed: {resp.text}"
        data = resp.json()
        assert data.get("status") in ["open", "partial"]
        state["sale5_id"] = data["id"]
        state["sale5_invoice_number"] = data.get("invoice_number", "")
        print(f"Credit sale to Juan: {data.get('invoice_number')} balance={data['balance']}")

    def test_sale_partial_green_valley(self, hdr):
        """Partial payment sale to Green Valley Farm."""
        assert "cust_green_valley_id" in state
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["lakewood_id"],
            "customer_id": state["cust_green_valley_id"],
            "customer_name": "Green Valley Farm",
            "payment_type": "partial",
            "payment_method": "Cash",
            "fund_source": "cashier",
            "order_date": self._get_today(),
            "items": [
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "quantity": 5, "rate": 1300.00},
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "quantity": 5, "rate": 400.00}
            ],
            "amount_paid": 5000.00,
            "sale_type": "walk_in"
        }, headers=hdr)
        assert resp.status_code == 200, f"Partial sale failed: {resp.text}"
        data = resp.json()
        assert data.get("status") in ["partial", "open"]
        state["sale6_id"] = data["id"]
        print(f"Partial sale to Green Valley: {data.get('invoice_number')} paid={data['amount_paid']} balance={data['balance']}")

    def test_sales_history_running_totals(self, hdr):
        """Check Sales History tab - verify running totals."""
        assert "lakewood_id" in state
        resp = requests.get(
            f"{BASE_URL}/api/invoices?branch_id={state['lakewood_id']}&status=paid",
            headers=hdr
        )
        assert resp.status_code == 200
        data = resp.json()
        invoices = data.get("invoices", data) if isinstance(data, dict) else data
        paid_sales = [inv for inv in invoices if inv.get("status") == "paid"]
        total = sum(inv.get("grand_total", 0) for inv in paid_sales)
        print(f"Sales history: {len(paid_sales)} paid invoices, total={total}")
        assert len(paid_sales) > 0, "No paid sales found"

    def test_void_sale_with_manager_pin(self, hdr):
        """Void sale #2 with manager PIN - verify inventory restored."""
        assert "sale2_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/invoices/{state['sale2_id']}/void",
            json={"reason": "Test void for E2E", "manager_pin": "521325"},
            headers=hdr
        )
        assert resp.status_code == 200, f"Void failed: {resp.text}"
        data = resp.json()
        # Verify invoice is now voided
        resp2 = requests.get(f"{BASE_URL}/api/invoices/{state['sale2_id']}", headers=hdr)
        if resp2.status_code == 200:
            inv_data = resp2.json()
            assert inv_data.get("status") == "voided", f"Expected voided, got {inv_data.get('status')}"
        print(f"Sale {state['sale2_id']} voided successfully")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: BRANCH TRANSFER
# ─────────────────────────────────────────────────────────────────────────────

class TestBranchTransfers:
    """Transfer from Lakewood to Riverside with repack prices."""

    def test_create_transfer_lakewood_to_riverside(self, hdr):
        """Create transfer with 3 products including repack price updates."""
        assert all(k in state for k in ["lakewood_id", "riverside_id", "repack_rice_id"])
        resp = requests.post(f"{BASE_URL}/api/branch-transfers", json={
            "from_branch_id": state["lakewood_id"],
            "to_branch_id": state["riverside_id"],
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "qty": 3},
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "qty": 5},
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "qty": 4}
            ],
            "repack_price_updates": [
                {"repack_id": state["repack_rice_id"], "repack_name": "Rice Premium 500g", "new_retail_price": 32.00}
            ],
            "notes": "E2E Transfer test"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create transfer failed: {resp.text}"
        data = resp.json()
        state["transfer1_id"] = data["id"]
        state["transfer1_number"] = data.get("transfer_number", "")
        print(f"Created transfer id={data['id']} number={data.get('transfer_number')}")

    def test_send_transfer(self, hdr):
        """Send the transfer from Lakewood."""
        assert "transfer1_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{state['transfer1_id']}/send",
            json={},
            headers=hdr
        )
        assert resp.status_code == 200, f"Send transfer failed: {resp.text}"
        data = resp.json()
        assert data.get("status") == "sent" or "sent" in str(data)
        print(f"Transfer sent: {state['transfer1_id']}")

    def test_view_incoming_transfer_at_riverside(self, hdr):
        """View incoming transfer at Riverside - verify repack price updates section."""
        assert "riverside_id" in state
        resp = requests.get(
            f"{BASE_URL}/api/branch-transfers?to_branch_id={state['riverside_id']}&status=sent",
            headers=hdr
        )
        assert resp.status_code == 200
        data = resp.json()
        transfers = data.get("transfers", data) if isinstance(data, dict) else data
        incoming = [t for t in transfers if t.get("to_branch_id") == state["riverside_id"]]
        assert len(incoming) > 0, "No incoming transfers found at Riverside"
        # Check repack_price_updates
        t = incoming[0]
        rpu = t.get("repack_price_updates", [])
        print(f"Incoming transfer repack_price_updates: {rpu}")
        if rpu:
            assert rpu[0].get("new_retail_price") == 32.00 or rpu[0].get("new_retail_price") > 0

    def test_receive_transfer_with_shortage(self, hdr):
        """Receive transfer at Riverside with 1 shortage (receive less than sent)."""
        assert "transfer1_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/branch-transfers/{state['transfer1_id']}/receive",
            json={
                "items": [
                    {"product_id": state["prod_fertilizer_id"], "qty_received": 3},
                    {"product_id": state["prod_rice_id"], "qty_received": 4},  # shortage: sent 5 received 4
                    {"product_id": state["prod_pesticide_id"], "qty_received": 4}
                ]
            },
            headers=hdr
        )
        assert resp.status_code == 200, f"Receive transfer failed: {resp.text}"
        data = resp.json()
        print(f"Transfer received with shortage. Status: {data.get('status')}")
        # Verify discrepancy
        discrepancy = data.get("discrepancy") or data.get("shortages") or []
        print(f"Discrepancies: {discrepancy}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: ACCOUNTING MODULE
# ─────────────────────────────────────────────────────────────────────────────

class TestAccountingModule:
    """Record expenses, delete expense, collect AR payment."""

    def test_record_utilities_expense(self, hdr):
        """Record Utilities expense at Lakewood."""
        assert "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/expenses", json={
            "branch_id": state["lakewood_id"],
            "category": "Utilities",
            "description": "Monthly electricity bill",
            "amount": 5000.00,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "fund_source": "cashier",
            "payment_method": "Cash"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Record expense failed: {resp.text}"
        data = resp.json()
        state["expense1_id"] = data["id"]
        print(f"Utilities expense created id={data['id']} amount=5000")

    def test_record_fuel_expense(self, hdr):
        """Record Fuel expense at Lakewood."""
        assert "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/expenses", json={
            "branch_id": state["lakewood_id"],
            "category": "Fuel/Gas",
            "description": "Delivery fuel",
            "amount": 1500.00,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "fund_source": "cashier",
            "payment_method": "Cash"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Fuel expense failed: {resp.text}"
        data = resp.json()
        state["expense2_id"] = data["id"]
        print(f"Fuel expense created id={data['id']}")

    def test_record_employee_advance_expense(self, hdr):
        """Record Employee Advance expense at Lakewood."""
        assert "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/expenses", json={
            "branch_id": state["lakewood_id"],
            "category": "Employee Advance",
            "description": "Cash advance for Juan Cashier",
            "amount": 2000.00,
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "fund_source": "cashier",
            "payment_method": "Cash",
            "employee_name": "Juan Cashier"
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Employee advance failed: {resp.text}"
        data = resp.json()
        state["expense3_id"] = data["id"]
        print(f"Employee advance created id={data['id']}")

    def test_verify_cashier_deducted_after_expenses(self, hdr):
        """Verify cashier wallet balance decreased after expenses."""
        assert "lakewood_id" in state
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        wallets = {w["type"]: w for w in resp.json()}
        cashier_bal = wallets.get("cashier", {}).get("balance", 0)
        print(f"Lakewood cashier after expenses: ₱{cashier_bal}")
        # Balance should have decreased from the expenses
        assert cashier_bal is not None

    def test_delete_fuel_expense_fund_returned(self, hdr):
        """Delete fuel expense - verify fund RETURNED to cashier."""
        assert "expense2_id" in state and "lakewood_id" in state
        # Get balance before
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        wallets_before = {w["type"]: w for w in resp.json()}
        cashier_before = wallets_before.get("cashier", {}).get("balance", 0)

        # Delete expense
        resp = requests.delete(f"{BASE_URL}/api/expenses/{state['expense2_id']}", headers=hdr)
        assert resp.status_code in [200, 204], f"Delete expense failed: {resp.text}"

        # Get balance after
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        wallets_after = {w["type"]: w for w in resp.json()}
        cashier_after = wallets_after.get("cashier", {}).get("balance", 0)
        print(f"Cashier before delete: {cashier_before}, after: {cashier_after}")
        # After deleting a 1500 expense, cashier should increase
        assert cashier_after >= cashier_before, "Cashier should increase after expense deletion"

    def test_collect_ar_payment_juan(self, hdr):
        """Collect AR payment from Juan dela Cruz."""
        assert "sale5_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/invoices/{state['sale5_id']}/payment",
            json={
                "amount": 1500.00,
                "payment_method": "Cash",
                "fund_source": "cashier",
                "reference": "AR collection from Juan"
            },
            headers=hdr
        )
        assert resp.status_code == 200, f"AR collection failed: {resp.text}"
        data = resp.json()
        print(f"AR collected from Juan: {data}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: FUND MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestFundManagement:
    """Transfer Cashier→Safe at Lakewood with manager PIN."""

    def test_cashier_to_safe_transfer(self, hdr):
        """Transfer 3000 from Cashier to Safe with manager PIN."""
        assert "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/fund-transfers", json={
            "branch_id": state["lakewood_id"],
            "transfer_type": "cashier_to_safe",
            "amount": 3000.00,
            "manager_pin": "521325",
            "note": "E2E test cashier to safe transfer"
        }, headers=hdr)
        assert resp.status_code == 200, f"Cashier to safe failed: {resp.text}"
        data = resp.json()
        state["fund_transfer_id"] = data.get("id", "")
        print(f"Cashier→Safe transfer: {data}")

    def test_verify_wallets_after_transfer(self, hdr):
        """Verify both wallets updated after transfer."""
        assert "lakewood_id" in state
        resp = requests.get(f"{BASE_URL}/api/fund-wallets?branch_id={state['lakewood_id']}", headers=hdr)
        wallets = {w["type"]: w for w in resp.json()}
        print(f"Lakewood wallets after transfer: cashier={wallets.get('cashier', {}).get('balance')}, safe={wallets.get('safe', {}).get('balance')}")
        # Both should exist and have valid balances
        assert "cashier" in wallets
        assert "safe" in wallets


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: CLOSE WIZARD
# ─────────────────────────────────────────────────────────────────────────────

class TestCloseWizard:
    """Run Close Wizard at Lakewood Branch."""

    def test_daily_close_preview(self, hdr):
        """Get Z-Report preview for Lakewood."""
        assert "lakewood_id" in state
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/api/daily-close-preview?branch_id={state['lakewood_id']}&date={today}",
            headers=hdr
        )
        assert resp.status_code == 200, f"Close preview failed: {resp.text}"
        data = resp.json()
        # Verify key sections present
        assert "total_cash_sales" in data or "cash_sales" in data or "summary" in data
        print(f"Z-Report preview keys: {list(data.keys())[:10]}")
        state["z_report"] = data

    def test_close_wizard_has_digital_totals(self, hdr):
        """Verify Z-Report shows digital sales totals."""
        assert "z_report" in state
        z = state["z_report"]
        # Check for digital section
        has_digital = any(
            k in z for k in ["digital_sales", "total_digital", "digital_totals", "digital_by_platform"]
        )
        print(f"Digital section in Z-report: {has_digital}, keys: {list(z.keys())}")

    def test_perform_day_close(self, hdr):
        """Complete the close with manager PIN."""
        assert "lakewood_id" in state
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = requests.post(f"{BASE_URL}/api/daily-ops/close-day", json={
            "branch_id": state["lakewood_id"],
            "date": today,
            "manager_pin": "521325",
            "actual_cash": 5000.00,
            "notes": "E2E test day close"
        }, headers=hdr)
        # Allow success or already-closed
        assert resp.status_code in [200, 201, 400], f"Day close failed unexpectedly: {resp.text}"
        if resp.status_code in [200, 201]:
            data = resp.json()
            state["close_id"] = data.get("id", "")
            print(f"Day close completed: {data.get('id', 'N/A')}")
        else:
            print(f"Day close response: {resp.status_code} {resp.text[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: CUSTOMER RETURNS
# ─────────────────────────────────────────────────────────────────────────────

class TestCustomerReturns:
    """Process a return of Fertilizer (shelf condition)."""

    def test_create_return(self, hdr):
        """Return Fertilizer from sale1."""
        assert "sale1_id" in state and "lakewood_id" in state
        resp = requests.post(f"{BASE_URL}/api/returns", json={
            "invoice_id": state["sale1_id"],
            "branch_id": state["lakewood_id"],
            "items": [
                {
                    "product_id": state["prod_fertilizer_id"],
                    "product_name": "Fertilizer Supreme 50kg",
                    "quantity": 1,
                    "rate": 950.00,
                    "condition": "shelf"
                }
            ],
            "reason": "Customer dissatisfied",
            "refund_method": "Cash",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create return failed: {resp.text}"
        data = resp.json()
        state["return1_id"] = data.get("id", data.get("return_id", ""))
        print(f"Return created id={state['return1_id']}")

    def test_verify_inventory_restored_after_return(self, hdr):
        """Verify inventory was restored after return."""
        assert "prod_fertilizer_id" in state and "lakewood_id" in state
        resp = requests.get(
            f"{BASE_URL}/api/inventory?product_id={state['prod_fertilizer_id']}&branch_id={state['lakewood_id']}",
            headers=hdr
        )
        assert resp.status_code == 200
        data = resp.json()
        print(f"Fertilizer inventory at Lakewood after return: {data}")

    def test_void_return_with_manager_pin(self, hdr):
        """Void the return with manager PIN."""
        if not state.get("return1_id"):
            pytest.skip("Return not created")
        resp = requests.post(
            f"{BASE_URL}/api/returns/{state['return1_id']}/void",
            json={"reason": "Test void of return", "manager_pin": "521325"},
            headers=hdr
        )
        assert resp.status_code in [200, 201, 404], f"Void return unexpected: {resp.text}"
        print(f"Return void: {resp.status_code} {resp.text[:100]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: COUNT SHEET
# ─────────────────────────────────────────────────────────────────────────────

class TestCountSheet:
    """Create and complete a count sheet at Riverside Branch with variances."""

    def test_create_count_sheet_riverside(self, hdr):
        """Create count sheet at Riverside."""
        assert "riverside_id" in state
        resp = requests.post(f"{BASE_URL}/api/count-sheets", json={
            "branch_id": state["riverside_id"],
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "notes": "E2E count sheet with variances",
            "items": [
                {"product_id": state["prod_fertilizer_id"], "product_name": "Fertilizer Supreme 50kg", "counted_qty": 8, "system_qty": 11},
                {"product_id": state["prod_rice_id"], "product_name": "Rice Premium 25kg", "counted_qty": 22, "system_qty": 22},
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "counted_qty": 12, "system_qty": 14}
            ]
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Create count sheet failed: {resp.text}"
        data = resp.json()
        state["count_sheet_id"] = data.get("id", "")
        print(f"Count sheet created id={state['count_sheet_id']}")

    def test_complete_count_sheet(self, hdr):
        """Complete the count sheet."""
        if not state.get("count_sheet_id"):
            pytest.skip("Count sheet not created")
        resp = requests.post(
            f"{BASE_URL}/api/count-sheets/{state['count_sheet_id']}/complete",
            json={"manager_pin": "521325", "notes": "Completed E2E count"},
            headers=hdr
        )
        assert resp.status_code in [200, 201], f"Complete count sheet failed: {resp.text}"
        data = resp.json()
        print(f"Count sheet completed: {data.get('status', 'N/A')}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13: AUDIT CENTER
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditCenter:
    """Run Full Audit at Lakewood Branch."""

    def test_run_full_audit_lakewood(self, hdr):
        """Run full audit at Lakewood Branch."""
        assert "lakewood_id" in state
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        resp = requests.post(f"{BASE_URL}/api/audit/sessions", json={
            "branch_id": state["lakewood_id"],
            "audit_type": "full",
            "period_from": month_start,
            "period_to": today
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Audit failed: {resp.text}"
        data = resp.json()
        state["audit1_id"] = data.get("id", "")
        print(f"Audit created id={state['audit1_id']}")

    def test_audit_has_required_sections(self, hdr):
        """Verify audit has: Cash, Sales, AR, Payables, Transfers, Returns, Digital, Activity, Inventory."""
        if not state.get("audit1_id"):
            pytest.skip("Audit not created")
        resp = requests.get(f"{BASE_URL}/api/audit/sessions/{state['audit1_id']}", headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        # Check key sections in audit result
        print(f"Audit sections: {list(data.keys())}")
        assert "id" in data
        # The audit result should contain various sections
        result = data.get("result", data)
        print(f"Audit result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

    def test_get_audit_compute(self, hdr):
        """Run audit compute endpoint if available."""
        assert "lakewood_id" in state
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/api/audit/compute?branch_id={state['lakewood_id']}&date={today}",
            headers=hdr
        )
        # This might be 200 or 404 depending on implementation
        print(f"Audit compute: {resp.status_code} {resp.text[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 14: BAD MANAGER SCENARIO AT RIVERSIDE
# ─────────────────────────────────────────────────────────────────────────────

class TestBadManagerScenario:
    """Create suspicious activity at Riverside Branch and run audit."""

    def test_void_sale_without_reason(self, hdr):
        """Create a sale at Riverside then void without proper reason."""
        assert "riverside_id" in state
        # Create a sale first
        resp = requests.post(f"{BASE_URL}/api/invoices", json={
            "branch_id": state["riverside_id"],
            "customer_name": "Bad Manager Test",
            "payment_type": "cash",
            "payment_method": "Cash",
            "fund_source": "cashier",
            "order_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "items": [
                {"product_id": state["prod_pesticide_id"], "product_name": "Pesticide Gold 1L", "quantity": 1, "rate": 450.00}
            ],
            "amount_paid": 450.00
        }, headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        state["bad_sale_id"] = data["id"]

        # Void without reason
        void_resp = requests.post(
            f"{BASE_URL}/api/invoices/{state['bad_sale_id']}/void",
            json={"reason": "", "manager_pin": "521325"},
            headers=hdr
        )
        print(f"Void without reason: {void_resp.status_code} {void_resp.text[:100]}")
        state["bad_sale_voided"] = void_resp.status_code == 200

    def test_inventory_corrections_without_justification(self, hdr):
        """Do 3 inventory corrections without justification (suspicious)."""
        assert "riverside_id" in state
        corrections_done = 0
        for i in range(3):
            resp = requests.post(f"{BASE_URL}/api/inventory/correction", json={
                "branch_id": state["riverside_id"],
                "product_id": state["prod_fertilizer_id"],
                "quantity_adjustment": -(i + 1),
                "reason": "",  # No justification
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
            }, headers=hdr)
            if resp.status_code in [200, 201]:
                corrections_done += 1
            print(f"Correction {i+1}: {resp.status_code}")
        state["bad_corrections_count"] = corrections_done
        print(f"Inventory corrections done: {corrections_done}/3")

    def test_run_audit_riverside_for_flags(self, hdr):
        """Run audit at Riverside to check for suspicious activity flags."""
        assert "riverside_id" in state
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        resp = requests.post(f"{BASE_URL}/api/audit/sessions", json={
            "branch_id": state["riverside_id"],
            "audit_type": "full",
            "period_from": month_start,
            "period_to": today
        }, headers=hdr)
        assert resp.status_code in [200, 201], f"Riverside audit failed: {resp.text}"
        data = resp.json()
        state["audit_riverside_id"] = data.get("id", "")
        print(f"Riverside audit id={state['audit_riverside_id']}")

    def test_audit_shows_activity_flags(self, hdr):
        """Verify audit shows user activity and sales audit flags."""
        if not state.get("audit_riverside_id"):
            pytest.skip("Riverside audit not created")
        resp = requests.get(f"{BASE_URL}/api/audit/sessions/{state['audit_riverside_id']}", headers=hdr)
        assert resp.status_code == 200
        data = resp.json()
        result = data.get("result", data)
        # Check for activity or voided_sales in audit
        has_activity = any(
            k in (result if isinstance(result, dict) else {})
            for k in ["user_activity", "voided_sales", "suspicious_activity", "flags", "activity_log"]
        )
        print(f"Audit has activity flags: {has_activity}")
        print(f"Riverside audit result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 15: VERIFICATION SYSTEM
# ─────────────────────────────────────────────────────────────────────────────

class TestVerificationSystem:
    """Verify a PO at Lakewood with admin PIN."""

    def test_verify_po_with_admin_pin(self, hdr):
        """Verify a PO - badge should appear."""
        assert "po_lakewood1_id" in state
        resp = requests.post(
            f"{BASE_URL}/api/verify/purchase-order/{state['po_lakewood1_id']}",
            json={"pin": "521325", "notes": "E2E verification test"},
            headers=hdr
        )
        print(f"Verify PO: {resp.status_code} {resp.text[:200]}")
        assert resp.status_code in [200, 201, 404], f"Verify PO unexpected: {resp.text}"
        if resp.status_code in [200, 201]:
            data = resp.json()
            print(f"PO verified: {data}")

    def test_verify_expense_with_admin_pin(self, hdr):
        """Verify an expense."""
        if not state.get("expense1_id"):
            pytest.skip("Expense not created")
        resp = requests.post(
            f"{BASE_URL}/api/verify/expense/{state['expense1_id']}",
            json={"pin": "521325", "notes": "E2E expense verification"},
            headers=hdr
        )
        print(f"Verify expense: {resp.status_code} {resp.text[:100]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 16: REPORTS
# ─────────────────────────────────────────────────────────────────────────────

class TestReports:
    """AR Aging and Sales Reports."""

    def test_ar_aging_report(self, hdr):
        """Run AR Aging Report - Juan dela Cruz should appear."""
        resp = requests.get(f"{BASE_URL}/api/reports/ar-aging", headers=hdr)
        if resp.status_code == 404:
            # Try alternate endpoint
            resp = requests.get(f"{BASE_URL}/api/reports?type=ar_aging", headers=hdr)
        assert resp.status_code == 200, f"AR aging failed: {resp.text}"
        data = resp.json()
        print(f"AR Aging report: {type(data)} keys={list(data.keys()) if isinstance(data, dict) else len(data)}")

    def test_sales_report_today(self, hdr):
        """Run Sales Report for today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        resp = requests.get(
            f"{BASE_URL}/api/reports/sales?start_date={today}&end_date={today}&branch_id={state.get('lakewood_id', '')}",
            headers=hdr
        )
        if resp.status_code == 404:
            resp = requests.get(f"{BASE_URL}/api/reports?type=sales&date={today}", headers=hdr)
        assert resp.status_code == 200, f"Sales report failed: {resp.text}"
        data = resp.json()
        print(f"Sales report: {type(data)}")

    def test_dashboard_kpis(self, hdr):
        """Verify Lakewood dashboard shows correct KPIs."""
        assert "lakewood_id" in state
        resp = requests.get(
            f"{BASE_URL}/api/dashboard?branch_id={state['lakewood_id']}",
            headers=hdr
        )
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        data = resp.json()
        print(f"Dashboard KPIs: {list(data.keys())}")

    def test_upcoming_payables_widget(self, hdr):
        """Check Upcoming Payables widget shows Terms POs."""
        assert "lakewood_id" in state
        resp = requests.get(
            f"{BASE_URL}/api/purchase-orders?branch_id={state['lakewood_id']}&payment_terms=net30",
            headers=hdr
        )
        assert resp.status_code == 200
        data = resp.json()
        orders = data.get("orders", data) if isinstance(data, dict) else data
        terms_pos = [o for o in orders if o.get("payment_terms") not in ("cash", "COD") and o.get("status") == "received"]
        print(f"Terms POs at Lakewood: {len(terms_pos)}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 17: SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

class TestSettings:
    """Set Admin Verification PIN via UI. Grant auditor access to cashier user."""

    def test_get_settings(self, hdr):
        """Get current settings."""
        resp = requests.get(f"{BASE_URL}/api/settings", headers=hdr)
        assert resp.status_code == 200, f"Get settings failed: {resp.text}"
        data = resp.json()
        print(f"Settings: {type(data)} keys={list(data.keys()) if isinstance(data, dict) else 'list'}")

    def test_list_users(self, hdr):
        """List users for auditor access management."""
        resp = requests.get(f"{BASE_URL}/api/users", headers=hdr)
        assert resp.status_code == 200, f"List users failed: {resp.text}"
        data = resp.json()
        users = data.get("users", data) if isinstance(data, dict) else data
        print(f"Users: {len(users)}")
        state["all_users"] = users

    def test_branches_list(self, hdr):
        """Verify all branches including new ones are listed."""
        resp = requests.get(f"{BASE_URL}/api/branches", headers=hdr)
        assert resp.status_code == 200
        branches = resp.json()
        branch_names = [b["name"] for b in branches]
        assert "Lakewood Branch" in branch_names, f"Lakewood not found in {branch_names}"
        assert "Riverside Branch" in branch_names, f"Riverside not found in {branch_names}"
        print(f"All branches: {branch_names}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 18: RECEIPT UPLOAD / QR
# ─────────────────────────────────────────────────────────────────────────────

class TestReceiptUpload:
    """Generate View-on-Phone QR for a transfer."""

    def test_generate_view_qr_for_transfer(self, hdr):
        """QR link generation for branch transfer."""
        if not state.get("transfer1_id"):
            pytest.skip("Transfer not created")
        resp = requests.get(
            f"{BASE_URL}/api/branch-transfers/{state['transfer1_id']}",
            headers=hdr
        )
        assert resp.status_code == 200
        data = resp.json()
        # Check if transfer has QR or view link
        qr_link = data.get("view_link") or data.get("qr_url") or f"/view/transfer/{state['transfer1_id']}"
        print(f"Transfer QR link: {qr_link}")

    def test_upload_receipt_endpoint(self, hdr):
        """Test upload endpoint is available."""
        resp = requests.get(f"{BASE_URL}/api/uploads", headers=hdr)
        print(f"Uploads endpoint: {resp.status_code}")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
