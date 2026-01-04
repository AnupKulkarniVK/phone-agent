"""
Migration: Add Quality Metrics Tables
Adds 3 new tables: call_metrics, call_quality, conversation_turns
Does NOT modify existing tables (reservations, tables)
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.database import Base, engine, SessionLocal
from sqlalchemy import text


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    session = SessionLocal()
    try:
        result = session.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
        return result.fetchone() is not None
    finally:
        session.close()


def migrate_quality_metrics():
    """Add quality metrics tables to database"""

    print("🔄 Starting Quality Metrics Migration...")
    print("")

    # Check existing tables
    print("📋 Checking existing tables...")
    existing_tables = {
        "reservations": check_table_exists("reservations"),
        "tables": check_table_exists("tables"),
        "call_metrics": check_table_exists("call_metrics"),
        "call_quality": check_table_exists("call_quality"),
        "conversation_turns": check_table_exists("conversation_turns")
    }

    for table_name, exists in existing_tables.items():
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"  {status}: {table_name}")

    print("")

    # Verify existing tables are safe
    if not existing_tables["reservations"] or not existing_tables["tables"]:
        print("⚠️  WARNING: Core tables (reservations/tables) missing!")
        print("   Run init_db() first to create base tables")
        return False

    # Check if migration needed
    if existing_tables["call_metrics"] and existing_tables["call_quality"] and existing_tables["conversation_turns"]:
        print("✅ Quality metrics tables already exist!")
        print("   No migration needed.")
        return True

    # Create new tables
    print("📝 Creating quality metrics tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("   ✅ call_metrics")
        print("   ✅ call_quality")
        print("   ✅ conversation_turns")
        print("")
        print("✅ Migration completed successfully!")
        print("")
        print("📊 New tables added:")
        print("   • call_metrics - stores objective call data")
        print("   • call_quality - stores quality scores (5 dimensions)")
        print("   • conversation_turns - stores full transcripts")
        print("")
        print("🔒 Existing tables preserved:")
        print("   • reservations")
        print("   • tables")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate_quality_metrics()
    if success:
        print("")
        print("🎉 You can now:")
        print("   1. Collect metrics during calls")
        print("   2. Calculate quality scores")
        print("   3. View data in dashboard")
    sys.exit(0 if success else 1)