"""
Test script for SMS service
Run this to test SMS confirmations
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.sms_service import sms_service


def test_sms():
    """Test SMS sending"""
    print("🧪 Testing SMS Service\n")
    print("=" * 60)

    # Test confirmation SMS
    print("\n1️⃣  Testing Confirmation SMS...")

    # Use your actual phone number here
    test_phone = input("Enter your phone number (e.g., +14085551234): ").strip()

    if not test_phone:
        print("❌ No phone number provided. Test skipped.")
        return

    success = sms_service.send_confirmation_sms(
        to_phone=test_phone,
        name="Test User",
        party_size=4,
        date="2026-01-05",
        time="19:00",
        table_number=5
    )

    if success:
        print("✅ Confirmation SMS sent! Check your phone.")
    else:
        print("❌ SMS failed. Check Twilio credentials in .env")

    print("\n" + "-" * 60)

    # Test cancellation SMS
    print("\n2️⃣  Testing Cancellation SMS...")

    proceed = input("Send cancellation SMS too? (y/n): ").strip().lower()

    if proceed == 'y':
        success = sms_service.send_cancellation_sms(
            to_phone=test_phone,
            name="Test User",
            date="2026-01-05",
            time="19:00"
        )

        if success:
            print("✅ Cancellation SMS sent! Check your phone.")
        else:
            print("❌ SMS failed.")

    print("\n" + "=" * 60)
    print("\n💡 SMS Messages Include:")
    print("   ✅ Confirmation: Name, party size, date, time, table number")
    print("   ❌ Cancellation: Name, date, time, phone number to rebook")
    print("\n📱 Messages are formatted professionally and mobile-friendly!")


if __name__ == "__main__":
    test_sms()