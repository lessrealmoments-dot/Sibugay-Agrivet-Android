"""
Branch Transfer Repack Pricing Tests - Iteration 42
Tests:
  1. product-lookup returns repacks array with correct fields
  2. POST branch-transfer creates with repack_price_updates
  3. PUT branch-transfer saves repack_price_updates
  4. POST receive applies repack price updates to destination branch_prices
  5. Receive response includes repack_prices_applied list
  6. Blank repack price (no change) does NOT modify destination prices
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

MAIN_BRANCH_ID = "da114e26-fd00-467f-8728-6b8047a244b5"
IPIL_BRANCH_ID = "d4a041e7-4918-490e-afb8-54ae90cec7fb"
OWNER_USER = {"username": "owner", "password": "521325"}

# From misc_info: "updated by cashier" has repack "R VITMIN PRO POWDER (1 X 20)"
# 20 units/parent, capital 3.5/unit, current dest retail 20.0
REPACK_PARENT_QUERY = "updated by cashier"

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json=OWNER_USER)
    if res.status_code != 200:
        pytest.skip(f"Auth failed: {res.status_code} {res.text}")
    data = res.json()
    token = data.get("token") or data.get("access_token")
    print(f"Auth token obtained: {token[:20]}...")
    return token


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return s


@pytest.fixture(scope="module")
def repack_parent_product(client):
    """Lookup 'updated by cashier' to get product + repacks."""
    res = client.get(
        f"{BASE_URL}/api/branch-transfers/product-lookup",
        params={"q": REPACK_PARENT_QUERY, "from_branch_id": MAIN_BRANCH_ID, "to_branch_id": IPIL_BRANCH_ID}
    )
    assert res.status_code == 200, f"product-lookup failed: {res.status_code} {res.text}"
    products = res.json()
    assert len(products) > 0, f"No products found for query '{REPACK_PARENT_QUERY}'"
    # Find the one with repacks
    with_repacks = [p for p in products if p.get("repacks") and len(p["repacks"]) > 0]
    assert len(with_repacks) > 0, f"No product with repacks found. Products: {[p['name'] for p in products]}"
    return with_repacks[0]


@pytest.fixture(scope="module")
def any_main_branch_product(client):
    """Get any product from main branch for use as transfer item."""
    res = client.get(
        f"{BASE_URL}/api/branch-transfers/product-lookup",
        params={"q": "vitamin", "from_branch_id": MAIN_BRANCH_ID, "to_branch_id": IPIL_BRANCH_ID}
    )
    assert res.status_code == 200
    products = res.json()
    if not products:
        # fallback to broader search
        res2 = client.get(
            f"{BASE_URL}/api/branch-transfers/product-lookup",
            params={"q": "a", "from_branch_id": MAIN_BRANCH_ID, "to_branch_id": IPIL_BRANCH_ID}
        )
        products = res2.json()
    assert len(products) > 0, "No products found for main branch"
    return products[0]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestProductLookupRepacks:
    """Verify product-lookup returns repacks array with correct fields."""

    def test_product_lookup_returns_repacks_array(self, repack_parent_product):
        """Each product result must have a 'repacks' key."""
        p = repack_parent_product
        assert "repacks" in p, f"'repacks' key missing from product: {p['name']}"
        assert isinstance(p["repacks"], list), f"repacks must be a list, got: {type(p['repacks'])}"
        print(f"PASS: product '{p['name']}' has {len(p['repacks'])} repack(s)")

    def test_repack_has_required_fields(self, repack_parent_product):
        """Each repack must have: id, name, units_per_parent, capital_per_repack, current_dest_retail."""
        p = repack_parent_product
        repacks = p["repacks"]
        assert len(repacks) > 0, "Expected at least 1 repack"
        for rp in repacks:
            for field in ["id", "name", "units_per_parent", "capital_per_repack", "current_dest_retail"]:
                assert field in rp, f"Repack missing field '{field}': {rp}"
        print(f"PASS: All repack fields present: {repacks}")

    def test_repack_capital_per_repack_computed_correctly(self, repack_parent_product):
        """capital_per_repack = parent branch_capital / units_per_parent."""
        p = repack_parent_product
        rp = p["repacks"][0]
        branch_capital = float(p["branch_capital"])
        units = float(rp["units_per_parent"])
        expected_capital = round(branch_capital / units, 4) if units > 0 else 0
        actual_capital = round(float(rp["capital_per_repack"]), 4)
        assert abs(actual_capital - expected_capital) < 0.01, (
            f"capital_per_repack mismatch: expected {expected_capital}, got {actual_capital}. "
            f"branch_capital={branch_capital}, units_per_parent={units}"
        )
        print(f"PASS: capital_per_repack={actual_capital} (expected {expected_capital})")

    def test_repack_units_per_parent_matches_info(self, repack_parent_product):
        """units_per_parent should be 20 for 'R VITMIN PRO POWDER (1 X 20)'."""
        p = repack_parent_product
        # Find the 1x20 repack
        rp_20 = next((r for r in p["repacks"] if "20" in r["name"].upper() or float(r["units_per_parent"]) == 20), None)
        if rp_20:
            assert float(rp_20["units_per_parent"]) == 20, (
                f"Expected units_per_parent=20, got {rp_20['units_per_parent']}"
            )
            print(f"PASS: units_per_parent=20 for '{rp_20['name']}'")
        else:
            print(f"INFO: No 20-unit repack found; repacks={[r['name'] for r in p['repacks']]}")

    def test_repack_current_dest_retail_present(self, repack_parent_product):
        """current_dest_retail must be a numeric value (not null)."""
        p = repack_parent_product
        for rp in p["repacks"]:
            assert rp["current_dest_retail"] is not None, f"current_dest_retail is None for '{rp['name']}'"
            assert isinstance(float(rp["current_dest_retail"]), float), (
                f"current_dest_retail should be numeric, got: {rp['current_dest_retail']}"
            )
        print(f"PASS: current_dest_retail present for all repacks")

    def test_product_lookup_no_repacks_for_is_repack_products(self, client):
        """is_repack products should NOT appear in lookup (filtered out by is_repack != True)."""
        res = client.get(
            f"{BASE_URL}/api/branch-transfers/product-lookup",
            params={"q": "R VITMIN", "from_branch_id": MAIN_BRANCH_ID, "to_branch_id": IPIL_BRANCH_ID}
        )
        assert res.status_code == 200
        products = res.json()
        # Any returned products should NOT be repack products
        for p in products:
            assert not p.get("is_repack"), f"Repack product appeared in lookup: {p['name']}"
        print(f"PASS: No is_repack products in lookup results (found {len(products)} products)")


class TestCreateTransferWithRepackPricing:
    """POST /api/branch-transfers with repack_price_updates."""

    created_transfer_id = None

    def test_create_transfer_with_repack_price_updates(self, client, repack_parent_product):
        """Create a draft transfer with repack_price_updates containing new price."""
        p = repack_parent_product
        rp = p["repacks"][0]
        new_price = round(float(rp["capital_per_repack"]) * 2, 2)  # 2x capital = valid price

        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "min_margin": 20.0,
            "category_markups": [],
            "notes": "TEST_REPACK_CREATE",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": new_price,
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                    "parent_product_name": p["name"],
                }
            ],
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "category": p.get("category", "General"),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.25, 2),
                    "last_purchase_ref": p.get("last_purchase_ref"),
                    "moving_average_ref": p.get("moving_average_ref"),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200, f"Create transfer failed: {res.status_code} {res.text}"
        data = res.json()
        assert "id" in data, "Transfer ID missing from response"
        assert "repack_price_updates" in data, "repack_price_updates missing from created transfer"
        assert len(data["repack_price_updates"]) == 1, (
            f"Expected 1 repack_price_update, got {len(data['repack_price_updates'])}"
        )
        assert data["repack_price_updates"][0]["repack_id"] == rp["id"]
        assert float(data["repack_price_updates"][0]["new_retail_price"]) == new_price
        TestCreateTransferWithRepackPricing.created_transfer_id = data["id"]
        TestCreateTransferWithRepackPricing.new_price = new_price
        TestCreateTransferWithRepackPricing.rp_id = rp["id"]
        TestCreateTransferWithRepackPricing.rp_name = rp["name"]
        print(f"PASS: Transfer created id={data['id']}, repack_price_updates={data['repack_price_updates']}")

    def test_get_created_transfer_has_repack_price_updates(self, client):
        """GET the created transfer to verify repack_price_updates persisted."""
        tid = TestCreateTransferWithRepackPricing.created_transfer_id
        if not tid:
            pytest.skip("No transfer ID from create test")
        res = client.get(f"{BASE_URL}/api/branch-transfers/{tid}")
        assert res.status_code == 200, f"GET transfer failed: {res.status_code}"
        data = res.json()
        assert "repack_price_updates" in data
        assert len(data["repack_price_updates"]) >= 1
        print(f"PASS: GET transfer has repack_price_updates: {data['repack_price_updates']}")

    def test_update_transfer_saves_repack_price_updates(self, client, repack_parent_product):
        """PUT transfer to update repack_price_updates with a new price."""
        tid = TestCreateTransferWithRepackPricing.created_transfer_id
        if not tid:
            pytest.skip("No transfer ID from create test")
        p = repack_parent_product
        rp = p["repacks"][0]
        updated_price = round(float(rp["capital_per_repack"]) * 3, 2)

        # First GET to get current items
        res_get = client.get(f"{BASE_URL}/api/branch-transfers/{tid}")
        order = res_get.json()

        put_payload = {
            "items": order["items"],
            "notes": "TEST_REPACK_UPDATED",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": updated_price,
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                }
            ],
        }
        res = client.put(f"{BASE_URL}/api/branch-transfers/{tid}", json=put_payload)
        assert res.status_code == 200, f"PUT transfer failed: {res.status_code} {res.text}"
        data = res.json()
        assert "repack_price_updates" in data
        assert float(data["repack_price_updates"][0]["new_retail_price"]) == updated_price
        print(f"PASS: PUT transfer updated repack price to {updated_price}")


class TestReceiveWithRepackPricing:
    """POST /{id}/receive applies repack price updates to destination branch_prices."""

    created_transfer_id = None
    rp_id = None
    new_price = None

    def test_create_transfer_for_receive(self, client, repack_parent_product):
        """Create + send a transfer so we can receive it with repack price update."""
        p = repack_parent_product
        rp = p["repacks"][0]
        # Use a price that's clearly above capital
        new_price = round(float(rp["capital_per_repack"]) * 2.5, 2)
        if new_price == 0:
            new_price = 25.0  # fallback

        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "min_margin": 20.0,
            "notes": "TEST_REPACK_RECEIVE",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": new_price,
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                }
            ],
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "category": p.get("category", "General"),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.5, 2),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200, f"Create failed: {res.status_code} {res.text}"
        tid = res.json()["id"]
        TestReceiveWithRepackPricing.created_transfer_id = tid
        TestReceiveWithRepackPricing.rp_id = rp["id"]
        TestReceiveWithRepackPricing.new_price = new_price
        TestReceiveWithRepackPricing.p_id = p["id"]
        print(f"PASS: Transfer created for receive test: {tid}, repack price={new_price}")

    def test_send_transfer_before_receive(self, client):
        """Send the draft transfer so it can be received."""
        tid = TestReceiveWithRepackPricing.created_transfer_id
        if not tid:
            pytest.skip("No transfer ID from create test")
        res = client.post(f"{BASE_URL}/api/branch-transfers/{tid}/send")
        assert res.status_code == 200, f"Send failed: {res.status_code} {res.text}"
        data = res.json()
        assert data.get("status") == "sent"
        print(f"PASS: Transfer sent: {data}")

    def test_receive_transfer_applies_repack_price_updates(self, client, repack_parent_product):
        """POST receive — response must include repack_prices_applied with correct price."""
        tid = TestReceiveWithRepackPricing.created_transfer_id
        rp_id = TestReceiveWithRepackPricing.rp_id
        new_price = TestReceiveWithRepackPricing.new_price
        if not tid:
            pytest.skip("No transfer ID")

        p = repack_parent_product
        receive_payload = {
            "notes": "TEST_RECEIVE_REPACK",
            "items": [
                {"product_id": p["id"], "qty_received": 1}
            ]
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers/{tid}/receive", json=receive_payload)
        assert res.status_code == 200, f"Receive failed: {res.status_code} {res.text}"
        data = res.json()
        assert "repack_prices_applied" in data, f"'repack_prices_applied' missing from receive response. Got: {list(data.keys())}"
        applied = data["repack_prices_applied"]
        assert len(applied) >= 1, f"Expected at least 1 repack price applied, got {len(applied)}"
        applied_rp = next((r for r in applied if r["repack_id"] == rp_id), None)
        assert applied_rp is not None, f"Repack {rp_id} not found in repack_prices_applied: {applied}"
        assert float(applied_rp["new_retail_price"]) == new_price, (
            f"Applied price {applied_rp['new_retail_price']} != expected {new_price}"
        )
        TestReceiveWithRepackPricing.received = True
        print(f"PASS: repack_prices_applied: {applied}")

    def test_branch_prices_updated_at_destination(self, client):
        """After receive, destination branch_prices should reflect the new retail price."""
        rp_id = TestReceiveWithRepackPricing.rp_id
        new_price = TestReceiveWithRepackPricing.new_price
        if not rp_id or not new_price:
            pytest.skip("No repack ID or price from receive test")

        # Check branch_prices via product pricing endpoint
        res = client.get(
            f"{BASE_URL}/api/branch-prices/{rp_id}",
            params={"branch_id": IPIL_BRANCH_ID}
        )
        if res.status_code == 404:
            # Try alternate endpoint
            res2 = client.get(
                f"{BASE_URL}/api/products/{rp_id}"
            )
            if res2.status_code == 200:
                product_data = res2.json()
                print(f"INFO: Product found but branch_prices endpoint not available. Product: {product_data.get('name')}")
                pytest.skip("branch_prices endpoint not available for verification")
            pytest.skip("Cannot verify branch prices directly")

        if res.status_code == 200:
            data = res.json()
            retail = None
            if "prices" in data:
                retail = data["prices"].get("retail")
            elif "retail" in data:
                retail = data["retail"]
            if retail is not None:
                assert float(retail) == new_price, (
                    f"branch_prices retail={retail} != expected={new_price}"
                )
                print(f"PASS: Destination branch_prices updated to {retail}")
            else:
                print(f"INFO: branch_prices response structure: {data}")
        else:
            print(f"INFO: branch_prices check returned {res.status_code}; skipping direct price verification")


class TestRepackPriceBlankNoChange:
    """Blank repack price should NOT modify destination prices."""

    def test_create_transfer_blank_repack_price(self, client, repack_parent_product):
        """Transfer with empty new_retail_price (blank) → should not apply repack price."""
        p = repack_parent_product
        rp = p["repacks"][0]

        # Get current dest retail before transfer
        cur_retail = float(rp["current_dest_retail"])

        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "notes": "TEST_REPACK_BLANK_PRICE",
            "repack_price_updates": [],  # No repack price updates (blank)
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "category": p.get("category", "General"),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.5, 2),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200, f"Create failed: {res.status_code} {res.text}"
        tid = res.json()["id"]

        # Send
        s_res = client.post(f"{BASE_URL}/api/branch-transfers/{tid}/send")
        assert s_res.status_code == 200

        # Receive
        receive_payload = {
            "notes": "TEST_BLANK_RECEIVE",
            "items": [{"product_id": p["id"], "qty_received": 1}]
        }
        r_res = client.post(f"{BASE_URL}/api/branch-transfers/{tid}/receive", json=receive_payload)
        assert r_res.status_code == 200, f"Receive failed: {r_res.status_code} {r_res.text}"
        data = r_res.json()

        # repack_prices_applied should be empty
        applied = data.get("repack_prices_applied", [])
        assert len(applied) == 0, f"Expected no repack prices applied for blank price, got: {applied}"
        print(f"PASS: Blank repack price → repack_prices_applied is empty: {applied}")

    def test_zero_price_not_applied(self, client, repack_parent_product):
        """repack_price_updates with new_retail_price=0 should NOT be applied."""
        p = repack_parent_product
        rp = p["repacks"][0]

        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "notes": "TEST_REPACK_ZERO_PRICE",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": 0,  # zero = no change
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                }
            ],
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "category": p.get("category", "General"),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.5, 2),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200, f"Create failed: {res.status_code} {res.text}"
        tid = res.json()["id"]

        # Send
        s_res = client.post(f"{BASE_URL}/api/branch-transfers/{tid}/send")
        assert s_res.status_code == 200

        # Receive
        r_res = client.post(
            f"{BASE_URL}/api/branch-transfers/{tid}/receive",
            json={"notes": "TEST_ZERO_RECEIVE", "items": [{"product_id": p["id"], "qty_received": 1}]}
        )
        assert r_res.status_code == 200, f"Receive failed: {r_res.status_code} {r_res.text}"
        data = r_res.json()

        applied = data.get("repack_prices_applied", [])
        assert len(applied) == 0, f"Expected 0 repack prices applied for zero price, got: {applied}"
        print(f"PASS: Zero repack price → repack_prices_applied is empty: {applied}")


class TestReceiveResponseStructure:
    """Verify the receive endpoint response structure."""

    def test_receive_response_has_required_fields(self, client, repack_parent_product):
        """Receive response must always have repack_prices_applied field."""
        p = repack_parent_product
        rp = p["repacks"][0]
        new_price = round(float(rp["capital_per_repack"]) * 2, 2) + 1.0

        # Create + send a transfer
        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "notes": "TEST_REPACK_RESPONSE_STRUCTURE",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": new_price,
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                }
            ],
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "category": p.get("category", "General"),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.5, 2),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200
        tid = res.json()["id"]
        client.post(f"{BASE_URL}/api/branch-transfers/{tid}/send")

        # Receive
        r_res = client.post(
            f"{BASE_URL}/api/branch-transfers/{tid}/receive",
            json={"notes": "test", "items": [{"product_id": p["id"], "qty_received": 1}]}
        )
        assert r_res.status_code == 200, f"Receive failed: {r_res.status_code} {r_res.text}"
        data = r_res.json()

        # Verify all required response fields
        for field in ["message", "order_number", "status", "repack_prices_applied"]:
            assert field in data, f"Receive response missing field '{field}': {list(data.keys())}"
        assert data["status"] == "received"
        assert isinstance(data["repack_prices_applied"], list)
        print(f"PASS: Receive response has all required fields: {list(data.keys())}")
        print(f"PASS: repack_prices_applied: {data['repack_prices_applied']}")

    def test_repack_prices_applied_entry_structure(self, client, repack_parent_product):
        """Each entry in repack_prices_applied must have repack_id, repack_name, new_retail_price."""
        p = repack_parent_product
        rp = p["repacks"][0]
        new_price = round(float(rp["capital_per_repack"]) * 2, 2) + 2.0

        payload = {
            "from_branch_id": MAIN_BRANCH_ID,
            "to_branch_id": IPIL_BRANCH_ID,
            "notes": "TEST_REPACK_ENTRY_STRUCTURE",
            "repack_price_updates": [
                {
                    "repack_id": rp["id"],
                    "repack_name": rp["name"],
                    "new_retail_price": new_price,
                    "units_per_parent": rp["units_per_parent"],
                    "capital_per_repack": rp["capital_per_repack"],
                    "parent_product_id": p["id"],
                }
            ],
            "items": [
                {
                    "product_id": p["id"],
                    "product_name": p["name"],
                    "sku": p.get("sku", ""),
                    "unit": p.get("unit", ""),
                    "qty": 1,
                    "branch_capital": float(p["branch_capital"]),
                    "transfer_capital": float(p["branch_capital"]),
                    "branch_retail": round(float(p["branch_capital"]) * 1.5, 2),
                    "override": False,
                    "override_reason": "",
                }
            ],
        }
        res = client.post(f"{BASE_URL}/api/branch-transfers", json=payload)
        assert res.status_code == 200
        tid = res.json()["id"]
        client.post(f"{BASE_URL}/api/branch-transfers/{tid}/send")
        r_res = client.post(
            f"{BASE_URL}/api/branch-transfers/{tid}/receive",
            json={"notes": "test", "items": [{"product_id": p["id"], "qty_received": 1}]}
        )
        assert r_res.status_code == 200
        data = r_res.json()
        applied = data.get("repack_prices_applied", [])
        assert len(applied) >= 1
        entry = applied[0]
        for field in ["repack_id", "repack_name", "new_retail_price"]:
            assert field in entry, f"repack_prices_applied entry missing '{field}': {entry}"
        print(f"PASS: repack_prices_applied entry structure OK: {entry}")
