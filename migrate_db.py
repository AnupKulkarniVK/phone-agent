"""
Database migration script
Adds assigned_table_id column to existing reservations table
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import engine, SessionLocal, Reservation
from sqlalchemy import text


def migrate_database():
    """Add assigned_table_id column to reservations table"""

    print("🔄 Starting database migration...")

    session = SessionLocal()

    try:
        # Check if column already exists
        result = session.execute(text("PRAGMA table_info(reservations)"))
        columns = [row[1] for row in result]

        if 'assigned_table_id' in columns:
            print("✅ Column 'assigned_table_id' already exists. No migration needed.")
            return

        # Add the column
        print("📝 Adding 'assigned_table_id' column to reservations table...")
        session.execute(text("ALTER TABLE reservations ADD COLUMN assigned_table_id INTEGER"))
        session.commit()

        print("✅ Migration completed successfully!")
        print("   - Added 'assigned_table_id' column to reservations table")
        print("   - Existing reservations will have NULL for this field (OK)")
        print("   - New reservations will get proper table assignments")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate_database()