"""
seats.py — Seat locking & availability API
==========================================
Routes:
  POST /seats/lock          — lock one or more seats for current user (10 min hold)
  POST /seats/release       — release locks the user chose to deselect
  GET  /seats/status/<sid>  — return which seats are locked/booked for a show
  POST /seats/confirm       — called after successful payment to mark seats permanent
"""
from flask import Blueprint, request, jsonify, session
from models.models import SeatLock, BookedSeat, UserBooking, db
from routes.auth import login_required
from sqlalchemy import text
from datetime import datetime, timedelta

seats_bp = Blueprint("seats", __name__, url_prefix="/seats")

LOCK_MINUTES = 5    # How long a seat hold lasts (5 min real-world style)


def _now():
    return datetime.utcnow()


def _expire_stale_locks():
    """Release any locks whose timer has run out."""
    db.session.execute(
        text("""
            UPDATE seat_locks
            SET status = 'released'
            WHERE status = 'locked'
              AND expires_at <= :now
        """),
        {"now": _now()}
    )
    db.session.commit()


# ── POST /seats/lock ─────────────────────────────────────────────────────────
@seats_bp.route("/lock", methods=["POST"])
@login_required
def lock_seats():
    """
    Body: { show_id, seat_ids: ["A01","A02",...] }
    Returns: { success, locked: [...], conflicts: [...] }
    """
    data      = request.get_json(silent=True) or {}
    show_id   = data.get("show_id", "").strip()
    seat_ids  = data.get("seat_ids", [])
    user_id   = session["user_id"]
    sid       = session.get("_id", str(user_id))   # use session id as fingerprint

    if not show_id or not seat_ids:
        return jsonify({"success": False, "message": "show_id and seat_ids required"}), 400

    _expire_stale_locks()   # clean up expired holds first

    locked    = []
    conflicts = []

    for seat_id in seat_ids:
        # Check booked (permanent)
        already_booked = db.session.execute(
            text("SELECT 1 FROM booked_seats WHERE show_id=:sid AND seat_id=:seat"),
            {"sid": show_id, "seat": seat_id}
        ).fetchone()
        if already_booked:
            conflicts.append({"seat_id": seat_id, "reason": "booked"})
            continue

        # Check locked by someone else
        existing = SeatLock.query.filter_by(
            show_id=show_id, seat_id=seat_id, status="locked"
        ).first()

        if existing:
            if existing.user_id == user_id:
                # Already locked by this user — refresh expiry
                existing.expires_at = _now() + timedelta(minutes=LOCK_MINUTES)
                db.session.commit()
                locked.append(seat_id)
            else:
                conflicts.append({"seat_id": seat_id, "reason": "locked_by_other"})
        else:
            # Create new lock
            try:
                lk = SeatLock(
                    show_id    = show_id,
                    seat_id    = seat_id,
                    user_id    = user_id,
                    session_id = sid,
                    locked_at  = _now(),
                    expires_at = _now() + timedelta(minutes=LOCK_MINUTES),
                    status     = "locked"
                )
                db.session.add(lk)
                db.session.commit()
                locked.append(seat_id)
            except Exception:
                db.session.rollback()
                conflicts.append({"seat_id": seat_id, "reason": "conflict"})

    return jsonify({
        "success"  : True,
        "locked"   : locked,
        "conflicts": conflicts
    })


# ── POST /seats/release ──────────────────────────────────────────────────────
@seats_bp.route("/release", methods=["POST"])
@login_required
def release_seats():
    """
    Body: { show_id, seat_ids: ["A01",...] }
    Releases only locks belonging to the current user.
    """
    data     = request.get_json(silent=True) or {}
    show_id  = data.get("show_id", "").strip()
    seat_ids = data.get("seat_ids", [])
    user_id  = session["user_id"]

    if not show_id or not seat_ids:
        return jsonify({"success": False, "message": "show_id and seat_ids required"}), 400

    for seat_id in seat_ids:
        SeatLock.query.filter_by(
            show_id=show_id, seat_id=seat_id, user_id=user_id, status="locked"
        ).update({"status": "released"})
    db.session.commit()

    return jsonify({"success": True, "released": seat_ids})


# ── GET /seats/status/<show_id> ──────────────────────────────────────────────
@seats_bp.route("/status/<show_id>")
@login_required
def seat_status(show_id):
    """
    Returns all unavailable seats for a show so the frontend can grey them out.
    Response: {
      booked:  ["A01", "A02", ...],   # permanently booked
      locked:  ["B03", ...],          # temp-locked by OTHER users
      mine:    ["C05", ...],          # locked by the current user
      expires: { "B03": <ISO timestamp>, ... }
    }
    """
    _expire_stale_locks()
    user_id = session["user_id"]

    booked_rows = db.session.execute(
        text("SELECT seat_id FROM booked_seats WHERE show_id = :sid"),
        {"sid": show_id}
    ).fetchall()

    lock_rows = SeatLock.query.filter_by(show_id=show_id, status="locked").all()

    booked  = [r.seat_id for r in booked_rows]
    locked  = []
    mine    = []
    expires = {}

    for lk in lock_rows:
        if lk.user_id == user_id:
            mine.append(lk.seat_id)
        else:
            locked.append(lk.seat_id)
        expires[lk.seat_id] = lk.expires_at.isoformat()

    return jsonify({
        "success" : True,
        "booked"  : booked,
        "locked"  : locked,
        "mine"    : mine,
        "expires" : expires
    })


# ── POST /seats/confirm ──────────────────────────────────────────────────────
@seats_bp.route("/confirm", methods=["POST"])
@login_required
def confirm_seats():
    """
    Called by user.py after creating the UserBooking record.
    Body: { show_id, seat_ids: [...], booking_id: <int> }
    Promotes locked → confirmed and writes permanent BookedSeat rows.
    """
    data       = request.get_json(silent=True) or {}
    show_id    = data.get("show_id", "").strip()
    seat_ids   = data.get("seat_ids", [])
    booking_id = data.get("booking_id")
    user_id    = session["user_id"]

    if not show_id or not seat_ids or not booking_id:
        return jsonify({"success": False, "message": "show_id, seat_ids, booking_id required"}), 400

    for seat_id in seat_ids:
        # Mark the lock as confirmed
        SeatLock.query.filter_by(
            show_id=show_id, seat_id=seat_id, user_id=user_id
        ).update({"status": "confirmed"})

        # Write permanent record (ignore duplicate — race condition safety)
        try:
            bs = BookedSeat(
                show_id    = show_id,
                seat_id    = seat_id,
                booking_id = booking_id,
                booked_at  = _now()
            )
            db.session.add(bs)
            db.session.flush()
        except Exception:
            db.session.rollback()

    db.session.commit()
    return jsonify({"success": True, "confirmed": seat_ids})


# ── POST /seats/auto-unlock-after-show ──────────────────────────────────────
@seats_bp.route("/auto-unlock-after-show", methods=["POST"])
@login_required
def auto_unlock_after_show():
    """
    Called by the frontend 3 hours after show start (simulating show end).
    Releases all permanent BookedSeat records for the show so seats become
    available again for the next booking cycle.
    Body: { show_id: <str> }
    """
    data    = request.get_json(silent=True) or {}
    show_id = data.get("show_id", "").strip()

    if not show_id:
        return jsonify({"success": False, "message": "show_id required"}), 400

    # Delete all permanent seat holds for this show
    result = db.session.execute(
        text("DELETE FROM booked_seats WHERE show_id = :sid"),
        {"sid": show_id}
    )
    # Also release any stale locks
    db.session.execute(
        text("UPDATE seat_locks SET status='released' WHERE show_id=:sid AND status='locked'"),
        {"sid": show_id}
    )
    db.session.commit()

    deleted = result.rowcount
    return jsonify({
        "success" : True,
        "show_id" : show_id,
        "seats_released": deleted,
        "message" : f"Show ended — {deleted} seat(s) released back to available."
    })


# ── POST /seats/release-on-cancel ────────────────────────────────────────────
@seats_bp.route("/release-on-cancel", methods=["POST"])
@login_required
def release_on_cancel():
    """
    Called when a user cancels their booking.
    Removes the permanent BookedSeat rows so seats become available again.
    Body: { booking_id: <int> }
    """
    data       = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    user_id    = session["user_id"]

    if not booking_id:
        return jsonify({"success": False, "message": "booking_id required"}), 400

    # Verify ownership
    booking = UserBooking.query.filter_by(id=booking_id, user_id=user_id).first()
    if not booking:
        return jsonify({"success": False, "message": "Booking not found"}), 404

    # Delete permanent seat holds
    db.session.execute(
        text("DELETE FROM booked_seats WHERE booking_id = :bid"),
        {"bid": booking_id}
    )
    db.session.commit()

    return jsonify({"success": True, "message": "Seats released successfully"})
