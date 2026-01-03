"""
Restaurant reservation tools for Claude AI function calling
Proper table assignment - each reservation gets a specific table
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import get_db, Reservation, Table


def get_current_date() -> Dict[str, Any]:
    """
    Get the current date and time information.
    Use this tool to know what "today", "tomorrow", "this week" means.

    Returns:
        Dict with current date info
    """
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    next_week = now + timedelta(days=7)

    return {
        "current_datetime": now.isoformat(),
        "today": now.strftime("%Y-%m-%d"),
        "today_day_of_week": now.strftime("%A"),
        "tomorrow": tomorrow.strftime("%Y-%m-%d"),
        "tomorrow_day_of_week": tomorrow.strftime("%A"),
        "next_week": next_week.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M"),
        "year": now.year,
        "month": now.month,
        "day": now.day
    }


def check_availability(party_size: int, date: str, time: str) -> Dict[str, Any]:
    """
    Check if restaurant has available tables for given party size, date, and time.
    Uses PROPER table assignment - checks which specific tables are available.

    Args:
        party_size: Number of people
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (24-hour)

    Returns:
        Dict with availability info and available table IDs
    """
    db = get_db()
    try:
        # STEP 1: Find ALL tables that can accommodate this party size
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

        # STEP 2: Find which tables are ALREADY ASSIGNED for this date/time
        booked_reservations = db.query(Reservation).filter(
            Reservation.date == date,
            Reservation.time == time,
            Reservation.status == 'confirmed',
            Reservation.assigned_table_id.isnot(None)  # Only confirmed assignments
        ).all()

        # Get set of booked table IDs
        booked_table_ids = {res.assigned_table_id for res in booked_reservations}

        # STEP 3: Filter to only AVAILABLE tables (not in booked list)
        available_tables = [
            table for table in suitable_tables
            if table.id not in booked_table_ids
        ]

        if not available_tables:
            # No tables available - suggest alternative times
            alternatives = suggest_alternative_times(date, time, party_size, db)
            return {
                "available": False,
                "reason": f"All tables for {party_size}+ people are booked at {time}",
                "suggested_alternatives": alternatives,
                "booked_tables": len(booked_table_ids),
                "total_suitable_tables": len(suitable_tables)
            }

        # STEP 4: Return available tables (we'll pick the best one when creating reservation)
        return {
            "available": True,
            "available_tables": [{"id": t.id, "number": t.table_number, "capacity": t.capacity} for t in available_tables],
            "count": len(available_tables),
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
    Create a new reservation with SPECIFIC table assignment.

    Algorithm:
    1. Check availability to get list of available tables
    2. Pick the SMALLEST table that fits (optimize space)
    3. Create reservation with assigned_table_id

    Args:
        name: Customer name
        party_size: Number of people
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (24-hour)
        phone: Customer phone number (optional)
        call_sid: Twilio call ID (optional)

    Returns:
        Dict with reservation details including assigned table
    """
    db = get_db()
    try:
        # STEP 1: Check availability
        availability = check_availability(party_size, date, time)

        if not availability["available"]:
            return {
                "success": False,
                "error": availability["reason"],
                "suggested_alternatives": availability.get("suggested_alternatives", [])
            }

        # STEP 2: Pick the BEST table (smallest that fits = optimal space usage)
        available_tables = availability["available_tables"]

        # Sort by capacity (smallest first)
        best_table = min(available_tables, key=lambda t: t["capacity"])

        # STEP 3: Create reservation WITH assigned table
        reservation = Reservation(
            name=name,
            phone=phone,
            party_size=party_size,
            date=date,
            time=time,
            status='confirmed',
            assigned_table_id=best_table["id"],  # ← KEY: Assign specific table
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
            "status": "confirmed",
            "assigned_table": {
                "table_id": best_table["id"],
                "table_number": best_table["number"],
                "table_capacity": best_table["capacity"]
            }
        }

    except Exception as e:
        db.rollback()
        print(f"Error creating reservation: {e}")
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

        # Get table info before canceling (for response message)
        table_info = ""
        if reservation.assigned_table_id:
            table = db.query(Table).filter(Table.id == reservation.assigned_table_id).first()
            if table:
                table_info = f" (Table {table.table_number})"

        # Cancel it (this frees up the table automatically)
        reservation.status = 'cancelled'
        db.commit()

        return {
            "success": True,
            "message": f"Cancelled reservation for {reservation.name} on {reservation.date} at {reservation.time}{table_info}",
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
    """
    Suggest alternative time slots if requested time is unavailable.
    Checks actual table availability for each alternative.
    """
    alternatives = []
    base_time = datetime.strptime(requested_time, "%H:%M")

    # Try ±30 min, ±1 hour, ±90 min
    time_offsets = [-90, -60, -30, 30, 60, 90]

    for offset in time_offsets:
        alt_time = (base_time + timedelta(minutes=offset)).strftime("%H:%M")

        # Make sure it's within restaurant hours (5pm - 10pm)
        alt_hour = int(alt_time.split(':')[0])
        if alt_hour < 17 or alt_hour >= 22:  # Before 5pm or after 10pm
            continue

        # Check if this time is actually available
        # Re-use our check_availability function
        temp_db = get_db()
        try:
            suitable_tables = temp_db.query(Table).filter(
                Table.capacity >= party_size,
                Table.is_active == True
            ).all()

            booked = temp_db.query(Reservation).filter(
                Reservation.date == date,
                Reservation.time == alt_time,
                Reservation.status == 'confirmed',
                Reservation.assigned_table_id.isnot(None)
            ).all()

            booked_ids = {r.assigned_table_id for r in booked}
            available = [t for t in suitable_tables if t.id not in booked_ids]

            if available:
                alternatives.append(alt_time)
                if len(alternatives) >= 3:  # Suggest max 3 alternatives
                    break
        finally:
            temp_db.close()

    return alternatives


# Tool definitions for Claude (function calling schema)
TOOL_DEFINITIONS = [
    {
        "name": "get_current_date",
        "description": "Get today's date and time. ALWAYS use this first when user says 'today', 'tomorrow', 'this week', 'next week', or any relative date. This tells you what the actual calendar date is.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
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
    "get_current_date": get_current_date,
    "check_availability": check_availability,
    "create_reservation": create_reservation,
    "get_reservations": get_reservations,
    "cancel_reservation": cancel_reservation
}