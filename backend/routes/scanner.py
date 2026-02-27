"""
Scanner Sessions — WebSocket-based linked barcode scanner.
Desktop creates a session → shows QR. Phone scans QR → connects → sends barcodes → desktop receives.
Sessions are branch-scoped.
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from config import db
from utils import get_current_user, now_iso, new_id
from typing import Dict, Set
import asyncio
import json

router = APIRouter(prefix="/scanner", tags=["Scanner"])

# ── In-memory session registry ──────────────────────────────────────────────
# { session_id: { "branch_id": str, "org_id": str, "desktop_ws": WebSocket|None, "phone_ws": WebSocket|None } }
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
        "status": "waiting",  # waiting | connected | closed
    }
    # Store in DB for persistence, and in memory for WS routing
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


@router.post("/close-session/{session_id}")
async def close_session(session_id: str, user=Depends(get_current_user)):
    """Desktop closes the scanner session."""
    await db.scanner_sessions.update_one({"id": session_id}, {"$set": {"status": "closed"}})
    if session_id in active_sessions:
        sess = active_sessions[session_id]
        # Close phone WS if connected
        if sess.get("phone_ws"):
            try:
                await sess["phone_ws"].close()
            except Exception:
                pass
        del active_sessions[session_id]
    return {"closed": True}


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
