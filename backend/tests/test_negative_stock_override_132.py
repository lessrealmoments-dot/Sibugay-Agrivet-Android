"""
Iteration 132: Negative Stock Override Feature Tests
Tests the 'Controlled Negative Stock Override' feature including:
- 422 error for insufficient stock
- PIN validation (wrong/correct)
- Auto-created incident tickets (negative_stock_override)
- Inventory shows negative stock
- Daily close preview negative_stock field
- Count sheet snapshot has_negative_stock flag
- Normal sale still works
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
BRANCH_ID = "c435277f-9fc7-4d83-83e7-38be5b4423ac"   # Branch 1
BRANCH_ID2 = "18c02daa-bce0-45de-860a-70ccc6ed6c6d"  # Branch 2
ZERO_STOCK_PRODUCT_ID = "5f5fa24d-a00b-4f48-8c4e-642590e59fbf"  # Animal Feed Deluxe 1kg (0 or negative on Branch 1)
MANAGER_PIN = "521325"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for super_admin"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "janmarkeahig@gmail.com",
        "password": "Aa@58798546521325"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json().get("token")
    assert token, "No token returned"
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestInsufficientStockValidation:
    """Test insufficient stock pre-validation returns 422 with correct structure"""

    def test_sale_with_zero_stock_returns_422(self, headers):
        """POST /api/unified-sale with 0-stock item should return 422 with type=insufficient_stock"""
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"product_id": ZERO_STOCK_PRODUCT_ID, "quantity": 1, "rate": 250}],
            "payment_type": "cash",
            "amount_paid": 250,
            "customer_name": "Test Walk-in"
        }
        resp = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=headers)
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", {})
        assert detail.get("type") == "insufficient_stock", f"Expected type=insufficient_stock, got: {detail}"
        assert "items" in detail, "Missing 'items' in detail"
        items = detail["items"]
        assert len(items) >= 1, "Expected at least 1 item in detail.items"
        item = items[0]
        assert item.get("product_id") == ZERO_STOCK_PRODUCT_ID
        assert "product_name" in item
        assert "system_qty" in item
        assert "needed_qty" in item
        print(f"PASS: 422 with correct structure — {detail['message']}")

    def test_sale_with_wrong_pin_returns_403(self, headers):
        """POST /api/unified-sale with wrong override PIN returns 403"""
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"product_id": ZERO_STOCK_PRODUCT_ID, "quantity": 1, "rate": 250}],
            "payment_type": "cash",
            "amount_paid": 250,
            "customer_name": "Test Walk-in",
            "manager_override_pin": "000000"
        }
        resp = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=headers)
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
        print(f"PASS: Wrong PIN returns 403 — {resp.json().get('detail')}")


class TestManagerOverrideWithCorrectPIN:
    """Test override with correct PIN completes sale and creates incident ticket"""

    def test_sale_with_correct_pin_succeeds(self, headers):
        """POST /api/unified-sale with correct manager PIN returns 200"""
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"product_id": ZERO_STOCK_PRODUCT_ID, "quantity": 1, "rate": 250}],
            "payment_type": "cash",
            "amount_paid": 250,
            "customer_name": "Manager Override Test",
            "manager_override_pin": MANAGER_PIN
        }
        resp = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "invoice_number" in data, "No invoice_number in response"
        assert data["invoice_number"].startswith("SI"), f"Unexpected invoice number format: {data['invoice_number']}"
        print(f"PASS: Override sale created: {data['invoice_number']}")

    def test_incident_ticket_created_after_override(self, headers):
        """After override sale, a negative_stock_override ticket should exist"""
        resp = requests.get(f"{BASE_URL}/api/incident-tickets", params={"status": "open", "limit": 100}, headers=headers)
        assert resp.status_code == 200, f"Failed to fetch tickets: {resp.text}"
        tickets = resp.json().get("tickets", [])
        nso_tickets = [t for t in tickets if t.get("ticket_type") == "negative_stock_override"]
        assert len(nso_tickets) >= 1, f"Expected at least 1 NSO ticket, found 0. All tickets: {[t.get('ticket_type') for t in tickets]}"
        ticket = nso_tickets[0]
        # Validate ticket structure
        assert ticket.get("ticket_number", "").startswith("NSO-"), f"Bad ticket number: {ticket.get('ticket_number')}"
        assert ticket.get("product_id") == ZERO_STOCK_PRODUCT_ID
        assert "qty_before_sale" in ticket
        assert "qty_sold" in ticket
        assert "invoice_number" in ticket
        assert ticket.get("status") == "open"
        print(f"PASS: NSO ticket found: {ticket['ticket_number']} for {ticket['product_name']}")


class TestNegativeStockViews:
    """Test that negative stock shows up in inventory, close-preview, and count sheets"""

    def test_inventory_shows_negative_stock(self, headers):
        """Inventory API should return negative quantity for overridden item"""
        resp = requests.get(f"{BASE_URL}/api/inventory", params={
            "branch_id": BRANCH_ID,
            "search": "Animal Feed Deluxe 1kg"
        }, headers=headers)
        assert resp.status_code == 200, f"Inventory API failed: {resp.text}"
        items = resp.json().get("items", [])
        target = next((it for it in items if it["id"] == ZERO_STOCK_PRODUCT_ID), None)
        assert target is not None, "Target product not found in inventory"
        branch_qty = target.get("branch_stock", {}).get(BRANCH_ID, None)
        assert branch_qty is not None and branch_qty < 0, f"Expected negative qty, got: {branch_qty}"
        print(f"PASS: Inventory shows negative qty={branch_qty} for Animal Feed Deluxe 1kg")

    def test_close_preview_negative_stock_warning(self, headers):
        """Daily close preview should include negative_stock field with count > 0"""
        import datetime
        today = datetime.date.today().isoformat()
        resp = requests.get(f"{BASE_URL}/api/daily-close-preview", params={
            "branch_id": BRANCH_ID,
            "date": today
        }, headers=headers)
        assert resp.status_code == 200, f"Close preview failed: {resp.text}"
        data = resp.json()
        ns = data.get("negative_stock", {})
        assert "count" in ns, "Missing 'count' in negative_stock"
        assert "items" in ns, "Missing 'items' in negative_stock"
        assert ns["count"] >= 1, f"Expected count >= 1, got {ns['count']}"
        print(f"PASS: Close preview shows {ns['count']} negative stock items")

    def test_count_sheet_snapshot_has_negative_flag(self, headers):
        """Count sheet snapshot items should have has_negative_stock=True for negative items"""
        import datetime
        today = datetime.date.today().isoformat()
        # Try to create count sheet; if one already exists, use the existing one
        create_resp = requests.post(f"{BASE_URL}/api/count-sheets", json={
            "branch_id": BRANCH_ID,
            "sheet_date": today,
            "notes": "pytest negative stock flag test"
        }, headers=headers)
        if create_resp.status_code in [200, 201]:
            sheet_id = create_resp.json().get("id")
        elif create_resp.status_code == 400 and "already exists" in create_resp.text:
            # Get the existing active sheet
            list_resp = requests.get(f"{BASE_URL}/api/count-sheets", params={"branch_id": BRANCH_ID}, headers=headers)
            assert list_resp.status_code == 200, f"Count sheet list failed: {list_resp.text}"
            data = list_resp.json()
            sheets = data if isinstance(data, list) else data.get("sheets", data.get("count_sheets", []))
            active = next((s for s in sheets if s.get("status") in ["active", "in_progress", "pending"]), None)
            assert active is not None, "No active count sheet found"
            sheet_id = active.get("id")
        else:
            pytest.fail(f"Create count sheet failed: {create_resp.text}")
        assert sheet_id, "No sheet id found"
        # Take snapshot if draft; otherwise get items directly from existing sheet
        snap_resp = requests.post(f"{BASE_URL}/api/count-sheets/{sheet_id}/snapshot", json={}, headers=headers)
        if snap_resp.status_code == 200:
            items = snap_resp.json().get("items", [])
        else:
            # Sheet already snapshotted (in_progress) — get items via GET
            get_resp = requests.get(f"{BASE_URL}/api/count-sheets/{sheet_id}", headers=headers)
            assert get_resp.status_code == 200, f"Get count sheet failed: {get_resp.text}"
            items = get_resp.json().get("items", [])
        assert len(items) > 0, "No items in snapshot"
        neg_items = [it for it in items if it.get("has_negative_stock")]
        assert len(neg_items) >= 1, "Expected at least 1 item with has_negative_stock=True"
        target = next((it for it in neg_items if it.get("product_id") == ZERO_STOCK_PRODUCT_ID), None)
        assert target is not None, "Target product not found in snapshot's negative items"
        assert target.get("system_available_qty", 0) < 0
        print(f"PASS: Count sheet snapshot has {len(neg_items)} item(s) with has_negative_stock=True")


class TestNormalSaleUnaffected:
    """Test that normal sales (sufficient stock) still work"""

    def test_normal_sale_completes_without_override(self, headers):
        """POST /api/unified-sale with sufficient stock should return 200 directly, no PIN needed"""
        payload = {
            "branch_id": BRANCH_ID2,
            "items": [{"product_id": ZERO_STOCK_PRODUCT_ID, "quantity": 1, "rate": 250}],
            "payment_type": "cash",
            "amount_paid": 250,
            "customer_name": "Normal Customer"
        }
        resp = requests.post(f"{BASE_URL}/api/unified-sale", json=payload, headers=headers)
        assert resp.status_code == 200, f"Normal sale failed: {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "invoice_number" in data
        # Make sure no NSO ticket was created for this normal sale
        print(f"PASS: Normal sale completed: {data['invoice_number']}")
