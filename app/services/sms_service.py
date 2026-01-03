"""
SMS Service - Send confirmation messages via Twilio
"""
import os
import ssl
import certifi
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient

load_dotenv()


class SMSService:
    """Service for sending SMS messages via Twilio"""

    def __init__(self):
        """Initialize Twilio SMS client with proper SSL configuration"""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")

        if not all([account_sid, auth_token, self.from_phone]):
            print("⚠️  Twilio credentials not fully configured - SMS disabled")
            self.client = None
        else:
            # Create custom HTTP client with proper SSL verification
            # This fixes SSL certificate errors on macOS
            http_client = TwilioHttpClient()
            http_client.session.verify = certifi.where()

            self.client = Client(account_sid, auth_token, http_client=http_client)

    def send_confirmation_sms(
            self,
            to_phone: str,
            name: str,
            party_size: int,
            date: str,
            time: str,
            table_number: int = None
    ) -> bool:
        """
        Send reservation confirmation SMS

        Args:
            to_phone: Customer's phone number
            name: Customer name
            party_size: Number of people
            date: Reservation date (YYYY-MM-DD)
            time: Reservation time (HH:MM)
            table_number: Assigned table number

        Returns:
            True if SMS sent successfully, False otherwise
        """
        if not self.client:
            print("⚠️  SMS not configured - skipping")
            return False

        # Format the date nicely
        from datetime import datetime
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = dt.strftime("%A, %B %d, %Y")
        except:
            formatted_date = date

        # Format time (convert from 24hr to 12hr)
        try:
            time_obj = datetime.strptime(time, "%H:%M")
            formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")
        except:
            formatted_time = time

        # Build message
        table_info = f" at Table {table_number}" if table_number else ""

        message = f"""✅ Luigi's Italian Restaurant

Your reservation is CONFIRMED!

👤 Name: {name}
👥 Party: {party_size} people
📅 Date: {formatted_date}
🕐 Time: {formatted_time}{table_info}

📍 123 Main Street, San Jose, CA
📞 (408) 555-LUIGI

See you soon! 🍝"""

        try:
            # Send SMS
            msg = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=to_phone
            )

            print(f"✅ SMS sent to {to_phone}: {msg.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send SMS: {e}")
            return False

    def send_cancellation_sms(
            self,
            to_phone: str,
            name: str,
            date: str,
            time: str
    ) -> bool:
        """
        Send reservation cancellation SMS

        Args:
            to_phone: Customer's phone number
            name: Customer name
            date: Reservation date
            time: Reservation time

        Returns:
            True if SMS sent successfully
        """
        if not self.client:
            print("⚠️  SMS not configured - skipping")
            return False

        # Format the date and time
        from datetime import datetime
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            formatted_date = dt.strftime("%A, %B %d")
        except:
            formatted_date = date

        try:
            time_obj = datetime.strptime(time, "%H:%M")
            formatted_time = time_obj.strftime("%I:%M %p").lstrip("0")
        except:
            formatted_time = time

        message = f"""❌ Luigi's Italian Restaurant

Your reservation has been CANCELLED.

👤 Name: {name}
📅 Date: {formatted_date}
🕐 Time: {formatted_time}

To make a new reservation, call us at:
📞 +1-833-402-5651

Hope to see you soon! 🍝"""

        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_phone,
                to=to_phone
            )

            print(f"✅ Cancellation SMS sent to {to_phone}: {msg.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send cancellation SMS: {e}")
            return False


# Create singleton instance
sms_service = SMSService()