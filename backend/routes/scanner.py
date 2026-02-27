"""
Scanner Sessions — Linked barcode scanner with REST polling + WebSocket.
Desktop creates a session → shows QR. Phone scans QR → sends barcodes via REST.
Desktop polls for new scans. WebSocket used as optional real-time boost.
Sessions are branch-scoped.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from config import db
from utils import get_current_user, now_iso, new_id
from typing import Dict
import json

router = APIRouter(prefix="/scanner", tags=["Scanner"])

# ── In-memory session registry (for WebSocket only) ─────────────────────────
active_sessions: Dict[str, dict] = {}


@router.post("/create-session")
async def create_session(data: dict, user=Depends(get_current_user)):
    """Desktop creates a scanner session linked to current branch."""
    branch_id = data.get("branch_id")
    if not branch_id:
        raise HTTPException(status_code=400, detail="branch_id is required")

    session_id = new_id()
    session = {
        "id": session_id,
        "branch_id": branch_id,
        "org_id": user.get("org_id", ""),
        "created_by": user.get("id", ""),
        "created_at": now_iso(),
        "status": "waiting",
        "scans": [],  # REST-based scan queue
        "last_poll_index": 0,
    }
    await db.scanner_sessions.insert_one({**session, "_id": session_id})
    active_sessions[session_id] = {
        "branch_id": branch_id,
        "org_id": user.get("org_id", ""),
        "desktop_ws": None,
        "phone_ws": None,
    }
    return {"session_id": session_id, "branch_id": branch_id}


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Phone checks session validity before connecting."""
    session = await db.scanner_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == "closed":
        raise HTTPException(status_code=410, detail="Session expired")
    return {"session_id": session["id"], "branch_id": session["branch_id"], "status": session["status"]}


@router.post("/connect/{session_id}")
async def connect_session(session_id: str):
    """Phone confirms it has connected to the session (sets status to 'connected')."""
    result = await db.scanner_sessions.update_one(
        {"id": session_id, "status": {"$ne": "closed"}},
        {"$set": {"status": "connected", "updated_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found or closed")
    return {"connected": True}


@router.post("/close-session/{session_id}")
async def close_session(session_id: str, user=Depends(get_current_user)):
    """Desktop closes the scanner session."""
    await db.scanner_sessions.update_one({"id": session_id}, {"$set": {"status": "closed"}})
    if session_id in active_sessions:
        sess = active_sessions[session_id]
        if sess.get("phone_ws"):
            try:
                await sess["phone_ws"].close()
            except Exception:
                pass
        del active_sessions[session_id]
    return {"closed": True}


# ── REST-based scan (reliable, no WebSocket needed) ─────────────────────────

@router.post("/scan/{session_id}")
async def submit_scan(session_id: str, data: dict):
    """Phone submits a barcode scan via REST. Stores result for desktop to poll."""
    session = await db.scanner_sessions.find_one({"id": session_id, "status": {"$ne": "closed"}}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or closed")

    barcode = data.get("barcode", "").strip()
    if not barcode:
        raise HTTPException(status_code=400, detail="Barcode required")

    branch_id = session["branch_id"]

    # Look up product
    product = await db.products.find_one({"barcode": barcode, "active": True}, {"_id": 0})
    if not product:
        scan_result = {"found": False, "barcode": barcode, "scanned_at": now_iso()}
        await db.scanner_sessions.update_one(
            {"id": session_id}, {"$push": {"scans": scan_result}, "$set": {"status": "connected"}}
        )
        return scan_result

    # Get branch-specific pricing
    override = await db.branch_prices.find_one(
        {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
    )
    if override and override.get("prices"):
        product = {**product, "prices": {**(product.get("prices") or {}), **override["prices"]}}
        if override.get("cost_price") is not None:
            product["cost_price"] = override["cost_price"]

    # Get stock
    inv = await db.inventory.find_one(
        {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
    )
    product["available"] = float(inv["quantity"]) if inv else 0

    scan_result = {"found": True, "barcode": barcode, "product": product, "scanned_at": now_iso()}
    await db.scanner_sessions.update_one(
        {"id": session_id}, {"$push": {"scans": scan_result}, "$set": {"status": "connected"}}
    )

    # Also try WebSocket real-time delivery (best-effort)
    if session_id in active_sessions:
        desktop_ws = active_sessions[session_id].get("desktop_ws")
        if desktop_ws:
            try:
                await desktop_ws.send_json({"type": "scan_result", **scan_result})
            except Exception:
                pass

    return scan_result


@router.get("/scans/{session_id}")
async def get_scans(session_id: str, after: int = 0, user=Depends(get_current_user)):
    """Desktop polls for new scans. 'after' = index of last processed scan."""
    session = await db.scanner_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_scans = session.get("scans", [])
    new_scans = all_scans[after:]
    return {
        "scans": new_scans,
        "total": len(all_scans),
        "status": session.get("status", "waiting"),
    }


# ── WebSocket endpoints ─────────────────────────────────────────────────────

async def ws_desktop(websocket: WebSocket, session_id: str):
    """Desktop connects to receive scanned barcodes."""
    await websocket.accept()

    if session_id not in active_sessions:
        # Try to reload from DB
        session = await db.scanner_sessions.find_one({"id": session_id, "status": {"$ne": "closed"}}, {"_id": 0})
        if not session:
            await websocket.send_json({"type": "error", "message": "Invalid session"})
            await websocket.close()
            return
        active_sessions[session_id] = {
            "branch_id": session["branch_id"],
            "org_id": session.get("org_id", ""),
            "desktop_ws": None,
            "phone_ws": None,
        }

    active_sessions[session_id]["desktop_ws"] = websocket
    await websocket.send_json({"type": "connected", "role": "desktop", "session_id": session_id})

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Desktop can send commands to phone (e.g., "stop", "flash")
            if msg.get("type") == "command" and active_sessions[session_id].get("phone_ws"):
                await active_sessions[session_id]["phone_ws"].send_json(msg)
    except WebSocketDisconnect:
        if session_id in active_sessions:
            active_sessions[session_id]["desktop_ws"] = None
            # Notify phone
            if active_sessions[session_id].get("phone_ws"):
                try:
                    await active_sessions[session_id]["phone_ws"].send_json({"type": "desktop_disconnected"})
                except Exception:
                    pass


async def ws_phone(websocket: WebSocket, session_id: str):
    """Phone connects to send scanned barcodes."""
    await websocket.accept()

    if session_id not in active_sessions:
        session = await db.scanner_sessions.find_one({"id": session_id, "status": {"$ne": "closed"}}, {"_id": 0})
        if not session:
            await websocket.send_json({"type": "error", "message": "Invalid session"})
            await websocket.close()
            return
        active_sessions[session_id] = {
            "branch_id": session["branch_id"],
            "org_id": session.get("org_id", ""),
            "desktop_ws": None,
            "phone_ws": None,
        }

    active_sessions[session_id]["phone_ws"] = websocket
    branch_id = active_sessions[session_id]["branch_id"]

    # Mark session as connected
    await db.scanner_sessions.update_one({"id": session_id}, {"$set": {"status": "connected"}})

    # Notify desktop
    desktop_ws = active_sessions[session_id].get("desktop_ws")
    if desktop_ws:
        try:
            await desktop_ws.send_json({"type": "phone_connected"})
        except Exception:
            pass

    await websocket.send_json({"type": "connected", "role": "phone", "session_id": session_id, "branch_id": branch_id})

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "barcode_scan":
                barcode = msg.get("barcode", "").strip()
                if not barcode:
                    continue

                # Look up product by barcode
                product = await db.products.find_one({"barcode": barcode, "active": True}, {"_id": 0})
                if not product:
                    await websocket.send_json({"type": "scan_result", "found": False, "barcode": barcode})
                    desktop_ws = active_sessions[session_id].get("desktop_ws")
                    if desktop_ws:
                        try:
                            await desktop_ws.send_json({"type": "scan_result", "found": False, "barcode": barcode})
                        except Exception:
                            pass
                    continue

                # Get branch-specific pricing
                override = await db.branch_prices.find_one(
                    {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
                )
                if override and override.get("prices"):
                    product = {**product, "prices": {**(product.get("prices") or {}), **override["prices"]}}
                    if override.get("cost_price") is not None:
                        product["cost_price"] = override["cost_price"]

                # Get stock
                inv = await db.inventory.find_one(
                    {"product_id": product["id"], "branch_id": branch_id}, {"_id": 0}
                )
                product["available"] = float(inv["quantity"]) if inv else 0

                result = {"type": "scan_result", "found": True, "product": product, "barcode": barcode}

                # Send to phone
                await websocket.send_json(result)

                # Send to desktop
                desktop_ws = active_sessions[session_id].get("desktop_ws")
                if desktop_ws:
                    try:
                        await desktop_ws.send_json(result)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        if session_id in active_sessions:
            active_sessions[session_id]["phone_ws"] = None
            await db.scanner_sessions.update_one({"id": session_id}, {"$set": {"status": "waiting"}})
            desktop_ws = active_sessions[session_id].get("desktop_ws")
            if desktop_ws:
                try:
                    await desktop_ws.send_json({"type": "phone_disconnected"})
                except Exception:
                    pass
