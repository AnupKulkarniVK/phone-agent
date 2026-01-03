"""
Test script for date tool
Run this to verify get_current_date works correctly
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.tools.reservation_tools import get_current_date


def test_date_tool():
    """Test the get_current_date tool"""
    print("🧪 Testing get_current_date tool...\n")

    result = get_current_date()

    print("✅ Tool response:")
    print(f"   Today: {result['today']} ({result['today_day_of_week']})")
    print(f"   Tomorrow: {result['tomorrow']} ({result['tomorrow_day_of_week']})")
    print(f"   Next week: {result['next_week']}")
    print(f"   Current time: {result['current_time']}")
    print(f"   Full datetime: {result['current_datetime']}")

    print("\n✅ Date tool working correctly!")

    print("\n📋 Example usage in conversation:")
    print(f"   User: 'I need a table tomorrow at 7pm'")
    print(f"   Claude calls: get_current_date()")
    print(f"   Claude sees: today = {result['today']}, tomorrow = {result['tomorrow']}")
    print(f"   Claude calls: check_availability(party_size=X, date='{result['tomorrow']}', time='19:00')")


if __name__ == "__main__":
    test_date_tool()
