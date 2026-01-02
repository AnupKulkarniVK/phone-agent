"""
Restaurant reservation tools for Claude AI function calling
These are the actions the AI agent can perform
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import get_db, Reservation, Table



def check_availability(party_size: int, date: str, time: str) -> Dict[str, Any]:
    """
    Check if restaurant has available tables for given party size, date, and time.

    Args:
        party_size: Number of people
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (24-hour)

    Returns:
        Dict with availability info
    """
    db = get_db()
    try:
        # Find tables that can accommodate party size
        suitable_tables = db.query(Table).filter(
            Table.capacity >= party_size,
            Table.is_active == True
        ).all()

        if not suitable_tables:
            return {
                "available": False,
                "reason": f"No tables large enough for {party_size} people",
                "suggested_alternatives": []
            }

        # Check if any are already reserved at this time
        # (Simple logic: one reservation per time slot for now)
        existing = db.query(Reservation).filter(
            Reservation.date == date,
            Reservation.time == time,
            Reservation.status == 'confirmed'
        ).all()

        # Count how many tables are booked
        booked_count = len(existing)
        total_suitable = len(suitable_tables)

        if booked_count >= total_suitable:
            # All tables booked, suggest alternative times
            alternatives = suggest_alternative_times(date, time, party_size, db)
            return {
                "available": False,
                "reason": f"All tables for {party_size} are booked at {time}",
                "suggested_alternatives": alternatives
            }

        return {
            "available": True,
            "tables_available": total_suitable - booked_count,
            "party_size": party_size,
            "date": date,
            "time": time
        }

    finally:
        db.close()


def create_reservation(
        name: str,
        party_size: int,
        date: str,
        time: str,
        phone: str = None,
        call_sid: str = None
) -> Dict[str, Any]:
    """
    Create a new reservation.

    Args:
        name: Customer name
        party_size: Number of people
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (24-hour)
        phone: Customer phone number (optional)
        call_sid: Twilio call ID (optional)

    Returns:
        Dict with reservation details
    """
    db = get_db()
    try:
        # First check availability
        availability = check_availability(party_size, date, time)

        if not availability["available"]:
            return {
                "success": False,
                "error": availability["reason"],
                "suggested_alternatives": availability.get("suggested_alternatives", [])
            }

        # Create reservation
        reservation = Reservation(
            name=name,
            phone=phone,
            party_size=party_size,
            date=date,
            time=time,
            status='confirmed',
            call_sid=call_sid
        )

        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        return {
            "success": True,
            "reservation_id": reservation.id,
            "name": name,
            "party_size": party_size,
            "date": date,
            "time": time,
            "status": "confirmed"
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to create reservation: {str(e)}"
        }
    finally:
        db.close()


def get_reservations(date: str = None, name: str = None) -> List[Dict[str, Any]]:
    """
    Get existing reservations, optionally filtered by date or name.

    Args:
        date: Filter by date (YYYY-MM-DD format)
        name: Filter by customer name

    Returns:
        List of reservation dictionaries
    """
    db = get_db()
    try:
        query = db.query(Reservation).filter(Reservation.status == 'confirmed')

        if date:
            query = query.filter(Reservation.date == date)
        if name:
            query = query.filter(Reservation.name.ilike(f"%{name}%"))

        reservations = query.all()
        return [r.to_dict() for r in reservations]

    finally:
        db.close()


def cancel_reservation(reservation_id: int = None, name: str = None, date: str = None) -> Dict[str, Any]:
    """
    Cancel a reservation.

    Args:
        reservation_id: Specific reservation ID (if known)
        name: Customer name (to find reservation)
        date: Date of reservation (to narrow search)

    Returns:
        Dict with cancellation status
    """
    db = get_db()
    try:
        if reservation_id:
            reservation = db.query(Reservation).filter(
                Reservation.id == reservation_id
            ).first()
        elif name and date:
            reservation = db.query(Reservation).filter(
                Reservation.name.ilike(f"%{name}%"),
                Reservation.date == date,
                Reservation.status == 'confirmed'
            ).first()
        elif name:
            # Find most recent reservation for this name
            reservation = db.query(Reservation).filter(
                Reservation.name.ilike(f"%{name}%"),
                Reservation.status == 'confirmed'
            ).order_by(Reservation.created_at.desc()).first()
        else:
            return {
                "success": False,
                "error": "Need either reservation_id or name to cancel"
            }

        if not reservation:
            return {
                "success": False,
                "error": "No reservation found"
            }

        # Cancel it
        reservation.status = 'cancelled'
        db.commit()

        return {
            "success": True,
            "message": f"Cancelled reservation for {reservation.name} on {reservation.date} at {reservation.time}",
            "reservation": reservation.to_dict()
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": f"Failed to cancel: {str(e)}"
        }
    finally:
        db.close()


def suggest_alternative_times(date: str, requested_time: str, party_size: int, db) -> List[str]:
    """Suggest alternative time slots if requested time is unavailable"""
    from datetime import datetime, timedelta

    alternatives = []
    base_time = datetime.strptime(requested_time, "%H:%M")

    # Try ±30 min, ±1 hour
    time_offsets = [-60, -30, 30, 60]

    for offset in time_offsets:
        alt_time = (base_time + timedelta(minutes=offset)).strftime("%H:%M")

        # Check if this time is available
        result = check_availability(party_size, date, alt_time)
        if result.get("available"):
            alternatives.append(alt_time)
            if len(alternatives) >= 2:  # Suggest max 2 alternatives
                break

    return alternatives


# Tool definitions for Claude (function calling schema)
TOOL_DEFINITIONS = [
    {
        "name": "check_availability",
        "description": "Check if restaurant has available tables for a given party size, date, and time. Use this BEFORE creating a reservation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "party_size": {
                    "type": "integer",
                    "description": "Number of people in the party"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (e.g., 2024-01-15)"
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM 24-hour format (e.g., 19:00 for 7pm)"
                }
            },
            "required": ["party_size", "date", "time"]
        }
    },
    {
        "name": "create_reservation",
        "description": "Create a confirmed reservation. Only use this AFTER checking availability and getting customer confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Customer's full name"
                },
                "party_size": {
                    "type": "integer",
                    "description": "Number of people"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "Time in HH:MM 24-hour format"
                },
                "phone": {
                    "type": "string",
                    "description": "Customer phone number (optional)"
                }
            },
            "required": ["name", "party_size", "date", "time"]
        }
    },
    {
        "name": "get_reservations",
        "description": "Look up existing reservations by date or customer name",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Filter by date (YYYY-MM-DD format)"
                },
                "name": {
                    "type": "string",
                    "description": "Filter by customer name"
                }
            }
        }
    },
    {
        "name": "cancel_reservation",
        "description": "Cancel an existing reservation",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Customer name"
                },
                "date": {
                    "type": "string",
                    "description": "Date of reservation (YYYY-MM-DD)"
                }
            },
            "required": ["name"]
        }
    }
]


# Map tool names to functions
TOOL_FUNCTIONS = {
    "check_availability": check_availability,
    "create_reservation": create_reservation,
    "get_reservations": get_reservations,
    "cancel_reservation": cancel_reservation
}
